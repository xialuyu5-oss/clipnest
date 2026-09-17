"""Download lifecycle tests, using isolated local data rather than user tasks."""
import asyncio
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.safety import UserError


def connect(client):
    result = client.get('/api/session')
    assert result.status_code == 200, result.text
    return {'X-CSRF-Token': result.json()['csrf_token']}


def start(client, headers):
    media = client.post('/api/demo', headers=headers).json()
    response = client.post('/api/downloads', headers=headers, json={
        'analysis_id': media['id'], 'option_id': media['options'][0]['id'],
        'rights_confirmed': True, 'download_confirmed': True})
    assert response.status_code == 202, response.text
    return response.json()['id']


def wait_for(client, job_id, predicate):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        job = client.get('/api/downloads/' + job_id).json()
        if predicate(job):
            return job
        time.sleep(.02)
    pytest.fail(f'Timed out: {job}')


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    cfg = Settings(data_dir=tmp_path, member_login=False, min_free_mb=50)
    app = create_app(cfg)
    attempts = []

    async def transfer(payload, timeout, progress, disk_check):
        part = Path(payload['directory']) / 'media.mp4.part'
        saved = part.read_bytes() if part.exists() else b''
        attempts.append(saved)
        part.write_bytes(saved + b'chunk')
        progress({'state': 'downloading', 'downloaded': part.stat().st_size,
                  'progress': 50, 'speed': 100, 'eta': 12, 'total': 10})
        if not saved:
            await asyncio.sleep(60)
        target = part.with_suffix('')
        part.rename(target)
        return {'path': str(target), 'actual': {'filesize': 10, 'container': 'mp4'}}

    monkeypatch.setattr('app.main.run_worker', transfer)
    return app, cfg, attempts


def test_pause_resume_keeps_bytes_cancel_deletes(lifecycle):
    app, cfg, attempts = lifecycle
    with TestClient(app) as client:
        headers = connect(client)
        job_id = start(client, headers)
        base = '/api/downloads/' + job_id
        wait_for(client, job_id, lambda j: j['downloaded'] > 0)
        assert client.post(base + '/pause').status_code == 403
        paused = client.post(base + '/pause', headers=headers)
        assert paused.json()['state'] == 'paused'
        assert (cfg.data_dir / 'jobs' / job_id / 'media.mp4.part').read_bytes() == b'chunk'
        assert client.post(base + '/pause', headers=headers).status_code == 200
        assert client.post(base + '/resume', headers=headers).status_code == 202
        ready = wait_for(client, job_id, lambda j: j['state'] == 'ready')
        assert attempts == [b'', b'chunk']
        assert ready['expires_at'] is None
        assert client.get(ready['file_url']).content == b'chunkchunk'
        assert client.delete(base, headers=headers).status_code == 200
        assert not (cfg.data_dir / 'jobs' / job_id).exists()


def test_restart_retains_paused_and_ready_without_credentials(lifecycle):
    app, cfg, attempts = lifecycle
    with TestClient(app) as client:
        headers = connect(client)
        cookie = client.cookies.get('clipnest_session')
        job_id = start(client, headers)
        wait_for(client, job_id, lambda j: j['downloaded'] > 0)
    manifest = cfg.data_dir / 'jobs' / job_id / 'job.json'
    assert cookie not in manifest.read_text(encoding='utf-8')
    assert json.loads(manifest.read_text(encoding='utf-8'))['state'] == 'paused'
    with TestClient(create_app(cfg)) as client:
        connect(client)
        assert not client.get('/api/downloads').json()['items']
        client.cookies.clear()
        client.cookies.set('clipnest_session', cookie)
        headers = connect(client)
        assert client.get('/api/downloads').json()['items'][0]['state'] == 'paused'
        assert client.post(f'/api/downloads/{job_id}/resume', headers=headers).status_code == 202
        ready = wait_for(client, job_id, lambda j: j['state'] == 'ready')
    restored = create_app(cfg)
    with TestClient(restored) as client:
        client.cookies.set('clipnest_session', cookie)
        connect(client)
        # Even an old legacy expiry field cannot remove persistent downloads.
        restored.state.store.jobs[job_id].expires_at = time.time() - 86400
        restored.state.store.sweep_once()
        assert client.get(ready['file_url']).content == b'chunkchunk'


def test_cancel_paused_and_queued_jobs(lifecycle):
    app, cfg, _ = lifecycle
    with TestClient(app) as client:
        headers = connect(client)
        job_id = start(client, headers)
        wait_for(client, job_id, lambda j: j['downloaded'] > 0)
        assert client.post(f'/api/downloads/{job_id}/pause', headers=headers).status_code == 200
        assert client.delete(f'/api/downloads/{job_id}', headers=headers).status_code == 200
        assert not (cfg.data_dir / 'jobs' / job_id).exists()
        other = start(client, headers)
        assert client.delete(f'/api/downloads/{other}', headers=headers).status_code == 200
        assert not (cfg.data_dir / 'jobs' / other).exists()


def test_network_error_preserves_checkpoint(lifecycle, monkeypatch):
    app, cfg, _ = lifecycle

    async def fail(payload, *args):
        (Path(payload['directory']) / 'media.mp4.part').write_bytes(b'partial')
        raise UserError('Network unavailable', 'NETWORK_ERROR')

    monkeypatch.setattr('app.main.run_worker', fail)
    with TestClient(app) as client:
        headers = connect(client)
        job_id = start(client, headers)
        wait_for(client, job_id, lambda j: j['state'] == 'error')
        assert (cfg.data_dir / 'jobs' / job_id / 'media.mp4.part').read_bytes() == b'partial'


def test_restart_still_requires_instance_login(tmp_path):
    cfg = Settings(data_dir=tmp_path, member_login=False, access_key='synthetic-test-password')
    with TestClient(create_app(cfg)) as client:
        assert client.post('/api/login', json={'key': cfg.access_key}).status_code == 200
        cookie = client.cookies.get('clipnest_session')
    with TestClient(create_app(cfg)) as client:
        client.cookies.set('clipnest_session', cookie)
        assert client.get('/api/session').status_code == 401
        assert client.get('/api/downloads').status_code == 401
        assert client.post('/api/login', json={'key': cfg.access_key}).status_code == 200
        assert client.cookies.get('clipnest_session', domain='testserver.local') == cookie
