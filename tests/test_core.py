import ast
import asyncio
from dataclasses import replace
import io
import json
from pathlib import Path
import re
import socket
import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, ROOT
from app.main import create_app
from app.media import build_media, public_media, quality_height
from app.safety import UserError, is_public_ip, normalize_url, network_guard, friendly_error, public_thumbnail


@pytest.mark.parametrize('url,platform', [
    ('https://youtu.be/abc?si=track', 'YouTube'),
    ('https://www.youtube.com/watch?v=abc&list=test', 'YouTube'),
    ('https://x.com/example/status/123', 'X / Twitter'),
    ('https://twitter.com/example/status/123', 'X / Twitter'),
    ('https://vm.tiktok.com/xyz/', 'TikTok'),
    ('https://www.instagram.com/reel/123/', 'Instagram'),
    ('https://www.facebook.com/watch/?v=123', 'Facebook'),
    ('https://vimeo.com/123', 'Vimeo'),
    ('https://b23.tv/abc', '哔哩哔哩'),
    ('https://dai.ly/x123', 'Dailymotion'),
    ('https://www.reddit.com/r/test/comments/123', 'Reddit'),
    ('https://clips.twitch.tv/example', 'Twitch'),
])
def test_valid_urls(url, platform):
    clean, got = normalize_url(url)
    assert got == platform
    assert clean.startswith('https://')
    assert 'si=track' not in clean


@pytest.mark.parametrize('url', [
    'https://youtube.com.evil.test/watch?v=x', 'https://evilyoutube.com/watch?v=x',
    'https://127.0.0.1/a', 'http://169.254.169.254/latest/meta-data/',
    'https://localhost/a', 'file:///etc/passwd', 'ftp://youtube.com/a',
    'https://youtube.com:9000/watch?v=x', 'https://name:pass@youtube.com/watch?v=x',
    'https://youtube.com/playlist?list=x', 'https://youtube.com/',
    'https://x.com/a https://x.com/b', 'https://youtube.com\\@evil.test/watch',
    'a' * 5000,
])
def test_bad_urls(url):
    with pytest.raises(UserError):
        normalize_url(url)


def test_share_text_and_tracking():
    url, _ = normalize_url('看看这个视频 https://www.youtube.com/watch?v=abc&utm_source=share&si=xyz。')
    assert url == 'https://www.youtube.com/watch?v=abc'


@pytest.mark.parametrize('ip', ['127.0.0.1', '10.0.0.1', '172.16.0.2', '192.168.1.2',
                                '169.254.169.254', '0.0.0.0', '100.64.0.1', '224.0.0.1',
                                '::1', 'fc00::1', 'fe80::1', '::ffff:127.0.0.1', '2002:7f00:1::'])
def test_private_ips(ip):
    assert not is_public_ip(ip)


@pytest.mark.parametrize('ip', ['8.8.8.8', '1.1.1.1', '2606:4700:4700::1111'])
def test_public_ips(ip):
    assert is_public_ip(ip)


def test_socket_guard_checks_redirect_dns(monkeypatch):
    def fake_dns(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]
    monkeypatch.setattr(socket, 'getaddrinfo', fake_dns)
    with network_guard():
        with pytest.raises(OSError, match='private address'):
            socket.getaddrinfo('platform-redirect.example', 443)
        with socket.socket() as sock:
            with pytest.raises(OSError, match='private address'):
                sock.connect(('169.254.169.254', 80))
    assert socket.getaddrinfo is fake_dns


def sample_info():
    return {'title': '<img onerror=alert(1)>', 'uploader': 'A creator', 'duration': 20,
            'formats': [
                {'format_id': '137', 'height': 1080, 'width': 1920, 'fps': 30, 'ext': 'mp4',
                 'vcodec': 'avc1.640028', 'acodec': 'none', 'tbr': 1200, 'filesize': 3000000,
                 'url': 'https://media.example/v.mp4'},
                {'format_id': '18', 'height': 360, 'width': 640, 'fps': 30, 'ext': 'mp4',
                 'vcodec': 'avc1', 'acodec': 'mp4a.40.2', 'filesize': 800000,
                 'url': 'https://media.example/low.mp4'},
                {'format_id': '247', 'height': 720, 'width': 1280, 'fps': 30, 'ext': 'webm',
                 'vcodec': 'vp9', 'acodec': 'none', 'tbr': 900, 'url': 'https://media.example/v.webm'},
                {'format_id': '140', 'ext': 'm4a', 'vcodec': 'none', 'acodec': 'mp4a.40.2', 'abr': 128,
                 'filesize': 300000, 'url': 'https://media.example/a.m4a'},
                {'format_id': '251', 'ext': 'webm', 'vcodec': 'none', 'acodec': 'opus', 'abr': 160,
                 'tbr': 160, 'url': 'https://media.example/a.webm'},
                {'format_id': 'drm', 'height': 2160, 'width': 3840, 'ext': 'mp4', 'vcodec': 'avc1',
                 'acodec': 'none', 'has_drm': True, 'url': 'https://media.example/drm'},
            ]}


def test_real_formats_only_and_merging():
    result = build_media(sample_info(), 'YouTube', 'https://youtube.com/watch?v=abc')
    assert [o['height'] for o in result['options']] == [1080, 720, 360]
    top = result['options'][0]
    assert top['_selector'] == '137+140'
    assert top['needs_merge'] and top['has_audio']
    assert top['filesize'] == 3300000
    assert not top['approximate']
    assert result['options'][1]['container'] == 'webm'
    assert result['options'][1]['_selector'] == '247+251'
    assert all('_selector' not in opt for opt in public_media(result)['options'])
    assert not any(o['height'] == 2160 for o in result['options'])


def test_portrait_short_edge():
    assert quality_height({'height': 1920, 'width': 1080}) == 1080


def test_completed_hls_replay_duration_and_size():
    import io
    from types import SimpleNamespace
    from app.worker import fill_replay_duration

    playlist = b'#EXTM3U\n#EXTINF:10.5,\na.ts\n#EXTINF:9.5,\nb.ts\n#EXT-X-ENDLIST\n'
    source = sample_info()
    source.update(duration=None, was_live=True)
    source['formats'][0]['protocol'] = 'm3u8_native'
    del source['formats'][0]['filesize']
    fill_replay_duration(SimpleNamespace(urlopen=lambda _: io.BytesIO(playlist)), source)
    assert source['duration'] == 20
    option = build_media(source, 'X', 'https://x.com/i/broadcasts/example')['options'][0]
    assert option['filesize'] == 3_300_000 and option['approximate']
    source['duration'] = None
    fill_replay_duration(SimpleNamespace(urlopen=lambda _: io.BytesIO(playlist.replace(b'#EXT-X-ENDLIST', b''))), source)
    assert source['duration'] is None


def test_audio_unknown_and_same_quality_preference():
    base = {'height': 720, 'width': 1280, 'ext': 'mp4', 'vcodec': 'avc1',
            'url': 'https://media.example/video.mp4'}
    info = {'formats': [dict(base, format_id='unknown'),
                        dict(base, format_id='silent', acodec='none'),
                        dict(base, format_id='audible', acodec='aac')]}
    options = build_media(info, 'X', 'https://x.com/test')['options']
    assert [o['has_audio'] for o in options] == [True, None, False]
    info['formats'].append({'format_id': 'audio', 'vcodec': 'none', 'acodec': 'aac',
                            'ext': 'm4a', 'url': 'https://media.example/audio.m4a'})
    options = build_media(info, 'X', 'https://x.com/test')['options']
    unknown = next(o for o in options if o['has_audio'] is None)
    assert unknown['_selector'] == 'unknown' and not unknown['needs_merge']
    source = sample_info()
    source['formats'][3]['acodec'] = None
    top = build_media(source, 'X', 'https://x.com/test')['options'][0]
    assert top['_selector'] == '137+140' and top['has_audio'] and top['needs_merge']


def test_metadata_probe_reads_sample_and_preserves_failed_unknowns():
    import io
    from app.probe import fill_format_metadata

    class Response(io.BytesIO):
        url = 'https://media.example/sample.mp4'

    class Source:
        def urlopen(self, request):
            assert request.headers['Range'].startswith('bytes=0-')
            if request.url.endswith('unavailable.mp4'):
                raise OSError('Sample unavailable')
            return Response((ROOT / 'web/assets/demo-480.mp4').read_bytes())

    info = {'formats': [
        {'format_id': 'ok', 'url': 'https://media.example/sample.mp4', 'ext': 'mp4', 'height': 480},
        {'format_id': 'fail', 'url': 'https://media.example/unavailable.mp4', 'ext': 'mp4', 'height': 360},
    ]}
    fill_format_metadata(Source(), info)
    options = build_media(info, 'X', 'https://x.com/test')['options']
    assert options[0]['fps'] == 24 and options[0]['codec'] == 'h264'
    assert options[0]['audio_codec'] == 'aac' and options[0]['has_audio'] is True
    assert options[1]['fps'] is None and options[1]['has_audio'] is None


@pytest.mark.parametrize('extra,code', [
    ({'is_live': True}, 'LIVE_NOT_SUPPORTED'),
    ({'live_status': 'is_upcoming'}, 'LIVE_NOT_SUPPORTED'),
    ({'_type': 'playlist', 'entries': []}, 'PLAYLIST_NOT_SUPPORTED'),
    ({'has_drm': True}, 'DRM_PROTECTED'),
])
def test_disallowed_media(extra, code):
    info = sample_info(); info.update(extra)
    with pytest.raises(UserError) as caught:
        build_media(info, 'YouTube', 'https://youtube.com/watch?v=abc')
    assert caught.value.code == code


def test_reject_injected_format_ids():
    info = sample_info()
    info['formats'][0]['format_id'] = 'best/../../secret'
    result = build_media(info, 'YouTube', 'https://youtube.com/watch?v=abc')
    assert not any(o['height'] == 1080 for o in result['options'])


def test_safe_thumbnails_and_error_mapping():
    assert public_thumbnail('https://i.ytimg.com/vi/test/default.jpg')
    assert public_thumbnail('http://i.ytimg.com/a.jpg') is None
    assert public_thumbnail('https://127.0.0.1/a.jpg') is None
    assert public_thumbnail('https://i.ytimg.com.evil.test/a.jpg') is None
    assert friendly_error('Please sign in to confirm you are not a bot')[0] == 'AUTH_REQUIRED'
    assert friendly_error('HTTP Error 429')[0] == 'RATE_LIMITED'
    assert friendly_error('Temporary failure in name resolution')[0] == 'NETWORK_ERROR'


def test_ffmpeg_errors_are_not_all_reported_as_missing_ffmpeg():
    assert friendly_error('ffmpeg not found. Please install or provide the path using --ffmpeg-location')[0] == 'MISSING_FFMPEG'
    assert friendly_error('You have requested merging of multiple formats but ffmpeg is not installed.')[0] == 'MISSING_FFMPEG'
    assert friendly_error('ERROR: Postprocessing: ffmpeg exited with code 1')[0] == 'MERGE_FAILED'
    assert friendly_error('ERROR: Postprocessing: Conversion failed!')[0] == 'MERGE_FAILED'
    assert friendly_error('ERROR: No module named brotli')[0] == 'MISSING_DEPENDENCY'


def test_short_link_expansion_is_guarded_and_validated():
    from yt_dlp.networking.exceptions import TransportError
    from app.worker import resolve_short_link

    class Source:
        def __init__(self, final=None, error=None):
            self.final, self.error, self.requests = final, error, []

        def urlopen(self, request):
            self.requests.append(request.url)
            if self.error:
                raise self.error
            return type('R', (io.BytesIO,), {'url': self.final})(b'<html>')

    plain = Source()
    assert resolve_short_link(plain, 'https://www.bilibili.com/video/BV1xx411c7mD?share_source=copy_web') \
        == ('https://www.bilibili.com/video/BV1xx411c7mD?share_source=copy_web', '哔哩哔哩')
    assert plain.requests == [], 'links a real extractor claims must not trigger extra requests'
    ok = Source('https://www.bilibili.com/video/BV1xx411c7mD?p=1&utm_source=share')
    assert resolve_short_link(ok, '看这个 https://b23.tv/abc123 ') == ('https://www.bilibili.com/video/BV1xx411c7mD?p=1', '哔哩哔哩')
    assert ok.requests == ['https://b23.tv/abc123']
    fb = Source('https://www.facebook.com/watch/?v=123')
    assert resolve_short_link(fb, 'https://fb.watch/abc/')[1] == 'Facebook'
    for source, code in [(Source('https://evil.example/landing'), 'UNSUPPORTED_SITE'),
                         (Source('https://127.0.0.1/admin'), 'UNSUPPORTED_SITE'),
                         (Source('https://b23.tv/still-short'), 'SHORT_LINK_FAILED'),
                         (Source(error=TransportError('blocked')), 'SHORT_LINK_FAILED')]:
        with pytest.raises(UserError) as caught:
            resolve_short_link(source, 'https://b23.tv/abc123')
        assert caught.value.code == code


def test_analyze_expands_short_link_before_extraction(monkeypatch):
    import sys
    from types import SimpleNamespace
    from contextlib import nullcontext
    import yt_dlp.networking.exceptions  # noqa: F401  (real submodules must be loaded before yt_dlp is faked)
    from app.worker import run

    seen = {}

    class FakeYoutubeDL:
        def __init__(self, options):
            assert options['skip_download'] is True

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def urlopen(self, request):
            seen['redirect'] = request.url
            return type('R', (io.BytesIO,), {'url': 'https://www.bilibili.com/video/BV1xx411c7mD'})(b'')

        def extract_info(self, url, download):
            seen['extract'] = url
            return {'title': 'expanded', 'duration': 5, 'formats': [
                {'format_id': 'f', 'url': 'https://upos.example/v.mp4', 'ext': 'mp4', 'height': 720, 'width': 1280,
                 'vcodec': 'avc1', 'acodec': 'mp4a.40.2', 'fps': 30}]}

    monkeypatch.setitem(sys.modules, 'yt_dlp', SimpleNamespace(YoutubeDL=FakeYoutubeDL))
    monkeypatch.setattr('app.worker.network_guard', lambda *args: nullcontext())
    media = run({'mode': 'analyze', 'url': 'https://b23.tv/abc123', 'proxy': '', 'probe_seconds': 0})
    assert seen == {'redirect': 'https://b23.tv/abc123', 'extract': 'https://www.bilibili.com/video/BV1xx411c7mD'}
    assert media['url'] == 'https://www.bilibili.com/video/BV1xx411c7mD' and media['platform'] == '哔哩哔哩'


def test_worker_environment_strips_secrets_and_marks_worker(monkeypatch):
    from app.process import worker_environment
    monkeypatch.setenv('ACCESS_KEY', 'super-secret-value-123456')
    monkeypatch.setenv('PUBLIC_ORIGIN', 'https://clips.example.com')
    monkeypatch.setenv('YTDLP_PROXY', 'http://127.0.0.1:7897')
    env = worker_environment()
    assert 'ACCESS_KEY' not in env and 'PUBLIC_ORIGIN' not in env
    assert env['CLIPNEST_WORKER'] == '1' and env['YTDLP_PROXY'] == 'http://127.0.0.1:7897'


def test_worker_processes_do_not_reload_dotenv(monkeypatch):
    import importlib
    import dotenv
    import app.config as config
    calls = []
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda *args, **kwargs: calls.append(args))
    try:
        monkeypatch.setenv('CLIPNEST_WORKER', '1')
        importlib.reload(config)
        assert calls == [], 'a worker must not read .env again (it would resurrect ACCESS_KEY)'
        monkeypatch.delenv('CLIPNEST_WORKER')
        importlib.reload(config)
        assert len(calls) == 1 and calls[0][0] == ROOT / '.env'
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_access_key_must_be_printable_ascii():
    Settings(access_key='correct-password-123456').validate()
    for key in ('密码密码密码密码密码密码密码密码', 'tab\tinside-the-key-1234', 'ñoño-accent-key-12345'):
        with pytest.raises(RuntimeError, match='ASCII'):
            Settings(access_key=key).validate()
    with pytest.raises(RuntimeError, match='LOG_LEVEL'):
        Settings(log_level='verbose').validate()


def test_non_ascii_secrets_are_rejected_not_crashed(tmp_path):
    app = create_app(Settings(member_login=False, data_dir=tmp_path, access_key='correct-password-123456'))
    with TestClient(app) as client:
        response = client.post('/api/login', json={'key': '密码密码密码密码密码密码密码密码'})
        assert response.status_code == 401 and response.json()['error']['code'] == 'UNAUTHORIZED'
        assert client.post('/api/login', json={'key': 'correct-password-123456'}).status_code == 200
        response = client.post('/api/demo', headers={b'X-CSRF-Token': b'caf\xe9-\xff'})
        assert response.status_code == 403 and response.json()['error']['code'] == 'CSRF_FAILED'


def test_health_redetects_dependencies(app):
    import shutil
    with TestClient(app) as client:
        app.state.store.dependencies['ffprobe'] = not shutil.which('ffprobe')
        assert client.get('/api/health').json()['dependencies']['ffprobe'] is bool(shutil.which('ffprobe'))
        assert app.state.store.dependencies['ffprobe'] is bool(shutil.which('ffprobe'))
        assert client.get('/api/health').json()['version'] == '1.3.1'


def test_periodic_cleanup_survives_an_exception(app, monkeypatch):
    store = app.state.store
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError('transient')

    monkeypatch.setattr(store, 'sweep_once', flaky)
    real_sleep = asyncio.sleep
    monkeypatch.setattr('app.main.asyncio.sleep', lambda _: real_sleep(0))

    async def scenario():
        task = asyncio.create_task(store.sweep())
        for _ in range(50):
            await real_sleep(0)
            if len(calls) >= 2:
                break
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    asyncio.run(scenario())
    assert len(calls) >= 2, 'cleanup loop must keep running after one failure'


@pytest.fixture
def app(tmp_path):
    cfg = Settings(member_login=False, data_dir=tmp_path, access_key='', public_origin='', secure_cookie=False,
                   min_free_mb=50, proxy='')
    return create_app(cfg)


def session(client):
    result = client.get('/api/session')
    assert result.status_code == 200
    return {'X-CSRF-Token': result.json()['csrf_token']}


def demo(client, headers):
    response = client.post('/api/demo', headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_csrf_and_origin(app):
    with TestClient(app) as client:
        headers = session(client)
        assert client.post('/api/demo').status_code == 403
        assert client.post('/api/demo', headers={**headers, 'Origin': 'https://evil.example'}).status_code == 403
        assert client.post('/api/demo', headers={**headers, 'Sec-Fetch-Site': 'cross-site'}).status_code == 403
        assert client.post('/api/analyze', headers=headers, json={'url': 'https://127.0.0.1/a'}).status_code == 400
        assert client.get('/').headers['X-Frame-Options'] == 'DENY'
        assert 'HttpOnly' in client.get('/api/session').headers['set-cookie']


def test_access_key_required(tmp_path):
    app = create_app(Settings(member_login=False, data_dir=tmp_path, access_key='correct-password-123456', public_origin=''))
    with TestClient(app) as client:
        assert client.get('/api/session').status_code == 401
        assert client.get('/api/downloads').status_code == 401
        assert client.post('/api/login', json={'key': 'incorrect'}).status_code == 401
        response = client.post('/api/login', json={'key': 'correct-password-123456'})
        assert response.status_code == 200
        csrf = response.json()['csrf_token']
        assert client.get('/api/downloads').status_code == 200
        assert client.post('/api/logout', headers={'X-CSRF-Token': csrf}).status_code == 200
        assert client.get('/api/downloads').status_code == 401


def test_public_origin_requires_password(tmp_path):
    app = create_app(Settings(member_login=False, data_dir=tmp_path, access_key='', public_origin='https://clips.example.com'))
    with pytest.raises(RuntimeError, match='ACCESS_KEY'):
        with TestClient(app):
            pass


@pytest.mark.parametrize('height', [1080, 720, 480])
def test_real_demo_download_integrity_range_and_cleanup(app, height):
    with TestClient(app) as client:
        headers = session(client)
        media = demo(client, headers)
        opt = next(o for o in media['options'] if o['height'] == height)
        body = {'analysis_id': media['id'], 'option_id': opt['id'], 'rights_confirmed': True, 'download_confirmed': True}
        reject = client.post('/api/downloads', headers=headers, json={k: v for k, v in body.items() if k != 'download_confirmed'})
        assert reject.status_code == 400
        assert reject.json()['error']['code'] == 'DOWNLOAD_CONFIRMATION_REQUIRED'
        assert not app.state.store.jobs
        reject = client.post('/api/downloads', headers=headers, json={**body, 'rights_confirmed': False})
        assert reject.status_code == 400
        reject = client.post('/api/downloads', headers=headers, json={**body, 'option_id': 'best'})
        assert reject.status_code == 400
        response = client.post('/api/downloads', headers=headers, json=body)
        assert response.status_code == 202, response.text
        job_id = response.json()['id']
        for _ in range(120):
            job = client.get('/api/downloads/' + job_id).json()
            if job['state'] not in ('queued', 'downloading', 'processing'):
                break
            time.sleep(0.05)
        assert job['state'] == 'ready', job
        assert job['actual']['height'] == height
        assert job['actual']['width'] == opt['width']
        assert job['actual']['has_audio']
        full = client.get(job['file_url'])
        assert full.status_code == 200
        assert full.headers['content-type'] == 'video/mp4'
        assert 'attachment' in full.headers['content-disposition']
        assert full.content[4:8] == b'ftyp'
        assert len(full.content) == opt['filesize']
        partial = client.get(job['file_url'], headers={'Range': 'bytes=0-15'})
        assert partial.status_code == 206
        assert partial.content == full.content[:16]
        owner_cookie = client.cookies.get('clipnest_session')
        client.cookies.clear(); session(client)
        assert client.get('/api/downloads/' + job_id).status_code == 404
        assert client.get(job['file_url']).status_code == 404
        client.cookies.clear(); client.cookies.set('clipnest_session', owner_cookie)
        assert client.delete('/api/downloads/' + job_id, headers=headers).status_code == 200
        assert client.get(job['file_url']).status_code == 404
        assert not (app.state.store.jobs_dir / job_id).exists()


def test_analyze_result_has_no_secrets(app, monkeypatch):
    async def fake_worker(payload, *args, **kwargs):
        assert payload['mode'] == 'analyze'
        return build_media(sample_info(), 'YouTube', payload['url'])
    monkeypatch.setattr('app.main.run_worker', fake_worker)
    app.state.store.dependencies['yt_dlp'] = 'test-double-not-live'
    with TestClient(app) as client:
        headers = session(client)
        result = client.post('/api/analyze', headers=headers, json={'url': 'https://youtube.com/watch?v=abc'})
        assert result.status_code == 200
        assert '_selector' not in result.text
        assert '_owner' not in result.text
        assert 'media.example' not in result.text
        assert result.json()['title'] == '<img onerror=alert(1)>'  # UI must render as text.


@pytest.mark.parametrize('filesize', [None, 25 * 1024**3])
def test_confirmed_large_or_unknown_download_can_be_cancelled(app, monkeypatch, filesize):
    info = sample_info()
    info['duration'] = 99999
    assert build_media(info, 'X', 'https://x.com/test')['duration'] == 99999

    async def slow_worker(payload, timeout, *args, **kwargs):
        assert timeout is None
        await asyncio.sleep(60)
    monkeypatch.setattr('app.main.run_worker', slow_worker)
    with TestClient(app) as client:
        headers = session(client); media = demo(client, headers)
        app.state.store.analyses[media['id']]['options'][0]['filesize'] = filesize
        app.state.store.analyses[media['id']]['duration'] = 99999
        body = {'analysis_id': media['id'], 'option_id': media['options'][0]['id'], 'rights_confirmed': True, 'download_confirmed': True}
        response = client.post('/api/downloads', headers=headers, json=body)
        assert response.status_code == 202, response.text
        job = response.json()
        assert client.delete('/api/downloads/' + job['id'], headers=headers).status_code == 200
        assert not (app.state.store.jobs_dir / job['id']).exists()
        assert client.get('/api/downloads/' + job['id']).status_code == 404


def test_expired_analysis(app):
    with TestClient(app) as client:
        headers = session(client); media = demo(client, headers)
        app.state.store.analyses[media['id']]['_expires'] = time.time() - 1
        response = client.post('/api/downloads', headers=headers, json={
            'analysis_id': media['id'], 'option_id': media['options'][0]['id'], 'rights_confirmed': True, 'download_confirmed': True})
        assert response.status_code == 410


def test_per_session_rate_limit(app):
    with TestClient(app) as client:
        headers = session(client)
        for _ in range(10):
            assert client.post('/api/demo', headers=headers).status_code == 200
        assert client.post('/api/demo', headers=headers).status_code == 429


@pytest.mark.parametrize('has_output', [True, False])
def test_worker_one_download_limit_validates_output(tmp_path, monkeypatch, has_output):
    """Regression: yt-dlp's one-file cap can raise after a successful download.

    Fake extractor only; not a claim that a real platform was downloaded.
    """
    import shutil
    import sys
    from types import SimpleNamespace
    from contextlib import nullcontext
    from app.worker import run

    class MaxDownloadsReached(Exception):
        pass

    class FakeYoutubeDL:
        def __init__(self, options):
            assert options['max_downloads'] == 1
            assert 'max_filesize' not in options
            assert options['match_filter']({'duration': 99999}) is None
            assert options['format'] == 'demo-test-format'
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download):
            assert download is True
            if has_output:
                shutil.copyfile(ROOT / 'web/assets/demo-480.mp4', tmp_path / 'media.mp4')
            raise MaxDownloadsReached()

    fake = SimpleNamespace(YoutubeDL=FakeYoutubeDL,
                           utils=SimpleNamespace(MaxDownloadsReached=MaxDownloadsReached))
    monkeypatch.setitem(sys.modules, 'yt_dlp', fake)
    monkeypatch.setattr('app.worker.network_guard', lambda *args: nullcontext())
    payload = {'mode': 'download', 'url': 'https://youtube.com/watch?v=demo-test',
               'directory': str(tmp_path), 'option': {'_selector': 'demo-test-format',
               'container': 'mp4', 'height': 480, 'has_audio': True}}
    if has_output:
        result = run(payload)
        assert result['actual']['height'] == 480
        assert result['actual']['has_audio'] is True
    else:
        with pytest.raises(UserError) as exc:
            run(payload)
        assert exc.value.code == 'MERGE_FAILED'


CODE_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]{3,}$')


def backend_error_codes():
    """Every error code the backend can send to the browser, collected from the source with ast.

    Covers UserError(message, 'CODE') calls (including event.get('code', 'DEFAULT') defaults),
    friendly_error() rule tuples and its final return, and tuple assignments to job.error_code.
    """
    codes = set()

    def constant(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and CODE_PATTERN.match(node.value):
            codes.add(node.value)
        elif isinstance(node, ast.Call) and getattr(node.func, 'attr', None) == 'get' and len(node.args) == 2:
            constant(node.args[1])

    for path in sorted((ROOT / 'app').glob('*.py')):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'UserError':
                for arg in node.args[1:2] + [k.value for k in node.keywords if k.arg == 'code']:
                    constant(arg)
            elif isinstance(node, ast.Tuple) and len(node.elts) == 3:
                constant(node.elts[1])  # friendly_error rules: (needles, 'CODE', message)
            elif isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple) and node.value.elts:
                constant(node.value.elts[0])  # friendly_error fallback: return 'CODE', message
            elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Tuple):
                for target in node.targets:
                    if isinstance(target, ast.Tuple):
                        for index, element in enumerate(target.elts):
                            if getattr(element, 'attr', None) == 'error_code' and index < len(node.value.elts):
                                constant(node.value.elts[index])
    return codes


def test_frontend_error_map_covers_backend_codes():
    # v1.2.0 replaced server error messages with code-based localized texts; any backend code
    # missing from web/app.js errorMessage() falls back to a misleading "check your input" hint.
    codes = backend_error_codes()
    assert {'EXTRACTION_FAILED', 'WORKER_ERROR', 'SERVER_ERROR', 'LOCAL_ONLY', 'UNSUPPORTED_SITE'} <= codes
    assert len(codes) > 40, codes
    app_js = (ROOT / 'web/app.js').read_text(encoding='utf-8')
    block = app_js[app_js.index('function errorMessage('):app_js.index('function el(')]
    mapped = set(re.findall(r'^\s+([A-Z][A-Z0-9_]+):', block, re.M))
    assert codes <= mapped, f'backend codes without a frontend message: {sorted(codes - mapped)}'
