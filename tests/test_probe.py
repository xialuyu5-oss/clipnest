"""Metadata probe (app.probe): what gets sampled, what gets filled, what is left unknown."""
import io
import itertools
import shutil
import subprocess

import pytest

from app.config import ROOT, Settings
from app.media import build_media
from app.probe import fill_format_metadata, first_hls_sample, needs_probe

DEMO = (ROOT / 'web/assets/demo-480.mp4').read_bytes()
BASE = 'https://media.example/hls/'


class FakeResponse(io.BytesIO):
    def __init__(self, data: bytes, url: str):
        super().__init__(data)
        self.url = url


class FakeSource:
    """Stands in for YoutubeDL.urlopen; serves bytes by URL and records requests."""

    def __init__(self, files: dict, fail: dict | None = None):
        self.files, self.fail, self.requests = files, fail or {}, []

    def urlopen(self, request):
        self.requests.append(request.url)
        assert request.headers['Range'].startswith('bytes=0-')
        if request.url in self.fail:
            raise self.fail[request.url]
        return FakeResponse(self.files[request.url], request.url)


def video(**extra):
    return {'format_id': 'v', 'url': BASE + 'video.mp4', 'ext': 'mp4', 'height': 480, 'width': 854, **extra}


def test_complete_formats_are_not_probed():
    source = FakeSource({})
    info = {'formats': [video(vcodec='avc1.640028', acodec='mp4a.40.2', fps=30),
                        {'format_id': 'a', 'url': BASE + 'a.m4a', 'ext': 'm4a', 'vcodec': 'none', 'acodec': 'mp4a.40.2'},
                        video(format_id='drm', has_drm=True),
                        video(format_id='odd', protocol='rtmp')]}
    assert not any(needs_probe(f) for f in info['formats'])
    fill_format_metadata(source, info)
    assert source.requests == []


def test_probe_fills_only_missing_fields():
    source = FakeSource({BASE + 'video.mp4': DEMO})
    fmt = video(vcodec='avc1.640028')  # platform knows the codec profile, not fps/audio
    fill_format_metadata(source, {'formats': [fmt]})
    assert fmt['vcodec'] == 'avc1.640028', 'platform metadata must not be overwritten'
    assert fmt['fps'] == 24 and fmt['acodec'] == 'aac'
    known_audio = video(format_id='k', acodec='mp4a.40.2')
    fill_format_metadata(source, {'formats': [known_audio]})
    assert known_audio['acodec'] == 'mp4a.40.2' and known_audio['vcodec'] == 'h264'


def test_single_format_info_is_probed():
    source = FakeSource({BASE + 'video.mp4': DEMO})
    info = {'title': 'single', 'format_id': 'single', 'url': BASE + 'video.mp4', 'ext': 'mp4', 'height': 480, 'width': 854}
    fill_format_metadata(source, info)
    option = build_media(info, 'Reddit', 'https://reddit.com/r/x/comments/1')['options'][0]
    assert (option['codec'], option['fps'], option['has_audio'], option['audio_codec']) == ('h264', 24, True, 'aac')


def test_hls_media_playlist_map_and_first_segment_are_sampled():
    playlist = b'#EXTM3U\n#EXT-X-MAP:URI="init.mp4"\n#EXTINF:6.0,\nseg0.m4s\n#EXT-X-ENDLIST\n'
    source = FakeSource({BASE + 'index.m3u8': playlist, BASE + 'init.mp4': DEMO, BASE + 'seg0.m4s': b''})
    fmt = video(url=BASE + 'index.m3u8', protocol='m3u8_native')
    fill_format_metadata(source, {'formats': [fmt]})
    assert source.requests == [BASE + 'index.m3u8', BASE + 'init.mp4', BASE + 'seg0.m4s']
    assert (fmt['vcodec'], fmt['acodec'], fmt['fps']) == ('h264', 'aac', 24)


@pytest.mark.parametrize('playlist', [
    b'#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key"\n#EXTINF:6.0,\nseg0.ts\n',
    b'#EXTM3U\n#EXT-X-MAP:URI="init.mp4",BYTERANGE="700@0"\n#EXTINF:6.0,\nseg0.m4s\n',
    b'#EXTM3U\n#EXTINF:6.0,\n#EXT-X-BYTERANGE:1000@0\nall.ts\n',
    b'#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1000000\nvariant.m3u8\n',
], ids=['encrypted', 'map-byterange', 'byterange', 'master'])
def test_hls_unsupported_playlists_are_left_unknown(playlist):
    assert first_hls_sample(playlist.decode()) is None
    source = FakeSource({BASE + 'index.m3u8': playlist})
    fmt = video(url=BASE + 'index.m3u8', protocol='m3u8_native')
    fill_format_metadata(source, {'formats': [fmt]})
    assert source.requests == [BASE + 'index.m3u8'], 'no media bytes may be fetched'
    assert 'vcodec' not in fmt and 'acodec' not in fmt


def test_probe_budget_bounds_requests(monkeypatch):
    source = FakeSource({BASE + 'video.mp4': DEMO})
    fill_format_metadata(source, {'formats': [video()]}, budget=0)
    assert source.requests == []
    clock = itertools.chain([0, 0], itertools.repeat(100))  # deadline passes as the first read starts
    monkeypatch.setattr('app.probe.time.monotonic', lambda: next(clock))
    fmt = video()
    fill_format_metadata(source, {'formats': [fmt, video(format_id='second', url=BASE + 'second.mp4')]}, budget=10)
    assert 'vcodec' not in fmt and len(source.requests) <= 1
    assert Settings(analyze_timeout=90).probe_seconds == 25
    assert Settings(analyze_timeout=30).probe_seconds == 10
    assert Settings(analyze_timeout=5).probe_seconds == 1


def test_probe_survives_unexpected_exception_types():
    class Odd(Exception):
        pass
    source = FakeSource({BASE + 'video.mp4': DEMO, BASE + 'second.mp4': b'not a media file at all'},
                        fail={BASE + 'video.mp4': Odd('handler quirk')})
    formats = [video(), video(format_id='second', url=BASE + 'second.mp4')]
    fill_format_metadata(source, {'formats': formats})  # must not raise
    assert 'vcodec' not in formats[0] and 'vcodec' not in formats[1]
    options = build_media({'formats': formats}, 'X', 'https://x.com/test')['options']
    assert len(options) == 1 and options[0]['has_audio'] is None


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='ffmpeg needed to build fMP4 HLS fixture')
@pytest.mark.parametrize('with_audio', [True, False], ids=['audio', 'video-only'])
def test_real_fmp4_hls_variant(tmp_path, with_audio):
    """Same shape as X's HLS variants: fMP4 init segment plus media segments."""
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(ROOT / 'web/assets/demo-480.mp4'), '-c', 'copy']
                   + ([] if with_audio else ['-an'])
                   + ['-f', 'hls', '-hls_time', '2', '-hls_playlist_type', 'vod', '-hls_segment_type', 'fmp4',
                      '-hls_fmp4_init_filename', 'init.mp4', '-hls_segment_filename', 'seg%d.m4s', 'index.m3u8'],
                   cwd=tmp_path, check=True, timeout=60)
    source = FakeSource({BASE + p.name: p.read_bytes() for p in tmp_path.iterdir()})
    fmt = video(url=BASE + 'index.m3u8', protocol='m3u8_native')  # platform gave no codec/fps/audio info
    fill_format_metadata(source, {'formats': [fmt]})
    assert fmt['vcodec'] == 'h264' and fmt['fps'] == 24
    # fMP4 init segments carry the full stream table, so "no audio track" is a safe inference here.
    assert fmt['acodec'] == ('aac' if with_audio else 'none')
    if not with_audio:
        # An independent audio track with unknown codec must still be merged with it.
        audio = {'format_id': 'audio', 'url': BASE + 'audio.m3u8', 'ext': 'mp4', 'vcodec': 'none', 'protocol': 'm3u8_native'}
        option = build_media({'formats': [fmt, audio]}, 'X', 'https://x.com/test')['options'][0]
        assert option['_selector'] == 'v+audio' and option['needs_merge'] and option['has_audio'] is True
