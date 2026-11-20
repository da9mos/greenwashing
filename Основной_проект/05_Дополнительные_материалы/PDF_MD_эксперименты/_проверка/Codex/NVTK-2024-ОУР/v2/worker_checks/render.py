import sys,json
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from playwright.sync_api import sync_playwright
ck=Path('result/_проверка').resolve()
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
 page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
 page.goto((ck/'preview.html').as_uri(),wait_until='load',timeout=60000)
 page.screenshot(path=str(ck/'preview-top.png'))
 last=page.locator('table').last;last.screenshot(path=str(ck/'preview-table-129.png'))
 metrics=page.evaluate('''() => ({images:document.images.length,brokenImages:[...document.images].filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.src),tables:document.querySelectorAll('table').length,bodyWidth:document.body.scrollWidth,viewportWidth:innerWidth})''')
 (ck/'render.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2));print(metrics)
 browser.close()
