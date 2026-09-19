"""Read-only local runtime check. Does not install packages or contact a server."""
import json
import re
import shutil
import subprocess
import sys


def probe(name, args, minimum=None):
    executable = shutil.which(name)
    if not executable:
        return {'name': name, 'ready': False, 'detail': 'Not installed / not on PATH'}
    try:
        result = subprocess.run([executable, *args], capture_output=True, text=True,
                                errors='replace', timeout=3)
        line = (result.stdout or result.stderr).splitlines()[0]
        match = re.search(r'(\d+)\.(\d+)', line)
        compatible = minimum is None or (match and tuple(map(int, match.groups())) >= minimum)
        return {'name': name, 'ready': bool(result.returncode == 0 and compatible), 'detail': line}
    except (OSError, subprocess.TimeoutExpired, IndexError) as error:
        return {'name': name, 'ready': False, 'detail': type(error).__name__}


def report():
    checks = [{'name': 'Python', 'ready': sys.version_info >= (3, 11), 'detail': sys.version.split()[0]},
              probe('ffmpeg', ['-version']), probe('ffprobe', ['-version']),
              probe('deno', ['--version'], (2, 3)), probe('node', ['--version'], (22, 0))]
    return {'processing': 'this-device', 'checks': checks,
            'ready': all(item['ready'] for item in checks[:3]) and any(item['ready'] for item in checks[3:])}


def main():
    result = report()
    if '--json' in sys.argv:
        print(json.dumps(result, indent=2))
    else:
        print('ClipNest local environment — no installation or network requests')
        for item in result['checks']:
            print(f"{'OK' if item['ready'] else 'CHECK'}  {item['name']}: {item['detail']}")
        print('Deno OR Node is required; you do not need both.')
        print('Ready. Run start-local.bat / start-local.sh.' if result['ready'] else
              'See docs/LOCAL_PROCESSING.md for the missing components.')
    return 0 if result['ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
