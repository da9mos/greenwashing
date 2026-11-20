from playwright.sync_api import sync_playwright
from pathlib import Path
import json
root=Path('result/_проверка').resolve()
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'],timeout=20000)
 page=b.new_page(viewport={'width':1440,'height':1100});page.goto((root/'rendered.html').as_uri(),wait_until='load',timeout=60000)
 print(page.locator('img').count(),page.locator('pre').count())
 for n in [1,90,114]:
  page.locator(f'#pdf-page-{n}').scroll_into_view_if_needed();page.screenshot(path=str(root/f'render-{n}.png'))
 broken=page.locator('img').evaluate_all('(xs)=>xs.filter(x=>!x.complete||x.naturalWidth===0).length');assert broken==0
 b.close()
 x=json.load(open(root/'validation.json'));x['visual_render_check']='Browser render and screenshots pages 1, 90, 114; no broken images. Not a full content review.';(root/'validation.json').write_text(json.dumps(x,ensure_ascii=False,indent=2))
