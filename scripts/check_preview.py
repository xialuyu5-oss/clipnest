import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
out = Path(os.getenv('CLIPNEST_TEST_OUTPUT', str(ROOT / 'test-output')))
out.mkdir(parents=True, exist_ok=True)
html=(ROOT/'ClipNest-界面预览.html').read_text(encoding='utf-8')
errors=[]; results={}
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.getenv('CHROMIUM_EXECUTABLE') or None,
        headless=True, args=['--no-sandbox'] if os.getenv('CHROMIUM_NO_SANDBOX') == '1' else [])
    ctx=browser.new_context(viewport={'width':1440,'height':1050},device_scale_factor=1,accept_downloads=True)
    page=ctx.new_page();page.set_default_timeout(5000);page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(html,wait_until='load')
    # The interface defaults to English (v1.2.0); storage is unavailable on about:blank, so no saved language applies.
    page.wait_for_function('document.querySelector("#service-text").textContent === "Offline preview"')
    page.screenshot(path=str(out/'clipnest-desktop.png'),full_page=True)
    results['desktop_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.select_option('#language-select','zh-CN')
    page.wait_for_function('document.querySelector("#service-text").textContent === "离线界面预览"')
    results['embedded_catalog_switch']=page.evaluate('document.documentElement.lang')=='zh-CN'
    page.select_option('#language-select','ar')
    results['rtl_layout']=page.evaluate('document.documentElement.dir')=='rtl'
    page.select_option('#language-select','en')
    page.wait_for_function('document.querySelector("#service-text").textContent === "Offline preview"')
    page.locator('#video-url').fill('https://www.youtube.com/watch?v=example')
    page.locator('#analyze-button').click();page.locator('#analyze-error').wait_for(state='visible')
    results['preview_does_not_fake_platform_parsing']='offline preview' in page.locator('#analyze-error').inner_text().lower()
    page.locator('#clear-input').click()
    page.locator('#demo-button').click();page.locator('#result-section').wait_for(state='visible')
    results['quality_count']=page.locator('.quality-option').count()
    results['consent_required']=page.locator('#download-button').is_disabled()
    page.locator('input[name="quality"][value="demo-480"]').locator('..').click()
    page.locator('#rights-confirmed').check();page.locator('#download-button').click()
    page.locator('#confirm-download-button').click()
    page.locator('.save-button').first.wait_for()
    with page.expect_download() as di:
        page.locator('.save-button').first.click()
    d=di.value;d.save_as(str(out/'clipnest-browser-demo-480.mp4'))
    results['browser_saved_filename']=d.suggested_filename
    results['browser_saved_bytes']=(out/'clipnest-browser-demo-480.mp4').stat().st_size
    page.evaluate("document.documentElement.style.scrollBehavior='auto';scrollTo(0,0)")
    page.wait_for_timeout(500)
    page.screenshot(path=str(out/'clipnest-result.png'),full_page=True)
    page.locator('[data-dialog="platforms-dialog"]').first.click()
    results['platform_count']=page.locator('.platform-item').count()
    page.keyboard.press('Escape')
    page.locator('#theme-button').click()
    results['dark_theme']=page.locator('html').get_attribute('data-theme')=='dark'
    page.evaluate("scrollTo(0,0)")
    page.wait_for_timeout(500)
    page.screenshot(path=str(out/'clipnest-dark.png'),full_page=True)
    page.locator('#theme-button').click()
    page.locator('[aria-label="Delete task and temporary files"]').first.click()
    page.locator('#empty-state').wait_for(state='visible');results['delete_job']=True
    phone=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True)
    m=phone.new_page();m.set_default_timeout(5000);m.on('pageerror',lambda e:errors.append(str(e)))
    m.set_content(html,wait_until='load')
    m.screenshot(path=str(out/'clipnest-mobile.png'),full_page=True)
    results['mobile_no_horizontal_overflow']=m.evaluate('document.documentElement.scrollWidth <= innerWidth')
    m.locator('#demo-button').click();m.locator('#result-section').wait_for(state='visible')
    m.screenshot(path=str(out/'clipnest-mobile-result.png'),full_page=True)
    results['mobile_result_no_overflow']=m.evaluate('document.documentElement.scrollWidth <= innerWidth')
    m.set_viewport_size({'width':320,'height':740})
    results['320px_no_overflow']=m.evaluate('document.documentElement.scrollWidth <= innerWidth')
    browser.close()
results['page_errors']=errors
(out/'clipnest-browser-tests.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2))

assert not errors, errors
assert all(value for key, value in results.items() if key != 'page_errors'), results
assert results['quality_count'] == 3
assert results['platform_count'] == 10
assert results['browser_saved_bytes'] == (ROOT / 'web/assets/demo-480.mp4').stat().st_size
