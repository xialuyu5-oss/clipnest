"""Cross-platform local launcher. Installs only project dependencies in .venv."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import venv
import webbrowser

ROOT = Path(__file__).resolve().parent


def main():
    if sys.version_info < (3, 11):
        raise SystemExit('需要 Python 3.11 或以上版本。请安装新版 Python 后重试。')
    parser = argparse.ArgumentParser(description='启动留影 ClipNest')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--update', action='store_true', help='更新 Python 依赖和解析引擎')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit('端口必须位于 1–65535。')
    os.chdir(ROOT)
    location = ROOT / '.venv'
    python = location / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        print('正在创建项目独立 Python 环境 .venv …', flush=True)
        venv.create(location, with_pip=True)
    requirement = ROOT / 'requirements.txt'
    digest = hashlib.sha256(requirement.read_bytes()).hexdigest()
    marker = location / '.clipnest-requirements'
    if args.update or not marker.is_file() or marker.read_text().strip() != digest:
        print('正在安装项目依赖；首次启动需要联网访问 Python 包仓库。', flush=True)
        command = [str(python), '-m', 'pip', 'install', '--upgrade', '-r', str(requirement)]
        if subprocess.call(command):
            raise SystemExit('依赖安装失败。请检查网络 / DNS / 包仓库访问权限后重试。没有启动服务。')
        marker.write_text(digest)
    if args.host not in ('127.0.0.1', 'localhost', '::1'):
        validation = subprocess.run([str(python), '-c',
            'from app.config import settings; settings.validate(); '
            'assert settings.access_key, "对外监听前必须在 .env 设置 ACCESS_KEY"'], cwd=ROOT)
        if validation.returncode:
            raise SystemExit('拒绝无口令的对外监听。请设置 ACCESS_KEY，并阅读 docs/DEPLOYMENT.md。')
    missing = [tool for tool in ('ffmpeg', 'ffprobe') if not shutil.which(tool)]
    if missing:
        print('\n提示：缺少 ' + ', '.join(missing) + '。页面可打开，但完整下载需要先安装 FFmpeg。')
    if not shutil.which('deno') and not shutil.which('node'):
        print('提示：YouTube 需要 Deno >= 2.3 或 Node >= 22。请安装受支持的运行环境。')
    host = '127.0.0.1' if args.host == '0.0.0.0' else args.host
    if ':' in host and not host.startswith('['):
        host = '[' + host + ']'
    url = f'http://{host}:{args.port}'
    print(f'\n留影 ClipNest 即将启动：{url}\n关闭此窗口或按 Ctrl+C 停止服务。\n', flush=True)
    if not args.no_browser:
        timer = threading.Timer(1.2, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()
    try:
        return subprocess.call([str(python), '-m', 'uvicorn', 'app.main:app',
                                '--host', args.host, '--port', str(args.port),
                                '--workers', '1', '--no-proxy-headers'])
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
