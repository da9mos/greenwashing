import sys,json
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parent
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,args=['--disable-background-networking','--disable-component-update'])
 page=browser.new_page(viewport={'width':1400,'height':1000},device_scale_factor=1)
 page.route('https://**/*',lambda route:route.abort());page.route('http://**/*',lambda route:route.abort())
 page.goto((root/'preview.html').as_uri(),wait_until='load')
 results={'title':page.title(),'anchors':page.locator('a[id^="pdf-page-"]').count(),'images':page.locator('img').count(),'tables':page.locator('table').count()}
 for n in [13,15,76,77,78,79]:
  # Review rendered text and table block above original page reference.
  page.locator(f'#pdf-page-{n}').scroll_into_view_if_needed();page.evaluate(f'document.getElementById("pdf-page-{n}").scrollIntoView()')
  page.screenshot(path=str(root/f'render_page_{n:04}.png'))
 results['broken_images']=page.locator('img').evaluate_all('(imgs)=>imgs.filter(i=>i.complete && i.naturalWidth===0).map(i=>i.src)')
 (root/'render_check.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(results)
 browser.close()
