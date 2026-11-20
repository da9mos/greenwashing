from pathlib import Path
from playwright.sync_api import sync_playwright
import json
A=Path('result/_проверка').resolve()
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True, executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
 page=browser.new_page(viewport={'width':1400,'height':1050},device_scale_factor=1)
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto((A/'report_preview.html').as_uri(),wait_until='load')
 page.evaluate('document.querySelectorAll("details").forEach(x => x.open = true)')
 page.wait_for_timeout(1000)
 result=page.evaluate('''() => ({images:document.images.length,failed_images:[...document.images].filter(x=>!x.complete||!x.naturalWidth).map(x=>x.src),page_anchors:document.querySelectorAll('a[id^="pdf-page-"]').length,html_tables:document.querySelectorAll('table').length,fixed_width_blocks:document.querySelectorAll('pre').length,scrolling_blocks:[...document.querySelectorAll('pre,div[style*="overflow"]')].filter(x=>x.scrollWidth>x.clientWidth).length})''')
 for n in [1,2,52,132,145,147]:
  page.locator(f'#pdf-page-{n}').scroll_into_view_if_needed();page.screenshot(path=str(A/f'render_{n:04}.png'))
 result['javascript_errors']=errors
 (A/'render_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2));browser.close()
