"""Test-only adapter: feed a local fixture into the real production download worker.

This is not imported by the app. No live-platform network requests are made.
"""
import json
import sys
from contextlib import nullcontext
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import yt_dlp
from app import worker

payload = json.loads(sys.stdin.readline())
assert payload['url'].startswith('http://127.0.0.1:')
worker.normalize_url = lambda url: (url, 'YouTube')
worker.network_guard = lambda proxy: nullcontext()


def fixture_info(self, url, download=True, **kwargs):
    return self.process_ie_result({
        'id': 'fixture', 'title': 'Local resume fixture', 'extractor': 'fixture',
        'formats': [{'format_id': 'fixture', 'url': url, 'ext': 'mp4',
                     'protocol': payload['protocol'], 'width': 854, 'height': 480,
                     'vcodec': 'h264', 'acodec': 'aac'}]}, download=download)


yt_dlp.YoutubeDL.extract_info = fixture_info
worker.emit({'type': 'result', 'data': worker.run(payload)})
