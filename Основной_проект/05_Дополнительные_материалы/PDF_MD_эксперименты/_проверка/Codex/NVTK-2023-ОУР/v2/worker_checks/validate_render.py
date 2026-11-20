import sys,json,re,html
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
root=Path('result').resolve();text=(root/'report.md').read_text();pages=[int(x) for x in re.findall(r'<!-- pdf_page: (\d+) -->',text)];assert pages==list(range(1,139))
md=MarkdownIt('commonmark',{'html':True}).enable('table');body=md.render(text);soup=BeautifulSoup(body,'html.parser');missing=[]
for im in soup.select('img[src]'):
 if not (root/im['src']).is_file():missing.append(im['src'])
ids={x['id'] for x in soup.select('[id]')}
for a in soup.select('a[href]'):
 ref=a['href']
 if ref.startswith('#') and ref[1:] not in ids:missing.append(ref)
assert not missing,missing
style='body{font:16px/1.5 Arial,sans-serif;max-width:1250px;margin:32px auto;padding:20px}img{max-width:100%;height:auto}table{display:block;overflow-x:auto;border-collapse:collapse;font-size:13px;margin:18px 0}td,th{border:1px solid #ccc;padding:7px;vertical-align:top;min-width:55px}blockquote{background:#f6f6f6;padding:8px 20px}h6{font-size:24px}details{margin:10px 0}a{overflow-wrap:anywhere}'
preview=root/'_проверка'/'preview.html';preview.write_text('<!doctype html><meta charset="utf-8"><title>Рабочая конвертация</title><style>'+style+'</style>'+body.replace('src="assets/','src="../assets/'))
result={'physical_pages':len(pages),'page_order_valid':True,'local_assets':len(soup.select('img[src]')),'missing_references':missing,'html_tables':len(soup.select('table')),'rendered_preview':'_проверка/preview.html'}
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,args=['--disable-gpu','--no-sandbox'])
  page=browser.new_page(viewport={'width':1450,'height':1050});page.goto(preview.as_uri(),wait_until='load')
  result['browser_render']='success';result['broken_images']=page.locator('img').evaluate_all('(imgs)=>imgs.filter(i=>!i.complete||i.naturalWidth===0).length')
  for n in [1,109,133]:
   page.locator(f'#pdf-page-{n}').scroll_into_view_if_needed();page.screenshot(path=str(root/'_проверка'/f'render_{n:04}.png'))
  browser.close()
except Exception as e:result['browser_render']='unavailable: '+str(e)
(root/'_проверка'/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
