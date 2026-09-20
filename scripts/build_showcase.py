"""Build the public product preview and reproducible multilingual introductions."""
import argparse
import json
from pathlib import Path

from build_preview import build_html

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ('en', 'zh-CN', 'zh-TW', 'ja', 'ko', 'es', 'fr', 'de', 'pt', 'ru', 'ar', 'hi')
BASE = 'https://xialuyu5-oss.github.io/clipnest/'


def catalogs():
    data = json.loads((ROOT / 'docs/i18n/introductions.json').read_text(encoding='utf-8'))
    assert tuple(data) == LOCALES
    keys = set(data['en'])
    assert all(set(values) == keys and all(isinstance(value, str) and value.strip()
               for value in values.values()) for values in data.values())
    return data


def payload():
    data = catalogs()
    files = {f'preview/{name}': (ROOT / 'site/preview' / name).read_bytes()
             for name in ('index.html', 'style.css', 'app.js')}
    files['preview/catalogs.js'] = ('window.CLIPNEST_INTRODUCTIONS = ' +
        json.dumps(data, ensure_ascii=False) + ';\n').encode('utf-8')
    files['preview/app.html'] = build_html().encode('utf-8')
    for name in ('desktop', 'platforms', 'mobile'):
        files[f'preview/images/{name}.png'] = (ROOT / f'docs/images/{name}-20260920.png').read_bytes()
    return files


def introductions():
    data = catalogs()
    for locale, item in data.items():
        navigation = ' · '.join(f'[{row["name"]}]({key}.md)' for key, row in data.items())
        text = f'# ClipNest — {item["title"]}\n\n{navigation}\n\n'
        text += f'[{item["preview"]}]({BASE}preview/?lang={locale}) · [{item["source"]}](../../README.md) · [{item["guide"]}](../LOCAL_PROCESSING.md)\n\n'
        text += item['summary'] + '\n\n' + f'![{item["desktop"]}](../images/desktop-20260920.png)\n\n'
        text += item['demo'] + '\n\n'
        for prefix in ('local', 'platform', 'mobile'):
            body = 'platforms' if prefix == 'platform' else prefix
            text += f'## {item[prefix + "Title"]}\n\n{item[body]}\n\n'
        text += item['credit'] + '\n\n' + item['rights'] + '\n\n'
        text += '[MIT](../../LICENSE) · Android: [GPL-3.0-only](../../clients/android/LICENSE)\n'
        (ROOT / f'docs/i18n/{locale}.md').write_text(text, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-introductions', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.write_introductions:
        introductions()
    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
        for name, content in payload().items():
            destination = args.output / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
    print(f'Validated {len(catalogs())} introduction languages.')


if __name__ == '__main__':
    main()
