"""Android subprocess adapter; media interpretation is shared with the Web service.

The command launcher is Android-specific. An iOS adapter must call an embedded
engine and use a native media processor instead of starting this subprocess.
"""
import json
import os
from pathlib import Path
import sys


def emit(event, **values):
    print(json.dumps({'event': event, **values}, ensure_ascii=False), flush=True)


def main():
    # A dedicated process group lets cancellation stop FFmpeg descendants too.
    os.setsid()
    emit('process', pid=os.getpid())
    payload = json.loads(sys.argv[1])
    sys.path.insert(0, payload['engine_zip'])
    import yt_dlp
    from app.media import build_media
    from app.safety import (ALLOWED_EXTRACTORS, normalize_url, network_guard,
                            friendly_error, UserError, resolve_short_link)

    class Logger:
        def debug(self, message): pass
        def warning(self, message): pass
        def error(self, message): pass

    def progress(data):
        if data.get('status') == 'downloading':
            total = data.get('total_bytes') or data.get('total_bytes_estimate')
            downloaded = data.get('downloaded_bytes') or 0
            emit('progress', downloaded=downloaded, total=total,
                 progress=min(99, downloaded / total * 100) if total else None,
                 speed=data.get('speed'), eta=data.get('eta'), eta_scope='track')

    def postprocess(data):
        if data.get('status') == 'started':
            emit('processing')

    try:
        url, platform = normalize_url(payload['url'])
        options = {'noplaylist': True, 'skip_download': payload['mode'] == 'analyze',
                   'logger': Logger(), 'socket_timeout': 30, 'retries': 3,
                   'nocheckcertificate': False, 'cachedir': False,
                   'js_runtimes': {'quickjs': {'path': payload['quickjs']}},
                   'ffmpeg_location': payload['ffmpeg'], 'quiet': True,
                   'remote_components': [], 'enable_file_urls': False,
                   'skip_unavailable_fragments': False, 'geo_bypass': False,
                   'allowed_extractors': list(ALLOWED_EXTRACTORS),
                   'progress_hooks': [progress], 'postprocessor_hooks': [postprocess]}
        if payload['mode'] == 'download':
            directory = Path(payload['directory']).resolve()
            options.update({'format': payload['selector'], 'continuedl': True,
                            'overwrites': False, 'nopart': False,
                            'merge_output_format': payload['container'],
                            'outtmpl': str(directory / 'media.%(ext)s')})
        with network_guard(), yt_dlp.YoutubeDL(options) as engine:
            url, platform = resolve_short_link(engine, url)
            info = engine.extract_info(url, download=False)
            media = build_media(info, platform, url)
            if payload['mode'] == 'analyze':
                emit('result', result=media)
            else:
                # Re-extract on every resume to refresh expiring source URLs;
                # reject selected formats which are no longer available.
                if not any(o['_selector'] == payload['selector'] for o in media['options']):
                    raise UserError('Re-analyze the link to select a current format.', 'INVALID_FORMAT')
                engine.process_ie_result(info, download=True)
                candidates = [p for p in directory.glob('media.*') if p.suffix in ('.mp4','.mkv','.webm','.mov','.m4v') and p.stat().st_size > 0]
                if len(candidates) != 1:
                    raise UserError('The final media file could not be verified.', 'MERGE_FAILED')
                emit('result', result={'path': str(candidates[0]), 'bytes': candidates[0].stat().st_size})
    except Exception as error:
        code, message = (error.code, error.message) if isinstance(error, UserError) else friendly_error(str(error))
        emit('error', code=code, message=message)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
