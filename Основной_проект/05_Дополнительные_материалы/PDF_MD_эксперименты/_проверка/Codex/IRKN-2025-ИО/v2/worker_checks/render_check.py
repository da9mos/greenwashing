import sys
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1600,'height':1000});page.goto((Path('result/_проверка/preview.html').resolve()).as_uri(),wait_until='domcontentloaded');page.screenshot(path='result/_проверка/render-start.png');page.locator('#pdf-page-200').scroll_into_view_if_needed();page.screenshot(path='result/_проверка/render-table.png');print('Rendered saved report; screenshots captured');browser.close()
