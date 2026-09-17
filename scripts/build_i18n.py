"""Bundle local catalogs for the server and standalone preview. No network requests."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    catalogs = {p.stem: json.loads(p.read_text(encoding='utf-8'))
                for p in sorted((ROOT / 'web/assets/locales').glob('*.json'))}
    source = 'window.CLIPNEST_CATALOGS=' + json.dumps(catalogs, ensure_ascii=False, separators=(',', ':')) + ';\n'
    (ROOT / 'web/assets/i18n-catalogs.js').write_text(source, encoding='utf-8')
    print(f'Bundled {len(catalogs)} languages.')


if __name__ == '__main__':
    main()
