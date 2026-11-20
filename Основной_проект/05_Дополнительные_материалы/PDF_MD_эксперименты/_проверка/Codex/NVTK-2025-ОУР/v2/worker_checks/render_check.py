import sys,json
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path="/Users/nikitachukreev/Library/Caches/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell")
 page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
 page.goto((Path('result/_проверка/preview.html').resolve()).as_uri(),wait_until='load')
 results={}
 for n in [1,97,117]:
  node=page.locator(f'#pdf-page-{n}');node.scroll_into_view_if_needed();page.evaluate('(el)=>window.scrollTo(0,el.getBoundingClientRect().top+window.scrollY-25)',node.element_handle());page.screenshot(path=f'result/_проверка/render-{n}.png');results[str(n)]='rendered'
 results['broken_images']=page.locator('img').evaluate_all('(imgs)=>imgs.filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.src)')
 results['internal_links_missing_targets']=page.locator('a[href^="#"]').evaluate_all('(as)=>as.filter(a=>!document.getElementById(a.getAttribute("href").slice(1))).map(a=>a.href)')
 results['tables']=page.locator('table').count();results['images']=page.locator('img').count()
 Path('result/_проверка/render_validation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(results);browser.close()
