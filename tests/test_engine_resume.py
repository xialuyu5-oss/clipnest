"""Real yt-dlp / FFmpeg restart tests with a throttled loopback HTTP fixture."""
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

import pytest

from app.config import ROOT


@pytest.mark.parametrize('protocol', ['http', 'm3u8_native'])
def test_real_engine_reuses_http_bytes_and_hls_fragments(tmp_path, protocol):
    source = ROOT / 'web/assets/demo-480.mp4'
    data = source.read_bytes()
    requests = []
    hls = tmp_path / 'hls'
    hls.mkdir()
    if protocol == 'm3u8_native':
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(source), '-c:v', 'libx264',
                        '-preset', 'ultrafast', '-g', '24', '-sc_threshold', '0',
                        '-c:a', 'aac', '-hls_time', '1', '-hls_list_size', '0',
                        str(hls / 'fixture.m3u8')], check=True, capture_output=True, timeout=30)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            content = data if self.path == '/fixture.mp4' else (hls / Path(self.path).name).read_bytes()
            start = int(re.search(r'bytes=(\d+)-', self.headers.get('Range', 'bytes=0-')).group(1))
            requests.append((self.path, start))
            self.send_response(206 if start else 200)
            self.send_header('Content-Length', str(len(content) - start))
            self.send_header('Content-Type', 'application/vnd.apple.mpegurl' if self.path.endswith('.m3u8') else 'video/mp4')
            if start:
                self.send_header('Content-Range', f'bytes {start}-{len(content)-1}/{len(content)}')
            self.end_headers()
            try:
                for offset in range(start, len(content), 2048):
                    self.wfile.write(content[offset:offset + 2048])
                    self.wfile.flush()
                    if not self.path.endswith('.m3u8'):
                        time.sleep(.015)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    directory = tmp_path / 'download'
    directory.mkdir()
    suffix = 'fixture.mp4' if protocol == 'http' else 'fixture.m3u8'
    payload = {'mode': 'download', 'url': f'http://127.0.0.1:{server.server_port}/{suffix}',
               'proxy': '', 'directory': str(directory), 'protocol': protocol,
               'option': {'_selector': 'fixture', 'container': 'mp4', 'height': 480, 'has_audio': True}}

    def launch():
        proc = subprocess.Popen([sys.executable, str(ROOT / 'tests/fixture_resume_worker.py')],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        proc.stdin.write((json.dumps(payload) + '\n').encode())
        proc.stdin.close()
        return proc

    first = None
    try:
        first = launch()
        checkpoint = None
        for raw in iter(first.stdout.readline, b''):
            event = json.loads(raw)
            if event.get('type') != 'progress':
                continue
            if protocol == 'http' and event.get('downloaded', 0) >= 8192:
                break
            if protocol == 'm3u8_native':
                sidecar = directory / 'media.mp4.ytdl'
                if sidecar.exists():
                    try:
                        checkpoint = json.loads(sidecar.read_text())['downloader']['current_fragment']['index']
                    except (ValueError, KeyError):
                        continue
                    if checkpoint >= 2:
                        break
        else:
            pytest.fail('No resumable checkpoint: ' + first.stderr.read().decode('utf-8', 'replace'))
        first.kill()
        first.wait(timeout=10)
        saved = (directory / 'media.mp4.part').stat().st_size
        assert saved > 0
        before = Counter(path for path, _ in requests)
        second = launch()
        # stdin was already closed, so communicate must not try to flush it.
        second.stdin = None
        stdout, stderr = second.communicate(timeout=45)
        assert second.returncode == 0, stderr.decode('utf-8', 'replace')
        result = next(json.loads(line)['data'] for line in stdout.splitlines()
                      if json.loads(line).get('type') == 'result')
        assert result['actual']['has_audio'] and result['actual']['height'] == 480
        if protocol == 'http':
            assert any(path == '/fixture.mp4' and offset == saved for path, offset in requests)
            assert Path(result['path']).read_bytes() == data
        else:
            after = Counter(path for path, _ in requests)
            assert after['/fixture0.ts'] == before['/fixture0.ts'] == 1
            assert after['/fixture1.ts'] == before['/fixture1.ts'] == 1
            assert abs(result['actual']['duration'] - 6) < .25
    finally:
        if first and first.poll() is None:
            first.kill()
            first.wait()
        server.shutdown()
        server.server_close()
