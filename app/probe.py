"""Best-effort metadata from a small local sample, never a remote FFprobe input."""
from fractions import Fraction
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urljoin

from .media import PROTOCOLS, VIDEO_EXTENSIONS, number, quality_height, safe_format_id

DEFAULT_BUDGET_SECONDS = 25
SAMPLE_BYTES = 1024 * 1024
PLAYLIST_BYTES = 64 * 1024


def stream_details(info: dict) -> dict:
    video = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), {})
    audio = next((s for s in info.get('streams', []) if s.get('codec_type') == 'audio'), {})
    fps = None
    for rate in (video.get('avg_frame_rate'), video.get('r_frame_rate')):
        try:
            fps = number(float(Fraction(rate or '0')))
        except (ValueError, ZeroDivisionError):
            continue
        if fps:
            break
    return {'video': video.get('codec_name'), 'audio': audio.get('codec_name'),
            'fps': round(fps, 2) if fps else None}


def needs_probe(fmt: dict) -> bool:
    """Only formats with missing codec/frame-rate metadata are worth a sample request."""
    if not fmt.get('url') or fmt.get('has_drm') or not safe_format_id(fmt):
        return False
    if fmt.get('protocol', 'https') not in PROTOCOLS:
        return False
    if fmt.get('vcodec') == 'none':
        return not fmt.get('acodec')  # independent audio with unknown codec
    if fmt.get('ext') not in VIDEO_EXTENSIONS or not quality_height(fmt):
        return False
    return not fmt.get('acodec') or not fmt.get('vcodec') or not number(fmt.get('fps'))


def first_hls_sample(text: str) -> tuple[str | None, str | None] | None:
    """Return (init_uri, segment_uri) for a plain media playlist, or None when unsupported."""
    from yt_dlp.utils import parse_m3u8_attributes

    init = None
    for line in text.splitlines():
        if line.startswith('#EXT-X-KEY:') and parse_m3u8_attributes(line).get('METHOD') != 'NONE':
            return None  # Do not decrypt media for metadata inspection.
        if line.startswith('#EXT-X-MAP:'):
            attrs = parse_m3u8_attributes(line)
            if attrs.get('BYTERANGE'):
                return None
            init = attrs.get('URI')
        if line.startswith(('#EXT-X-BYTERANGE:', '#EXT-X-STREAM-INF:')):
            return None  # Byte-range playlists and master playlists are left unknown.
        if line and not line.startswith('#'):
            return init, line
    return None


def apply_details(fmt: dict, details: dict, format_name: str) -> None:
    """Fill only fields the platform left empty; never overwrite platform metadata."""
    if details['video'] and details['video'] != 'unknown' and fmt.get('vcodec') != 'none':
        if not fmt.get('vcodec'):
            fmt['vcodec'] = details['video']
        if details['fps'] and not number(fmt.get('fps')):
            fmt['fps'] = details['fps']
    if fmt.get('acodec'):
        return
    if details['audio'] and details['audio'] != 'unknown':
        fmt['acodec'] = details['audio']
    elif details['video'] and 'mov' in format_name:
        # MP4's stream table identifies all tracks. A short TS sample may not.
        fmt['acodec'] = 'none'


def fill_format_metadata(ydl, info: dict, budget: float = DEFAULT_BUDGET_SECONDS) -> None:
    from yt_dlp.networking import Request

    probe = shutil.which('ffprobe')
    if not probe or budget <= 0:
        return
    # This bounds metadata inspection only; it does not limit user downloads.
    deadline = time.monotonic() + budget
    formats = info.get('formats') or ([info] if info.get('url') else [])
    candidates = [f for f in formats if needs_probe(f)]
    # Identify independent audio first, then the highest available video qualities.
    candidates.sort(key=lambda f: (f.get('vcodec') != 'none', -quality_height(f), -number(f.get('tbr'))))
    if not candidates:
        return

    def read(url, headers, limit):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        request = Request(url, headers={**headers, 'Range': f'bytes=0-{limit - 1}'},
                          extensions={'timeout': min(4, remaining)})
        with ydl.urlopen(request) as response:
            return response.read(limit), response.url

    with tempfile.TemporaryDirectory(prefix='clipnest-probe-') as directory:
        path = Path(directory) / 'sample.bin'
        for fmt in candidates:
            if time.monotonic() >= deadline:
                break
            headers = fmt.get('http_headers') or info.get('http_headers') or {}
            try:
                if fmt.get('protocol') in ('m3u8', 'm3u8_native'):
                    playlist, base = read(fmt['url'], headers, PLAYLIST_BYTES)
                    sample = first_hls_sample(playlist.decode('utf-8'))
                    if not sample:
                        continue
                    init, segment = sample
                    data = read(urljoin(base, init), headers, SAMPLE_BYTES)[0] if init else b''
                    data += read(urljoin(base, segment), headers, SAMPLE_BYTES)[0]
                elif fmt.get('protocol', 'https') in ('http', 'https'):
                    data, _ = read(fmt['url'], headers, SAMPLE_BYTES)
                else:
                    continue
                if not data:
                    continue
                path.write_bytes(data)
                result = subprocess.run([
                    probe, '-v', 'error', '-protocol_whitelist', 'file',
                    '-format_whitelist', 'mov,matroska,webm,mpegts,aac,mp3,ogg,flac',
                    '-show_entries', 'stream=codec_type,codec_name,avg_frame_rate,r_frame_rate:format=format_name',
                    '-of', 'json', str(path)], capture_output=True,
                    timeout=max(0.1, min(4, deadline - time.monotonic())), check=True)
                measured = json.loads(result.stdout)
                apply_details(fmt, stream_details(measured), measured.get('format', {}).get('format_name', ''))
            except Exception:
                # Missing optional metadata must never block usable formats, whatever the
                # failure type (network, decode, ffprobe, or an unexpected handler quirk).
                continue
