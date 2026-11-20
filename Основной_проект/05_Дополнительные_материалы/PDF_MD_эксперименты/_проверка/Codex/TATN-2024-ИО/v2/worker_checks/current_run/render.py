import sys,json
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from playwright.sync_api import sync_playwright
base=Path('result/_проверка/current_run').resolve()
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,args=['--no-sandbox','--disable-gpu'])
  page=browser.new_page(viewport={'width':1500,'height':1100},device_scale_factor=1)
  page.goto((base/'preview.html').as_uri(),wait_until='load')
  results=[]
  for n in [2,67,165,178]:
   page.locator(f'#pdf-page-{n}').evaluate('(e)=>e.scrollIntoView()')
   page.screenshot(path=str(base/f'render_page_{n}.png'))
   results.append({'page':n,'screenshot':f'render_page_{n}.png'})
  browser.close()
  j=json.load(open(base/'validation.json'));j['render_screenshot_completed']=True;j['rendered_samples']=[2,67,165,178];(base/'validation.json').write_text(json.dumps(j,ensure_ascii=False,indent=2))
  print(results)
except Exception as e:
 (base/'render_limitation.txt').write_text(str(e));print(type(e).__name__,str(e)[:1500])
