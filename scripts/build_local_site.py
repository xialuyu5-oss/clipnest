"""Build an offline-reviewable static entry site and PC setup kit. Never publish."""
import argparse
import hashlib
import html
import io
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_release import ROOT, payload, version
from build_showcase import payload as showcase_payload


def archive(files, prefix=''):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as output:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(prefix + name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, data)
    return buffer.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/local-device-preview')
    args = parser.parse_args()
    target = args.output.resolve()
    if target.exists():
        raise SystemExit('Output exists. Choose a new --output; nothing overwritten.')
    web = payload()
    setup_names = ['check-and-setup.bat', 'check-environment.bat', 'install-missing.bat', 'scripts/setup_windows.ps1']
    setup = {name: web[name] for name in setup_names}
    setup['README.md'] = (
        '# ClipNest Windows check and setup tool\n\n'
        '1. Extract this ZIP and double-click check-and-setup.bat. It checks locally before asking to install anything.\n'
        '2. Review missing/incompatible items. Type Y only for each download and installation you approve; Enter/N skips it.\n'
        '3. Close the window, reopen check-environment.bat and check again.\n'
        '4. In the separate ClipNest PC application package, run start-local.bat, then return to the website. '
        'The launcher separately asks before downloading project dependencies (including yt-dlp/EJS).\n\n'
        'No Python or running ClipNest service is needed to run this Windows PowerShell tool. '
        'check-environment.bat only checks; it never downloads or installs. System checks work offline. '
        'Approved installation uses WinGet, needs Internet access and may request administrator approval. '
        'It does not bundle Python/FFmpeg/Node, accept publisher agreements automatically, '
        'or install anything during a check. Working components are preserved.\n\n'
        'If WinGet is unavailable, install prerequisites from:\n'
        '- Python 3.11+: https://www.python.org/downloads/\n'
        '- FFmpeg + ffprobe: https://ffmpeg.org/download.html\n'
        '- Deno 2.3+: https://docs.deno.com/runtime/getting_started/installation/\n'
        '- OR Node.js 22+: https://nodejs.org/en/download\n\n'
        'This kit does not contain the ClipNest application.\n'
    ).encode()
    setup['README.zh-CN.md'] = (
        '# ClipNest Windows 本机检查与补装工具\n\n'
        '适用于 Windows 10/11，无需预装 Python，也无需先启动 ClipNest。\n\n'
        '1. 完整解压 ZIP，双击 check-and-setup.bat。工具首先在本机检查环境。\n'
        '2. 查看缺失或版本不兼容的项目。每个项目都需输入 Y 才会联网下载并安装；回车或 N 跳过。\n'
        '3. 安装后关闭窗口，重新运行 check-environment.bat 验证；该入口只检查，不安装。\n'
        '4. 在另行下载的 PC 程序包中运行 start-local.bat，再返回网页。首次安装 yt-dlp/EJS 等项目依赖也会单独询问。\n\n'
        '工具通过 WinGet 获取第三方安装程序，系统可能要求管理员许可；请阅读安装程序显示的协议。'
        '工具不自动接受协议，不下载已经检查可用的系统组件。Deno 与 Node.js 只需其中一种。\n\n'
        'WinGet 不可用时，工具会显示官方安装说明链接，供你自行选择。请按系统安全提示自行决定是否运行。\n\n'
        '检测在本机执行，结果显示在工具窗口，不会上传网站；此工具包不包含 ClipNest 主程序或第三方运行时。\n'
    ).encode('utf-8')
    setup['LICENSE'] = (ROOT / 'LICENSE').read_bytes()
    files = {name: (ROOT / 'site' / name).read_bytes() for name in ('index.html', 'style.css', 'app.js', 'catalogs.js', 'check-catalogs.js')}
    files.update(showcase_payload())
    files['.nojekyll'] = b''
    files['LICENSE'] = (ROOT / 'LICENSE').read_bytes()
    files['downloads/clipnest-local-pc.zip'] = archive(web, 'ClipNest/')
    files['downloads/clipnest-windows-setup.zip'] = archive(setup, 'ClipNest-Setup/')
    guide = html.escape((ROOT / 'docs/LOCAL_PROCESSING.md').read_text(encoding='utf-8'))
    files['guide.html'] = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                          '<title>ClipNest installation guide</title><link rel="stylesheet" href="style.css"><main><p><a href="./">← ClipNest</a></p><pre>' + guide + '</pre></main></html>').encode()
    files['downloads/SHA256SUMS.txt'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {Path(name).name}\n' for name, data in files.items() if name.endswith('.zip')).encode()
    manifest = {'status': 'build-artifact', 'web_version': version(), 'media_relay': False,
                'publication_status': 'not-recorded-in-build-artifact',
                'runtime_binaries_bundled': False, 'android_apk_included': False,
                'files': [{'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name,data in files.items()]}
    files['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    for name, data in files.items():
        path = target / 'site' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (target / 'clipnest-static-site.zip').write_bytes(archive(files))
    print(json.dumps({'output': str(target), 'files': len(files), 'published': False}, indent=2))


if __name__ == '__main__':
    main()
