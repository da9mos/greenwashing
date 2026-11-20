import sys
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True,executable_path="/Users/nikitachukreev/Library/Caches/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell")
 p=b.new_page(viewport={'width':1450,'height':1100},device_scale_factor=1)
 p.goto(Path('result/_проверка/preview.html').resolve().as_uri())
 for n in [7,11,26,29,114,143]:
  p.locator(f'#pdf-page-{n}').scroll_into_view_if_needed();p.screenshot(path=f'result/_проверка/render_{n:04}.png')
 print(p.evaluate('({tables:document.querySelectorAll("table").length,images:document.querySelectorAll("img").length,anchors:document.querySelectorAll("a[id]").length,brokenImages:[...document.images].filter(i=>!i.complete||i.naturalWidth===0).length})'))
 b.close()
