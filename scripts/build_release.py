"""Build allowlisted Web release artifacts locally; never upload or sign anything."""
import argparse
import ast
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
FIXED_TIME = 315532800  # 1980-01-01, also valid for ZIP timestamps.


def digest(data):
    return hashlib.sha256(data).hexdigest()


def version():
    module = ast.parse((ROOT / 'app/main.py').read_text(encoding='utf-8'))
    for item in module.body:
        if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'VERSION' for t in item.targets):
            result = ast.literal_eval(item.value)
            if not isinstance(result, str) or not all(c.isalnum() or c in '.-' for c in result):
                raise ValueError('Invalid release version')
            return result
    raise ValueError('Missing application version')


def payload():
    paths = list((ROOT / 'app').glob('*.py'))
    paths += [p for p in (ROOT / 'web').rglob('*') if p.is_file()
              and p.suffix in {'.html', '.css', '.js', '.svg', '.mp4'}
              and 'locales' not in p.relative_to(ROOT / 'web').parts]
    paths += [ROOT / name for name in (
        '.env.example', '.dockerignore', 'Dockerfile', 'compose.yaml', 'LICENSE',
        'requirements.txt', 'requirements-tested.txt', 'start.py', 'start.bat', 'start.sh')]
    files = {}
    for path in paths:
        if not path.resolve().is_relative_to(ROOT):
            raise ValueError('Payload path must stay in the source directory')
        name = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        # Normalize text so archives do not depend on a checkout's newline mode.
        if path.suffix not in {'.mp4'}:
            data = data.replace(b'\r\n', b'\n')
            if path.suffix == '.bat':
                data = data.replace(b'\n', b'\r\n')
        files[name] = data
    files['README.md'] = (ROOT / 'docs/WEB_INSTALL.md').read_bytes().replace(b'\r\n', b'\n')
    return dict(sorted(files.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Output directory; defaults to dist/v<version>')
    args = parser.parse_args()
    release_version = version()
    output = args.output or ROOT / 'dist' / ('v' + release_version)
    output.mkdir(parents=True, exist_ok=True)
    stem = f'clipnest-v{release_version}-web'
    names = [stem + '.zip', stem + '.tar.gz', 'SHA256SUMS.txt', 'release-manifest.json']
    if any((output / name).exists() for name in names):
        raise SystemExit('Output already exists. Review it or use a new --output directory; no files overwritten.')
    files = payload()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            info = zipfile.ZipInfo(stem + '/' + name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    tar_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=tar_buffer, mode='wb', mtime=FIXED_TIME, filename='') as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive:
            for name, data in files.items():
                info = tarfile.TarInfo(stem + '/' + name)
                info.size = len(data)
                info.mtime = FIXED_TIME
                info.mode = 0o755 if name.endswith('.sh') else 0o644
                archive.addfile(info, io.BytesIO(data))
    archives = {names[0]: zip_buffer.getvalue(), names[1]: tar_buffer.getvalue()}
    manifest = {
        'schema_version': 1, 'application_version': release_version, 'target': 'web-python',
        'runtime_bundled': False, 'docker_image_bundled': False,
        'mobile_apps_bundled': False,
        'files': [{'path': name, 'bytes': len(data), 'sha256': digest(data)} for name, data in files.items()],
        'assets': [{'name': name, 'bytes': len(data), 'sha256': digest(data)} for name, data in archives.items()],
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    assets = {**archives, 'release-manifest.json': manifest_bytes}
    sums = ''.join(f'{digest(data)}  {name}\n' for name, data in assets.items()).encode('ascii')
    for name, data in {**assets, 'SHA256SUMS.txt': sums}.items():
        with (output / name).open('xb') as handle:
            handle.write(data)
    print(json.dumps({'version': release_version, 'payload_files': len(files),
                      'output': str(output.resolve()), 'assets': manifest['assets']}, indent=2))


if __name__ == '__main__':
    main()
