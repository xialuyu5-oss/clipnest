import asyncio
import base64
from http.cookiejar import CookieJar
import time
from urllib.request import Request

import pytest
from fastapi.testclient import TestClient

from app.accounts import Accounts, Account, GENERATE, POLL, NAV, install_cookies
from app.config import Settings
from app.main import create_app
from app.media import build_media
from app.safety import UserError
from test_core import sample_info


def cookies():
    return [{'name': 'SESSDATA', 'value': 'synthetic-test-only', 'domain': '.bilibili.com',
             'path': '/', 'expires': int(time.time() + 3600)}]


class FakePlatform:
    code = 86101
    vip = 1
    valid = True

    async def request(self, url, values=None, params=None):
        if url == GENERATE:
            return {'code': 0, 'data': {'url': 'https://account.bilibili.com/h5/account-h5/auth/scan-web?key=' + 'a'*32,
                                      'qrcode_key': 'a'*32}}, []
        if url == POLL:
            assert params == {'qrcode_key': 'a'*32}
            return {'code': 0, 'data': {'code': self.code, 'refresh_token': 'never-return-or-store'}}, cookies()
        assert url == NAV and values[0]['name'] == 'SESSDATA'
        return {'code': 0 if self.valid else -101, 'data': {'isLogin': self.valid, 'vip': {'status': self.vip}}}, []


@pytest.fixture
def app(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, member_login=True, public_origin='', access_key=''))
    platform = FakePlatform()
    app.state.store.accounts.request = platform.request
    app.state.platform_test = platform
    return app


def client_for(app):
    return TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 53000))


def connect(client):
    response = client.get('/api/session')
    assert response.status_code == 200, response.text
    return {'X-CSRF-Token': response.json()['csrf_token']}


def login_member(client, app):
    headers = connect(client)
    result = client.post('/api/accounts/bilibili/qr', headers=headers)
    assert result.status_code == 200, result.text
    body = result.json()
    assert base64.b64decode(body['qr_image'].split(',')[1]).startswith(b'\x89PNG')
    assert 'qrcode_key' not in result.text and 'refresh_token' not in result.text
    app.state.platform_test.code = 0
    result = client.post('/api/accounts/bilibili/poll', headers=headers, json={'flow_id': body['flow_id']})
    assert result.status_code == 200, result.text
    assert result.json()['status'] == 'connected'
    assert 'synthetic-test-only' not in result.text and 'cookies' not in result.text
    return headers


def test_qr_login_and_scoped_secret(app):
    with client_for(app) as client:
        headers = login_member(client, app)
        assert client.get('/api/accounts/bilibili').json()['vip'] is True
        app.state.platform_test.vip = 0
        assert client.post('/api/accounts/bilibili/verify', headers=headers).json()['vip'] is False
        assert client.delete('/api/accounts/bilibili', headers=headers).status_code == 200
        assert client.get('/api/accounts/bilibili').json()['status'] == 'disconnected'
        assert not app.state.store.accounts.accounts
    assert not list(app.state.store.cfg.data_dir.rglob('*cookie*'))


def test_qr_owner_csrf_and_expiration(app):
    with client_for(app) as first, client_for(app) as other:
        headers = connect(first)
        assert first.post('/api/accounts/bilibili/qr').status_code == 403
        assert first.post('/api/accounts/bilibili/qr', headers={**headers,'Origin':'https://evil.test'}).status_code == 403
        flow = first.post('/api/accounts/bilibili/qr', headers=headers).json()['flow_id']
        other_headers = connect(other)
        assert other.post('/api/accounts/bilibili/poll', headers=other_headers, json={'flow_id':flow}).status_code == 410
        result = first.post('/api/accounts/bilibili/poll', headers=headers, json={'flow_id':flow})
        assert result.json()['status'] == 'waiting'
        assert first.post('/api/accounts/bilibili/poll', headers=headers, json={'flow_id':flow}).status_code == 429
        owner = first.cookies.get('clipnest_session')
        app.state.store.accounts.pending[owner].expires = time.time()-1
        assert first.post('/api/accounts/bilibili/poll', headers=headers, json={'flow_id':flow}).status_code == 410


@pytest.mark.parametrize('host,peer', [('evil.test','127.0.0.1'),('127.0.0.1','192.168.1.2'),('127.0.0.1.evil.test','127.0.0.1')])
def test_local_only_blocks_rebinding_and_remote(app,host,peer):
    with TestClient(app,base_url='http://'+host,client=(peer,52000)) as client:
        response = client.get('/api/session')
        assert response.status_code == 403
        # Docker/LAN operators hit this first; the message must say how to configure the service.
        assert 'ENABLE_MEMBER_LOGIN=false' in response.json()['error']['message']


def test_public_deployment_cannot_login(tmp_path):
    app = create_app(Settings(data_dir=tmp_path,member_login=True,public_origin='https://clip.example',access_key='test-access-key-123456'))
    with TestClient(app,base_url='https://clip.example') as client:
        data = client.post('/api/login',json={'key':'test-access-key-123456'}).json()
        assert client.get('/api/health').json()['member_login'] is False
        assert client.post('/api/accounts/bilibili/qr',headers={'X-CSRF-Token':data['csrf_token']}).status_code == 403


def test_cookie_domain_and_protocol_boundaries():
    jar = CookieJar()
    install_cookies(jar,cookies())
    for url,expected in [('https://api.bilibili.com/x',True),('https://evil.test/',False),
                         ('https://bilibili.com.evil.test/',False),('http://api.bilibili.com/x',False),
                         ('https://cdn.bilivideo.com/video',False)]:
        request = Request(url)
        jar.add_cookie_header(request)
        assert bool(request.get_header('Cookie')) is expected
    for change in ({'domain':'.evil.test'}, {'name':'anything'}, {'value':'a\r\nb'}, {'expires':0}):
        with pytest.raises(UserError):
            install_cookies(jar,[{**cookies()[0],**change}])


def test_cancel_inflight_qr_cannot_restore_login():
    async def scenario():
        manager=Accounts(); platform=FakePlatform(); manager.request=platform.request
        flow=await manager.begin('owner'); platform.code=0
        started=asyncio.Event(); release=asyncio.Event()
        async def slow(url,*args,**kwargs):
            if url==NAV:
                started.set(); await release.wait()
            return await platform.request(url,*args,**kwargs)
        manager.request=slow
        task=asyncio.create_task(manager.poll('owner',flow['flow_id']))
        await started.wait(); manager.clear('owner'); release.set()
        with pytest.raises(UserError,match='取消'):
            await task
        assert not manager.accounts
    asyncio.run(scenario())


def test_expired_remote_session_is_removed(app):
    with client_for(app) as client:
        headers=login_member(client,app)
        app.state.platform_test.valid=False
        result=client.post('/api/accounts/bilibili/verify',headers=headers)
        assert result.status_code==401
        assert result.json()['error']['code']=='ACCOUNT_EXPIRED'
        assert not app.state.store.accounts.accounts


def test_same_account_reaches_analyze_and_download(app,monkeypatch):
    payloads=[]
    async def fake_worker(payload,*args,**kwargs):
        payloads.append(payload)
        if payload['mode']=='analyze':
            return build_media(sample_info(),'哔哩哔哩',payload['url'])
        await asyncio.sleep(60)
    monkeypatch.setattr('app.main.run_worker',fake_worker)
    app.state.store.dependencies.update(yt_dlp='test',ffmpeg=True,ffprobe=True)
    with client_for(app) as client:
        headers=login_member(client,app)
        result=client.post('/api/analyze',headers=headers,json={'url':'https://bilibili.com/video/BVtest','use_account':True})
        assert result.status_code==200,result.text
        media=result.json()
        assert media['access_mode']=='member_session'
        assert 'synthetic-test-only' not in result.text and '_account_version' not in result.text
        assert payloads[0]['account_cookies']==cookies() or payloads[0]['account_cookies'][0]['value']=='synthetic-test-only'
        job=client.post('/api/downloads',headers=headers,json={'analysis_id':media['id'], 'option_id':media['options'][0]['id'],'rights_confirmed':True,'download_confirmed':True})
        assert job.status_code==202,job.text
        for _ in range(100):
            if len(payloads)>1:break
            time.sleep(.01)
        assert payloads[1]['account_cookies']==payloads[0]['account_cookies']
        assert client.delete('/api/accounts/bilibili',headers=headers).status_code==200
        assert client.get('/api/downloads/'+job.json()['id']).json()['state']=='cancelled'
        assert media['id'] not in app.state.store.analyses


def test_account_never_sent_to_other_platform(app,monkeypatch):
    async def fake_worker(payload,*args,**kwargs):
        assert 'account_cookies' not in payload
        return build_media(sample_info(),'YouTube',payload['url'])
    monkeypatch.setattr('app.main.run_worker',fake_worker)
    app.state.store.dependencies['yt_dlp']='test'
    with client_for(app) as client:
        headers=login_member(client,app)
        result=client.post('/api/analyze',headers=headers,json={'url':'https://youtube.com/watch?v=test','use_account':True})
        assert result.status_code==200
        assert result.json()['access_mode']=='anonymous'


@pytest.mark.parametrize('url', ['https://evil.test/qrcode/h5/login',
    'https://passport.bilibili.com.evil.test/qrcode/h5/login',
    'http://passport.bilibili.com/qrcode/h5/login',
    'https://name:pass@passport.bilibili.com/qrcode/h5/login',
    'https://account.bilibili.com:8443/h5/account-h5/auth/scan-web'])
def test_untrusted_qr_destination_rejected(url):
    async def scenario():
        manager=Accounts()
        async def response(*args,**kwargs):
            return {'code':0,'data':{'url':url,'qrcode_key':'a'*32}},[]
        manager.request=response
        with pytest.raises(UserError) as error:
            await manager.begin('test')
        assert error.value.code=='ACCOUNT_RESPONSE'
        assert not manager.pending
    asyncio.run(scenario())


def test_replacing_account_invalidates_previous_version():
    manager=Accounts()
    old=Account(cookies(),True,time.time()+3600)
    manager.accounts['owner']=old
    manager.accounts['owner']=Account(cookies(),True,time.time()+3600)
    with pytest.raises(UserError) as error:
        manager.current('owner',old.version)
    assert error.value.code=='ACCOUNT_CHANGED'
