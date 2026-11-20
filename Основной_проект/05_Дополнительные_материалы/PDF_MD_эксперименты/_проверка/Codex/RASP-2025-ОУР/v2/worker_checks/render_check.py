import sys,pathlib,json
sys.path.insert(0,'/private/tmp/sber-diff-libs');from playwright.sync_api import sync_playwright
base=pathlib.Path('result/_проверка').resolve();records=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,args=['--disable-gpu','--no-first-run','--disable-background-networking'])
 page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
 page.route('http://**/*',lambda route:route.abort());page.route('https://**/*',lambda route:route.abort())
 for f in sorted(base.glob('preview_[0-9]*.html')):
  page.goto(f.as_uri());page.screenshot(path=str(f.with_suffix('.png')),full_page=True)
  records.append({'pdf_page':int(f.stem.split('_')[1]),'screenshot':f.with_suffix('.png').name,'tables':page.locator('table').count(),'rendered_text_chars':len(page.locator('body').inner_text()),'body_scroll_width':page.evaluate('document.body.scrollWidth')})
 page.goto((base/'preview.html').as_uri());page.screenshot(path=str(base/'preview_top.png'))
 records.append({'full_report_loaded':True,'images':page.locator('img').count(),'tables':page.locator('table').count(),'page_anchors':page.locator('[id^="pdf-page-"]').count()})
 browser.close()
(base/'render_checks.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print('Rendered',len(records)-1,'reviewed page bodies and full report HTML')
