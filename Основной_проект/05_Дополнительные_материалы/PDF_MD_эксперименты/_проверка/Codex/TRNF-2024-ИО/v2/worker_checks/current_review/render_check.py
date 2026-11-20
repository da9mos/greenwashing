import sys,json
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from playwright.sync_api import sync_playwright
folder=Path('result/_проверка/current_review').resolve()
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True, executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
 page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
 page.goto((folder/'rendered.html').as_uri(),wait_until='load')
 results=[]
 for n in [9,30,31,42,53,54,67,68,69,70,71,103,144,165,176,177,184,185,190,194,195,228,241,243,244,254,260]:
  page.locator(f'#pdf-page-{n}').scroll_into_view_if_needed();page.screenshot(path=str(folder/f'render-{n}.png'))
  results.append({'page':n,'screenshot':f'render-{n}.png'})
 (folder/'render_checks.json').write_text(json.dumps(results,indent=2))
 browser.close()
