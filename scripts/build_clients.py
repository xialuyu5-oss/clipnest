"""Prepare allowlisted Mini Program development source; no upload or account access."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist' / 'clients-1.4.0-alpha.1')
    args = parser.parse_args()
    target = args.output.resolve() / 'clipnest-wechat-ondevice-preview'
    if target.exists():
        raise SystemExit('Destination exists; choose a new output directory. Nothing overwritten.')
    source = ROOT / 'clients' / 'wechat'
    for path in source.rglob('*'):
        if path.is_file() and path.suffix in {'.js', '.json', '.wxss', '.wxml', '.md'} and path.name != 'project.private.config.json':
            out = target / path.relative_to(source)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, out)
    lib = target / 'miniprogram' / 'lib'
    shutil.copyfile(ROOT / 'clients/shared/core.js', lib / 'core.js')
    catalogs = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in sorted((ROOT / 'web/assets/locales').glob('*.json'))}
    extra = json.loads((ROOT / 'clients/shared/strings.json').read_text(encoding='utf-8'))
    for index, locale in enumerate(extra['locales']):
        catalogs[locale].update({key: values[index] for key, values in extra['messages'].items()})
    (lib / 'catalogs.js').write_text('module.exports = ' + json.dumps(catalogs, ensure_ascii=False) + ';\n', encoding='utf-8')
    shutil.copyfile(ROOT / 'LICENSE', target / 'LICENSE')
    files = [p for p in target.rglob('*') if p.is_file()]
    archive = target.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(files):
            z.write(path, str(Path(target.name) / path.relative_to(target)))
    result = {'target': 'wechat-ondevice-development-source', 'files': len(files), 'archive': str(archive),
              'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'signed': False,
              'developer_tools_verified': False, 'phone_verified': False, 'published': False}
    (args.output / 'wechat-manifest.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
