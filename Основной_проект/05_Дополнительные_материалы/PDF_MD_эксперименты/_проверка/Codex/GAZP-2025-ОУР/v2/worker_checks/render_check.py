from playwright.sync_api import sync_playwright
from pathlib import Path
import json
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True, executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", args=["--no-sandbox"])
 p=b.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
 p.goto((Path('result/_проверка/preview.html').resolve()).as_uri(),wait_until='load')
 p.screenshot(path='result/_проверка/render_top.png')
 p.locator('#pdf-page-144').scroll_into_view_if_needed()
 # Open the source-column representation, leaving original images collapsed.
 p.evaluate('''() => { const a=document.getElementById('pdf-page-144'); let e=a.nextElementSibling; while(e && !(e.tagName==='A' && e.id.startsWith('pdf-page-'))){if(e.tagName==='DETAILS' && e.querySelector('pre'))e.open=true; e=e.nextElementSibling;} }''')
 p.locator('#pdf-page-144').scroll_into_view_if_needed();p.screenshot(path='result/_проверка/render_144.png')
 result=p.evaluate('''() => ({brokenImages:[...document.images].filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.src),preCount:document.querySelectorAll('pre').length,hasHorizontalPre:[...document.querySelectorAll('pre')].every(e=>getComputedStyle(e).overflowX==='auto'),tableCount:document.querySelectorAll('table').length})''')
 Path('result/_проверка/render_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(result);b.close()
