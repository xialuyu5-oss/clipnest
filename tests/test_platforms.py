"""Platform routing and packaging, without assuming a site's live availability."""
import hashlib
import io
import json
from pathlib import Path
import subprocess

import pytest
from yt_dlp import YoutubeDL

from app.safety import (ALLOWED_EXTRACTORS, PLATFORMS, UserError, normalize_url,
                        resolve_short_link, public_thumbnail)
from app.worker import common_options
from scripts.build_release import payload

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ('https://douyin.com/video/6961737553342991651', 'Douyin', 'Douyin'),
    ('https://www.iesdouyin.com/share/video/6961737553342991651/', 'Douyin', 'Douyin'),
    ('https://www.douyin.com/?modal_id=6961737553342991651', 'Douyin', 'Douyin'),
    ('https://www.douyin.com/share/video/6961737553342991651/', 'Douyin', 'Douyin'),
    ('https://xiaohongshu.com/explore/6411cf99000000001300b6d9', 'Xiaohongshu', 'XiaoHongShu'),
    ('https://www.xiaohongshu.com/discovery/item/674051740000000007027a15?xsec_token=example%2Btoken%3D', 'Xiaohongshu', 'XiaoHongShu'),
    ('https://weibo.com/7827771738/N4xlMvjhI', 'Weibo', 'Weibo'),
    ('https://m.weibo.cn/detail/4189191225395228', 'Weibo', 'Weibo'),
    ('https://weibo.com/tv/show/1034:4797699866951785', 'Weibo', 'WeiboVideo'),
    ('https://www.ixigua.com/6996881461559165471', 'Ixigua', 'Ixigua'),
    ('https://acfun.cn/v/ac35457073', 'AcFun', 'AcFunVideo'),
    ('https://www.xinpianchang.com/a11766551', 'Xinpianchang', 'Xinpianchang'),
    ('https://ted.com/talks/candace_parker_how_to_break_down_barriers_and_not_accept_limits', 'TED', 'TedTalk'),
    ('https://www.pinterest.com/pin/664281013778109217/', 'Pinterest', 'Pinterest'),
    ('https://www.pinterest.jp/pin/664281013778109217/', 'Pinterest', 'Pinterest'),
    ('https://www.nicovideo.jp/watch/sm8628149', 'Niconico', 'Niconico'),
]


@pytest.mark.parametrize('url,platform,extractor', CASES)
def test_new_platform_routes_to_real_dedicated_extractor(url, platform, extractor):
    clean, actual = normalize_url(url)
    assert actual == platform
    with YoutubeDL(common_options({})) as engine:
        matches = [ie.ie_key() for ie in engine._ies.values() if ie.suitable(clean)]
        assert extractor in matches
        assert 'Generic' not in engine._ies


def test_ixigua_id_is_not_truncated_by_upstream_url_pattern():
    from yt_dlp.extractor.ixigua import IxiguaIE
    for url in ('https://www.ixigua.com/6996881461559165471',
                'https://www.ixigua.com/video/6996881461559165471?utm_source=share'):
        clean, _ = normalize_url(url)
        assert IxiguaIE()._match_id(clean) == '6996881461559165471'


@pytest.mark.parametrize('short,final,platform', [
    ('https://v.douyin.com/example/', 'https://www.douyin.com/share/video/6961737553342991651/', 'Douyin'),
    ('https://xhslink.com/a/example', 'https://www.xiaohongshu.com/explore/6411cf99000000001300b6d9?xsec_token=A%2BB%3D&utm_source=share', 'Xiaohongshu'),
    ('https://t.cn/example', 'https://weibo.com/7827771738/N4xlMvjhI', 'Weibo'),
    ('https://v.ixigua.com/example/', 'https://www.ixigua.com/6996881461559165471', 'Ixigua'),
    ('https://pin.it/example', 'https://www.pinterest.com/pin/664281013778109217/', 'Pinterest'),
    ('https://nico.ms/sm8628149', 'https://www.nicovideo.jp/watch/sm8628149', 'Niconico'),
])
def test_new_sharing_hosts_and_access_parameters(short, final, platform):
    class Engine:
        def urlopen(self, request):
            assert request.url == short
            return type('Response', (io.BytesIO,), {'url': final})(b'')
    clean, actual = resolve_short_link(Engine(), short)
    assert actual == platform
    if platform == 'Xiaohongshu':
        assert 'xsec_token=A%2BB%3D' in clean
        assert 'utm_source' not in clean


@pytest.mark.parametrize('domain', [d for domains in PLATFORMS.values() for d in domains])
def test_platform_lookalikes_are_rejected(domain):
    with pytest.raises(UserError):
        normalize_url(f'https://{domain}.attacker.example/video/123')


def test_web_android_and_portable_clients_share_platform_scope():
    js = "process.stdout.write(JSON.stringify(require('./clients/shared/core.js').platforms))"
    core = json.loads(subprocess.check_output(['node', '-e', js], cwd=ROOT, text=True))
    expected = {('Bilibili' if k == '哔哩哔哩' else k): list(v) for k, v in PLATFORMS.items()}
    assert core == expected
    assert common_options({})['allowed_extractors'] == list(ALLOWED_EXTRACTORS)
    # The native worker imports the same routing and short-link policy; Android's
    # asset task already includes app/safety.py in its engine ZIP.
    native = (ROOT / 'clients/engine/worker.py').read_text(encoding='utf-8')
    assert "'allowed_extractors': list(ALLOWED_EXTRACTORS)" in native
    assert 'resolve_short_link(engine, url)' in native


def test_logo_payload_is_complete_and_binary_bytes_are_preserved():
    logos = json.loads((ROOT / 'docs/platform-logos.json').read_text())
    files = payload()
    assert len(logos) == len(PLATFORMS) == 19
    for logo in logos.values():
        data = (ROOT / logo['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == logo['sha256']
        assert files[logo['file']] == data, 'Packaging must not normalize image bytes as text'
        assert logo['source'].startswith('https://')


@pytest.mark.parametrize('host', ['p3.douyinpic.com', 'p3.byteimg.com', 'sns-webpic-qc.xhscdn.com',
    'wx1.sinaimg.cn', 'cdn.aixifan.com', 'cdn.acfun.cn', 'oss-xpc0.xpccdn.com',
    'pi.tedcdn.com', 'i.pinimg.com', 'img.cdn.nimg.jp'])
def test_new_platform_thumbnail_domains(host):
    assert public_thumbnail(f'https://{host}/cover.jpg')
    assert public_thumbnail(f'https://{host}.evil.example/cover.jpg') is None
    assert public_thumbnail(f'http://{host}/cover.jpg') is None
