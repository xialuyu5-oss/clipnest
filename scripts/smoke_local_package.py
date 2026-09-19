"""Test an extracted PC archive using an existing dependency environment, offline."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import venv
import zipfile

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dependency-site', type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    if target.exists():
        raise SystemExit('Choose a new output directory; nothing overwritten.')
    target.mkdir(parents=True)
    with zipfile.ZipFile(args.archive) as source:
        for name in source.namelist():
            if not (target / name).resolve().is_relative_to(target):
                raise ValueError('Archive path escapes output')
        source.extractall(target)
    app = target / 'ClipNest'
    venv.create(app / '.venv', with_pip=False)
    marker = hashlib.sha256((app / 'requirements.txt').read_bytes()).hexdigest()
    (app / '.venv/.clipnest-requirements').write_text(marker)
    (app / '.env').write_text('PUBLIC_ORIGIN=https://old.invalid\nCOOKIE_SECURE=true\n'
                            'ACCESS_KEY=not-a-real-secret-fixture\nYTDLP_PROXY=http://127.0.0.1:1\n')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'PYTHONPATH': str(args.dependency_site.resolve())}
    with (target / 'launcher.log').open('w', encoding='utf-8') as log:
        proc = subprocess.Popen([sys.executable, 'start.py', '--local-device', '--no-browser', '--port', str(port)],
                                cwd=app, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=5, trust_env=False) as client:
                deadline = time.monotonic() + 30
                while True:
                    try:
                        health = client.get('/api/health'); health.raise_for_status(); break
                    except httpx.TransportError:
                        if proc.poll() is not None or time.monotonic() > deadline:
                            raise RuntimeError('Local launcher did not start; inspect launcher.log')
                        time.sleep(.2)
                assert health.json()['member_login'] is True
                assert health.json()['access_key_required'] is False
                environment = client.get('/local/environment', headers={'Origin': 'https://xialuyu5-oss.github.io'})
                environment.raise_for_status()
                assert environment.json()['product'] == 'clipnest'
                assert environment.json()['ready'] is True, environment.text
                assert environment.headers['access-control-allow-origin'] == 'https://xialuyu5-oss.github.io'
                assert 'set-cookie' not in environment.headers
                session = client.get('/api/session'); session.raise_for_status()
                headers = {'X-CSRF-Token': session.json()['csrf_token']}
                media_response = client.post('/api/demo', headers=headers); media_response.raise_for_status()
                media = media_response.json()
                denied = client.post('/api/downloads', headers=headers, json={
                    'analysis_id': media['id'], 'option_id': media['options'][0]['id'],
                    'rights_confirmed': True, 'download_confirmed': False})
                assert denied.status_code == 400, denied.text
                response = client.post('/api/downloads', headers=headers, json={
                    'analysis_id': media['id'], 'option_id': media['options'][0]['id'],
                    'rights_confirmed': True, 'download_confirmed': True})
                response.raise_for_status(); job = response.json()
                deadline = time.monotonic() + 20
                while job['state'] not in ('ready', 'error') and time.monotonic() < deadline:
                    time.sleep(.1)
                    job = client.get('/api/downloads/' + job['id']).json()
                assert job['state'] == 'ready', job
                data = client.get(job['file_url']); data.raise_for_status()
                directory = app / 'data/local-device/jobs' / job['id']
                saved = next(p for p in directory.iterdir() if p.suffix == '.mp4')
                assert data.content == saved.read_bytes()
                removed = client.delete('/api/downloads/' + job['id'], headers=headers); removed.raise_for_status()
                assert not directory.exists()
                result = {'passed': True, 'dependency_install_tested': False, 'fixture_only': True,
                          'checks': ['extracted launcher startup', 'old hosting settings overridden',
                                     'explicit download confirmation', 'local media bytes', 'cancel/delete cache'],
                          'download_bytes': len(data.content)}
                (target / 'result.json').write_text(json.dumps(result, indent=2))
                print(json.dumps(result, indent=2))
        finally:
            if os.name == 'nt':
                stopped = subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
                if stopped.returncode and proc.poll() is None:
                    raise RuntimeError(f'Test process cleanup blocked; stop owned process {proc.pid}')
            else:
                proc.terminate()
            proc.wait(timeout=10)


if __name__ == '__main__':
    main()
