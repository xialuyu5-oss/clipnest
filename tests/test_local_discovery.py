from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ORIGIN = 'https://xialuyu5-oss.github.io'


@pytest.mark.parametrize('origin', ['*', 'http://public.example', 'https://site.example/path', 'https://user:pass@site.example'])
def test_website_origin_configuration_is_exact_https(origin):
    with pytest.raises(RuntimeError, match='LOCAL_SITE_ORIGIN'):
        Settings(local_site_origin=origin).validate()


def client_for(tmp_path, **changes):
    cfg = replace(Settings(), data_dir=tmp_path, local_device=True,
                  member_login=True, public_origin='', access_key='', **changes)
    return TestClient(create_app(cfg), base_url='http://127.0.0.1:8000', client=('127.0.0.1', 51000))


@pytest.mark.parametrize('missing', [None, 'ffprobe', 'node', 'yt_dlp', 'ejs'])
def test_reports_verified_components_without_private_data(tmp_path, monkeypatch, missing):
    calls = []
    def report():
        calls.append(True)
        return {'checks': [{'name': name, 'ready': name not in (missing, 'deno'),
                            'detail': 'PRIVATE PATH OR VERSION'}
                           for name in ['Python', 'ffmpeg', 'ffprobe', 'deno', 'node']]}
    monkeypatch.setattr('app.main.local_environment_report', report)
    monkeypatch.setattr('app.main.dependency_status', lambda: {'yt_dlp': missing != 'yt_dlp', 'ejs': missing != 'ejs'})
    with client_for(tmp_path) as client:
        response = client.get('/local/environment', headers={'Origin': ORIGIN})
        assert response.status_code == 200
        assert response.headers['access-control-allow-origin'] == ORIGIN
        assert 'access-control-allow-credentials' not in response.headers
        assert 'set-cookie' not in response.headers
        assert response.json()['ready'] is (missing is None)
        assert set(response.json()) == {'product', 'protocol', 'ready', 'checks'}
        assert 'PRIVATE' not in response.text
        for check in response.json()['checks']:
            assert set(check) == {'id', 'ready'}
        client.get('/local/environment', headers={'Origin': ORIGIN})
        assert len(calls) == 1
        assert not client.app.state.store.sessions


def test_discovery_does_not_open_task_or_account_api(tmp_path):
    with client_for(tmp_path) as client:
        headers = {'Origin': ORIGIN}
        response = client.options('/local/environment', headers={**headers, 'Access-Control-Request-Method': 'GET',
                                  'Access-Control-Request-Private-Network': 'true'})
        assert response.status_code == 200
        assert response.headers['access-control-allow-methods'] == 'GET'
        assert response.headers['access-control-allow-private-network'] == 'true'
        assert client.options('/local/environment', headers={**headers, 'Access-Control-Request-Method': 'POST'}).status_code == 403
        for path in ['/api/session', '/api/downloads', '/api/accounts/bilibili']:
            response = client.get(path, headers=headers)
            assert 'access-control-allow-origin' not in response.headers
        response = client.post('/api/analyze', headers=headers, json={'url': 'https://youtu.be/example'})
        assert response.status_code == 403
        assert response.json()['error']['code'] == 'CROSS_ORIGIN'


@pytest.mark.parametrize('origin', ['https://attacker.example', 'null', 'http://127.0.0.1.evil.test',
                                    'https://xialuyu5-oss.github.io.evil.test'])
def test_other_origins_are_rejected(tmp_path, origin):
    with client_for(tmp_path) as client:
        response = client.get('/local/environment', headers={'Origin': origin})
        assert response.status_code == 403
        assert 'access-control-allow-origin' not in response.headers


def test_disabled_in_normal_hosting_and_rebinding_blocked(tmp_path):
    cfg = replace(Settings(), data_dir=tmp_path, local_device=False, member_login=False)
    with TestClient(create_app(cfg)) as client:
        assert client.get('/local/environment').status_code == 404
    with client_for(tmp_path) as client:
        assert client.get('/local/environment', headers={'Host': 'evil.example', 'Origin': ORIGIN}).status_code == 403
    with TestClient(create_app(replace(cfg, local_device=True)), base_url='http://127.0.0.1', client=('192.168.1.4', 5000)) as client:
        assert client.get('/local/environment').status_code == 403
