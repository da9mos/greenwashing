import sys,json
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from playwright.sync_api import sync_playwright
A=Path('result/_проверка').resolve()
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/Users/nikitachukreev/Library/Caches/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell')
 page=browser.new_page(viewport={'width':1440,'height':1050},device_scale_factor=1)
 page.goto((A/'preview.html').as_uri(),wait_until='load')
 results=page.evaluate('''() => ({headings:document.querySelectorAll('h1,h2,h3').length,tables:document.querySelectorAll('table').length,coordinateBlocks:document.querySelectorAll('pre').length,images:document.images.length,brokenImages:[...document.images].filter(x=>!x.complete||x.naturalWidth===0).map(x=>x.src)})''')
 for n in [1,12,110,133,135]:
  page.locator('#pdf-page-'+str(n)).scroll_into_view_if_needed()
  page.screenshot(path=str(A/f'render-{n}.png'))
 (A/'render-validation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
 print(results);browser.close()
