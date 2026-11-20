import sys,json
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from playwright.sync_api import sync_playwright
root=Path('result/_проверка').resolve()
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1600,'height':1100},device_scale_factor=1)
 page.goto((root/'preview.html').as_uri(),wait_until='load')
 for n in [1,54,112,115,133]:
  page.locator(f'#pdf-page-{n}').scroll_into_view_if_needed();page.screenshot(path=str(root/f'render-{n:04}.png'))
 print({'images':page.locator('img').count(),'broken_images':page.locator('img').evaluate_all('(xs)=>xs.filter(x=>!x.complete || !x.naturalWidth).length'),'pre_blocks':page.locator('pre').count()})
 browser.close()
