"""Isolated extraction/download worker. JSON in; newline-delimited JSON events out.

It is deliberately not an HTTP endpoint and never accepts browser-supplied yt-dlp
arguments, cookies, arbitrary output paths, or executable commands.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

from .config import ROOT
from .media import build_media, number
from .probe import DEFAULT_BUDGET_SECONDS, fill_format_metadata, stream_details
from .safety import (ALLOWED_EXTRACTORS, UserError, friendly_error, network_guard,
                     normalize_url, resolve_short_link)

# Opt-in diagnostics: forwards yt-dlp warnings/errors and tracebacks to stderr, which the
# parent logs at DEBUG level. May include source URLs; keep off unless troubleshooting.
DEBUG = os.getenv('DEBUG_WORKER', '').lower() == 'true'


def attach_account(ydl, payload, platform):
    if payload.get('account_cookies'):
        if platform != '哔哩哔哩' or payload.get('account_platform') != 'bilibili':
            raise UserError('平台账号与链接不匹配。', 'ACCOUNT_MISMATCH')
        from .accounts import install_cookies
        install_cookies(ydl.cookiejar, payload['account_cookies'])


def emit(event: dict) -> None:
    print(json.dumps(event, ensure_ascii=False), flush=True)


class QuietLogger:
    def debug(self, message):
        pass

    def warning(self, message):
        if DEBUG:
            print(f'[yt-dlp] {message}', file=sys.stderr, flush=True)

    def error(self, message):
        # Exceptions are mapped to safe, actionable messages below.
        if DEBUG:
            print(f'[yt-dlp] {message}', file=sys.stderr, flush=True)


def common_options(payload: dict) -> dict:
    runtimes = {}
    if shutil.which('deno'):
        runtimes['deno'] = {}
    elif shutil.which('node'):
        runtimes['node'] = {}
    return {
        'quiet': True, 'no_warnings': True, 'logger': QuietLogger(),
        'noplaylist': True, 'playlistend': 1, 'extract_flat': False,
        'socket_timeout': 20, 'retries': 2, 'fragment_retries': 2,
        'extractor_retries': 1, 'concurrent_fragment_downloads': 2,
        'cachedir': False, 'js_runtimes': runtimes, 'remote_components': [],
        'proxy': payload.get('proxy') or '', 'geo_bypass': False,
        'enable_file_urls': False, 'allow_unplayable_formats': False,
        'skip_unavailable_fragments': False, 'hls_prefer_native': True,
        'check_formats': False, 'windowsfilenames': True,
        'allowed_extractors': list(ALLOWED_EXTRACTORS),
    }


def inspect_file(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size == 0:
        raise UserError('没有生成完整的视频文件，请重新解析后重试。', 'EMPTY_FILE')
    probe = shutil.which('ffprobe')
    if not probe:
        raise UserError('服务端未安装 FFprobe，无法检查下载结果。', 'MISSING_FFMPEG')
    result = subprocess.run([probe, '-v', 'error', '-show_streams', '-show_format',
                             '-of', 'json', str(path)], capture_output=True, timeout=45, check=True)
    info = json.loads(result.stdout)
    video = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), None)
    if not video:
        raise UserError('下载结果中没有有效的视频轨道。', 'INVALID_MEDIA')
    duration = float(info.get('format', {}).get('duration') or 0)
    details = stream_details(info)
    return {'filesize': path.stat().st_size, 'container': path.suffix[1:],
            'width': video.get('width'), 'height': video.get('height'),
            'codec': video.get('codec_name'), 'duration': duration,
            'fps': details['fps'], 'audio_codec': details['audio'],
            'has_audio': any(s.get('codec_type') == 'audio' for s in info.get('streams', []))}


def fill_replay_duration(ydl, info: dict) -> None:
    """Completed HLS replays sometimes omit duration in the platform metadata."""
    if info.get('duration') or not (info.get('was_live') or info.get('live_status') == 'was_live'):
        return
    fmt = next((f for f in info.get('formats', [])
                if f.get('protocol') in ('m3u8', 'm3u8_native') and f.get('url')), None)
    if not fmt:
        return
    from yt_dlp.networking import Request
    request = Request(fmt['url'], headers=fmt.get('http_headers') or info.get('http_headers') or {})
    with ydl.urlopen(request) as response:
        playlist = response.read(8 * 1024 * 1024 + 1)
    if len(playlist) > 8 * 1024 * 1024:
        return
    lines = playlist.decode('utf-8').splitlines()
    if '#EXT-X-ENDLIST' not in lines:
        return  # An unfinished playlist cannot establish the complete duration.
    duration = sum(number(line.split(':', 1)[1].split(',', 1)[0])
                   for line in lines if line.startswith('#EXTINF:'))
    if duration:
        info['duration'] = duration


def run(payload: dict) -> dict:
    mode = payload['mode']
    if mode == 'demo':
        height = int(payload['height'])
        if height not in (1080, 720, 480):
            raise UserError('演示清晰度不存在。')
        source = ROOT / 'web' / 'assets' / f'demo-{height}.mp4'
        target = Path(payload['directory']) / 'media.mp4'
        emit({'type': 'progress', 'state': 'downloading', 'progress': 35})
        shutil.copyfile(source, target)
        emit({'type': 'progress', 'state': 'processing', 'progress': 96})
        actual = inspect_file(target)
        return {'path': str(target), 'actual': actual}
    try:
        import yt_dlp
    except ImportError:
        raise UserError('服务端未安装 yt-dlp，请运行启动脚本安装依赖。', 'MISSING_DEPENDENCY')
    url, platform = normalize_url(payload['url'])
    options = common_options(payload)
    if payload.get('account_cookies'):
        if platform != '哔哩哔哩' or payload.get('account_platform') != 'bilibili':
            raise UserError('平台账号与链接不匹配。', 'ACCOUNT_MISMATCH')
        options['allowed_extractors'] = ['bilibili.*', 'bili.*']
    if mode == 'analyze':
        options['skip_download'] = True
        with network_guard(payload.get('proxy', '')), yt_dlp.YoutubeDL(options) as ydl:
            # Expand short links before attaching any account so the redirect request
            # carries no platform cookies; the resolved platform is what the account is matched to.
            url, platform = resolve_short_link(ydl, url)
            attach_account(ydl, payload, platform)
            info = ydl.extract_info(url, download=False)
            if isinstance(info, dict):
                fill_replay_duration(ydl, info)
                fill_format_metadata(ydl, info, number(payload.get('probe_seconds'), DEFAULT_BUDGET_SECONDS))
        if not isinstance(info, dict):
            raise UserError('平台未返回有效的视频信息。', 'NO_FORMATS')
        return build_media(info, platform, url)
    if mode != 'download':
        raise UserError('未知工作类型。')
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise UserError('服务端未安装 FFmpeg / FFprobe。', 'MISSING_FFMPEG')
    directory = Path(payload['directory']).resolve()
    option = payload['option']
    last_progress = 0.0
    track_bytes = {}
    track_totals = {}
    selected_tracks = set(option['_selector'].split('+'))

    def progress(data):
        nonlocal last_progress
        now = time.monotonic()
        if now - last_progress < 0.3 and data.get('status') != 'finished':
            return
        last_progress = now
        downloaded = data.get('downloaded_bytes') or 0
        total = data.get('total_bytes') or data.get('total_bytes_estimate') or 0
        track = str(data.get('info_dict', {}).get('format_id') or '')[:100]
        track_bytes[track] = downloaded
        if total:
            track_totals[track] = total
        eta = data.get('eta')
        eta_scope = 'track' if option.get('needs_merge') else 'download'
        if option.get('needs_merge') and track in selected_tracks:
            overall_total = (sum(track_totals[t] for t in selected_tracks)
                             if selected_tracks <= track_totals.keys() else option.get('filesize'))
            speed = data.get('speed')
            if overall_total and speed and speed > 0:
                # Includes the not-yet-downloaded audio track. Source size estimates
                # can change; merging time is deliberately excluded.
                eta = max(0, overall_total - sum(track_bytes.get(t, 0) for t in selected_tracks)) / speed
                eta_scope = 'download'
        # Each track has its own progress. The UI labels it as the current track
        # instead of inventing an overall percentage for an unknown-length merge.
        emit({'type': 'progress', 'state': 'downloading',
              'progress': min(95, round(downloaded / total * 95, 1)) if total else None,
              'downloaded': downloaded, 'total': total or None,
              'speed': data.get('speed'), 'eta': eta, 'eta_scope': eta_scope,
              'track': track})

    def postprocess(data):
        emit({'type': 'progress', 'state': 'processing', 'progress': 97,
              'speed': None, 'eta': None})

    def match_filter(info, *, incomplete=False):
        if info.get('is_live') or info.get('live_status') in ('is_live', 'is_upcoming'):
            return 'Live video is not supported'
        if info.get('has_drm'):
            return 'DRM protected video is not supported'
        return None

    options.update({
        'format': option['_selector'], 'merge_output_format': option['container'],
        'outtmpl': str(directory / 'media.%(ext)s'), 'paths': {'home': str(directory), 'temp': str(directory)},
        'max_downloads': 1,
        'progress_hooks': [progress], 'postprocessor_hooks': [postprocess],
        'match_filter': match_filter, 'noprogress': True, 'overwrites': False,
        'continuedl': True, 'nopart': False,
        'writethumbnail': False, 'writeinfojson': False, 'writesubtitles': False,
        'keepvideo': False,
    })
    with network_guard(payload.get('proxy', '')), yt_dlp.YoutubeDL(options) as ydl:
        attach_account(ydl, payload, platform)
        try:
            ydl.extract_info(url, download=True)
        except yt_dlp.utils.MaxDownloadsReached:
            # yt-dlp raises this after completing the first file when the
            # one-item limit is reached. It is NOT proof of success: validate
            # the exact output, tracks and dimensions below before returning.
            pass
    candidates = [p for p in directory.iterdir() if p.name in (
        'media.mp4', 'media.webm', 'media.mkv', 'media.mov', 'media.m4v')]
    if len(candidates) != 1:
        raise UserError('音视频未能合并成单个完整文件，请重试。', 'MERGE_FAILED')
    path = candidates[0]
    actual = inspect_file(path)
    edge = min(actual['width'] or 0, actual['height'] or 0)
    if edge and abs(edge - option['height']) > 8:
        raise UserError('平台返回的分辨率与所选清晰度不符，请重新解析。', 'QUALITY_CHANGED')
    if option.get('has_audio') and not actual['has_audio']:
        raise UserError('结果缺少预期的音轨，请重新解析。', 'MISSING_AUDIO')
    return {'path': str(path), 'actual': actual}


if __name__ == '__main__':
    try:
        payload = json.loads(sys.stdin.readline())
        emit({'type': 'result', 'data': run(payload)})
    except UserError as exc:
        emit({'type': 'error', 'code': exc.code, 'message': exc.message})
        print(f'Worker stopped: {exc.code}', file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        code, message = friendly_error(str(exc))
        emit({'type': 'error', 'code': code, 'message': message})
        # Default output avoids exposing source URLs, local filenames, or proxy credentials.
        print(f'Worker failed: {type(exc).__name__} ({code})', file=sys.stderr)
        if DEBUG:
            traceback.print_exc(file=sys.stderr)
        sys.exit(1)
