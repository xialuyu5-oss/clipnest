"""Check the built entry site's fallback and consent-tool download, without installing."""
import argparse
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import zipfile

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'test-output/local-checker')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(args.site.resolve())))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/'
    errors, unexpected_requests = [], []
    report = {'product': 'clipnest', 'protocol': 1, 'ready': False,
              'checks': [{'id': name, 'ready': name != 'ffmpeg'} for name in ['python', 'ffmpeg', 'javascript', 'extractor']]}
    mode = 'unreachable'

    def route(request):
        target = request.request.url
        if target == 'http://127.0.0.1:8000/local/environment':
            if mode == 'unreachable':
                request.abort('connectionrefused')
            else:
                request.fulfill(json=report, headers={'Access-Control-Allow-Origin': url.rstrip('/')})
        elif target.startswith('http://127.0.0.1:8000/?lang='):
            request.fulfill(content_type='text/html', body='<h1>Test-only local destination</h1>')
        elif target.startswith(url):
            request.continue_()
        else:
            unexpected_requests.append(target)
            request.abort()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.getenv('CHROMIUM_EXECUTABLE') or None, headless=True)
            context = browser.new_context(viewport={'width': 1440, 'height': 1050}, accept_downloads=True)
            context.route('**/*', route)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(url)
            page.locator('[data-state="unreachable"]').wait_for()
            assert page.locator('html').get_attribute('lang') == 'en'
            assert not page.locator('#checks').is_visible()
            assert page.locator('#checks li').count() == 0
            assert page.locator('#setup-package').is_visible()
            assert page.locator('#pc-package').is_visible()
            for width in [1440, 320]:
                page.set_viewport_size({'width': width, 'height': 1050})
                for locale in ['en', 'zh-CN', 'zh-TW', 'ja', 'ko', 'es', 'fr', 'de', 'pt', 'ru', 'ar', 'hi']:
                    page.select_option('#language', locale)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, locale)
                    assert page.locator('#setup-package').bounding_box()['height'] >= 44
                    if locale == 'ar':
                        assert page.locator('html').get_attribute('dir') == 'rtl'
                page.select_option('#language', 'zh-CN')
                page.screenshot(path=str(args.output / f'checker-fallback-{width}.png'), full_page=True)

            with page.expect_download() as download_info:
                page.locator('#setup-package').click()
            download = download_info.value
            target = args.output / download.suggested_filename
            download.save_as(target)
            assert target.read_bytes() == (args.site / 'downloads/clipnest-windows-setup.zip').read_bytes()
            with zipfile.ZipFile(target) as package:
                assert 'ClipNest-Setup/check-and-setup.bat' in package.namelist()
                assert 'ClipNest-Setup/README.zh-CN.md' in package.namelist()

            mode = 'report'
            page.locator('#retry').click()
            page.locator('#retry:not([disabled])').wait_for()
            page.locator('[data-state="missing"]').wait_for()
            assert page.locator('#checks li').count() == 4
            assert page.locator('#checks li').filter(has_text='FFmpeg').locator('a').count() == 1
            assert page.locator('#setup-package').is_visible()
            assert not page.locator('#pc-package').is_visible()

            report['checks'] = [{'id': c['id'], 'ready': c['id'] != 'extractor'} for c in report['checks']]
            page.locator('#retry').click()
            page.locator('#retry:not([disabled])').wait_for()
            assert not page.locator('#setup-package').is_visible(), 'Do not offer system installers for missing project packages'

            report['ready'] = True
            for check in report['checks']:
                check['ready'] = True
            page.locator('#retry').click()
            page.wait_for_url('http://127.0.0.1:8000/?lang=zh-CN')
            assert not errors, errors
            assert not unexpected_requests, unexpected_requests
            context.close()
            browser.close()
        result = {'unreachable_hides_unchecked_rows': True, 'checker_download_matches_built_zip': True,
                  'checker_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                  'locales': 12, 'widths': [1440, 320], 'verified_missing_components': True,
                  'extractor_does_not_offer_system_installer': True, 'ready_handoff': 'simulated report and destination',
                  'page_errors': errors, 'unexpected_requests': unexpected_requests, 'real_installs_performed': False}
        (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result, indent=2))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


if __name__ == '__main__':
    main()
