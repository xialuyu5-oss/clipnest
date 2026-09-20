"""Build a single HTML file with styles, scripts, and original demo media embedded."""
import base64
import json
from pathlib import Path
import re
import sys
from build_i18n import main as build_i18n

ROOT = Path(__file__).resolve().parent.parent


def build_html():
    web = ROOT / 'web'
    mapping = {}
    sizes = {}
    media_types = {'.svg': 'image/svg+xml', '.mp4': 'video/mp4', '.png': 'image/png',
                   '.ico': 'image/x-icon', '.webp': 'image/webp'}
    for file in (web / 'assets').rglob('*'):
        if not file.is_file() or file.suffix not in media_types:
            continue
        mime = media_types[file.suffix]
        mapping['/' + file.relative_to(web).as_posix()] = f'data:{mime};base64,' + base64.b64encode(file.read_bytes()).decode()
        if file.suffix == '.mp4':
            sizes[file.stem.split('-')[-1]] = file.stat().st_size
    html = (web / 'index.html').read_text(encoding='utf-8')
    # Version query strings change every release; match them generically.
    html, n_style = re.subn(r'<link rel="stylesheet" href="/style\.css(?:\?v=[^"]*)?">',
                            lambda _: '<style>' + (web / 'style.css').read_text(encoding='utf-8') + '</style>', html)
    html, n_member = re.subn(r'<link rel="stylesheet" href="/member\.css(?:\?v=[^"]*)?">',
                             lambda _: '<style>' + (web / 'member.css').read_text(encoding='utf-8') + '</style>', html)
    html, n_script = re.subn(r'<script defer src="/app\.js(?:\?v=[^"]*)?"></script>', '', html)
    assert (n_style, n_member, n_script) == (1, 1, 1), 'index.html asset tags changed; update build_preview.py'
    for asset in ('i18n-catalogs', 'i18n'):
        html, count = re.subn(r'<script defer src="/assets/' + asset + r'\.js(?:\?v=[^"]*)?"></script>', '', html)
        assert count == 1, f'Missing {asset} script tag'
    favicon = 'data:image/svg+xml;base64,' + base64.b64encode((web / 'favicon.svg').read_bytes()).decode()
    html = html.replace('href="/favicon.svg"', f'href="{favicon}"')
    for url, data in mapping.items():
        html = html.replace(f'src="{url}"', f'src="{data}"')
    prelude = ('window.CLIPNEST_PREVIEW=true;window.CLIPNEST_ASSETS=' + json.dumps(mapping)
               + ';window.CLIPNEST_DEMO_SIZES=' + json.dumps(sizes) + ';')
    js = '\n'.join((web / path).read_text(encoding='utf-8')
                   for path in ('assets/i18n-catalogs.js', 'assets/i18n.js', 'app.js')).replace('</script', '<\\/script')
    html = html.replace('</body>', '<script>' + prelude + js + '</script></body>')
    return html


def main():
    build_i18n()
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'ClipNest-界面预览.html'
    dest.write_text(build_html(), encoding='utf-8')
    print(dest)


if __name__ == '__main__':
    main()
