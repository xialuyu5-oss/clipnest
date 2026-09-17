"""Convert source formats into honest, server-owned quality options."""
import math
import re
import secrets
from typing import Any

from .safety import UserError, public_thumbnail

VIDEO_EXTENSIONS = {'mp4', 'webm', 'mkv', 'mov', 'm4v'}
PROTOCOLS = {'http', 'https', 'm3u8_native', 'm3u8', 'http_dash_segments'}


def number(value: Any, default=0):
    try:
        x = float(value)
        return x if math.isfinite(x) and x >= 0 else default
    except (ValueError, TypeError):
        return default


def quality_height(fmt: dict) -> int:
    h, w = number(fmt.get('height')), number(fmt.get('width'))
    # "1080p" on a 1080x1920 vertical short means the 1080-pixel short edge.
    return int(min(h, w) if h and w else h or w)


def file_size(fmt: dict, duration: float) -> tuple[int | None, bool]:
    if number(fmt.get('filesize')):
        return int(number(fmt['filesize'])), False
    if number(fmt.get('filesize_approx')):
        return int(number(fmt['filesize_approx'])), True
    if number(fmt.get('tbr')) and duration:
        return int(number(fmt['tbr']) * 1000 / 8 * duration), True
    return None, True


def safe_format_id(fmt: dict) -> str | None:
    fid = str(fmt.get('format_id', ''))
    # Never allow arbitrary yt-dlp selector syntax from a remote format ID.
    return fid if re.fullmatch(r'[A-Za-z0-9_.:-]{1,120}', fid) else None


def build_media(info: dict, platform: str, original_url: str) -> dict:
    if info.get('_type') in ('playlist', 'multi_video') or info.get('entries') is not None:
        raise UserError('该链接包含多个视频。当前版本请使用单条视频的独立链接。', 'PLAYLIST_NOT_SUPPORTED')
    if info.get('is_live') or info.get('live_status') in ('is_live', 'is_upcoming'):
        raise UserError('当前版本不录制直播，请在直播结束后使用回放链接。', 'LIVE_NOT_SUPPORTED')
    if info.get('has_drm'):
        raise UserError('该视频受 DRM 保护，不提供解密或绕过。', 'DRM_PROTECTED')
    duration = number(info.get('duration'))
    formats = info.get('formats') or ([info] if info.get('url') else [])
    formats = [f for f in formats if not f.get('has_drm') and f.get('url')
               and f.get('protocol', 'https') in PROTOCOLS and safe_format_id(f)]
    audios = [f for f in formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none']
    videos = [f for f in formats if f.get('vcodec') != 'none'
              and f.get('ext') in VIDEO_EXTENSIONS and quality_height(f) > 0]
    best: dict[tuple, tuple] = {}
    for video in videos:
        height = quality_height(video)
        ext = video.get('ext', 'mp4')
        selector = safe_format_id(video)
        audio = None
        # Missing metadata is unknown, not proof that the video is silent.
        acodec = video.get('acodec')
        has_audio = None if not acodec else acodec != 'none'
        if has_audio is False and audios:
            preferred = [a for a in audios if (a.get('ext') in ('m4a', 'mp4') if ext == 'mp4'
                                               else a.get('ext') in ('webm', 'opus') if ext == 'webm' else True)]
            # Prefer the source default/original language rather than audio-description tracks.
            audio = max(preferred or audios, key=lambda a: (number(a.get('language_preference')),
                                                           number(a.get('quality')), number(a.get('abr')), number(a.get('tbr'))))
            selector += '+' + safe_format_id(audio)
            has_audio = True
            if not ((ext == 'mp4' and audio.get('ext') in ('m4a', 'mp4'))
                    or (ext == 'webm' and audio.get('ext') in ('webm', 'opus'))):
                ext = 'mkv'
        size, approximate = file_size(video, duration)
        if audio:
            audio_size, audio_approx = file_size(audio, duration)
            size = size + audio_size if size and audio_size else None
            approximate = approximate or audio_approx
        fps = number(video.get('fps'))
        score = (number(video.get('quality')), fps, number(video.get('tbr')))
        group = (height, ext, has_audio)
        if group not in best or score > best[group][0]:
            best[group] = (score, {
                'id': secrets.token_urlsafe(12), 'label': f'{height}p', 'height': height,
                'width': int(number(video.get('width'))), 'source_height': int(number(video.get('height'))),
                'fps': round(fps, 2) if fps else None, 'container': ext,
                'codec': str(video.get('vcodec') or 'unknown').split('.')[0],
                'audio_codec': (audio or video).get('acodec') if has_audio else None,
                'has_audio': has_audio, 'needs_merge': audio is not None,
                'filesize': size, 'approximate': approximate,
                'dynamic_range': video.get('dynamic_range') or 'SDR',
                '_selector': selector,
            })
    options = [x[1] for x in best.values()]
    audio_order = {True: 0, None: 1, False: 2}
    options.sort(key=lambda x: (-x['height'], audio_order[x['has_audio']],
                                x['container'] != 'mp4', -(x['fps'] or 0)))
    if not options:
        raise UserError('没有找到可下载的公开视频格式；该链接可能需要登录，或解析器暂不支持。', 'NO_FORMATS')
    return {
        'title': str(info.get('title') or '未命名视频')[:240],
        'uploader': str(info.get('uploader') or info.get('channel') or platform)[:120],
        'duration': duration or None, 'platform': platform, 'url': original_url,
        'thumbnail': public_thumbnail(info.get('thumbnail')),
        'description': str(info.get('description') or '')[:600],
        'upload_date': str(info.get('upload_date') or '')[:8],
        'is_demo': False, 'options': options[:24],
    }


def public_media(media: dict) -> dict:
    return {**{k: v for k, v in media.items() if not k.startswith('_') and k != 'options'},
            'options': [{k: v for k, v in f.items() if not k.startswith('_')} for f in media['options']]}
