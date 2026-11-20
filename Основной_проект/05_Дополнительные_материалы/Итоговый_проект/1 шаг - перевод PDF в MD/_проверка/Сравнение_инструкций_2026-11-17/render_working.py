from pathlib import Path
import sys,json,hashlib,urllib.parse
sys.path.insert(0,'/private/tmp/sber-diff-libs')
sys.path.insert(0,str(Path('11_Проект_Сбер/2_итерация/Тесты_PDF_в_MD_DeepSeek_Codex/tools').resolve()))
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from render_results import CSS
CSS += "td,th{overflow-wrap:normal;word-break:normal}"

base=Path(__file__).resolve().parent
sources=sorted((base/'final').glob('*/codex_working.md'))+sorted((base/'final_retry75').glob('*/codex_working.md'))
if len(sources)!=13: raise SystemExit(f'Expected 13 reviewed working files, found {len(sources)}')
records=[]
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 for source in sources:
  out=base/'rendered'/source.parent.name;out.mkdir(parents=True,exist_ok=True)
  soup=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).enable('table').render(source.read_text()),'html.parser')
  missing=[]
  for el in soup.find_all(['script','iframe','object','embed']):el.decompose()
  for el in soup.find_all(True):
   for key in list(el.attrs):
    if key.lower().startswith('on'):del el[key]
  for img in soup.find_all('img'):
   path=(source.parent/urllib.parse.unquote(img.get('src',''))).resolve()
   if path.is_file() and path.is_relative_to(source.parent.resolve()):img['src']=path.as_uri()
   else:missing.append(str(img))
  for table in list(soup.find_all('table')):
   div=soup.new_tag('div');div['class']='scroll';table.wrap(div)
  html=out/'report.html';html.write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+CSS+'</style>'+str(soup))
  page=browser.new_page(viewport={'width':1440,'height':1000})
  page.route('http://**/*',lambda r:r.abort());page.route('https://**/*',lambda r:r.abort())
  page.goto(html.as_uri(),wait_until='load')
  widths=[]
  for width in [1440,390]:
   page.set_viewport_size({'width':width,'height':1000})
   old=out/f'full_{width}.png'
   if old.exists():old.rename(out/f'full_{width}_unreliable_capture.png')
   page.evaluate('window.scrollTo(0,0)')
   page.locator('.scroll').evaluate_all('(xs)=>xs.forEach(x=>x.scrollLeft=0)')
   height=page.evaluate('document.documentElement.scrollHeight')
   tiles=[]
   for index,y in enumerate(range(0,height,900)):
    page.evaluate('(y)=>window.scrollTo(0,y)',y);page.wait_for_timeout(80)
    actual=page.evaluate('window.scrollY')
    filename=f'tile_{width}_{index:03d}.png';page.screenshot(path=str(out/filename))
    tiles.append({'path':filename,'requested_y':y,'actual_y':actual})
   for i in range(page.locator('.scroll').count()):
    box=page.locator('.scroll').nth(i)
    size=box.evaluate('(x)=>({wide:x.scrollWidth>x.clientWidth,top:x.getBoundingClientRect().top+scrollY,height:x.clientHeight,client:x.clientWidth,scroll:x.scrollWidth})')
    if size['wide']:
     max_x=size['scroll']-size['client']
     offsets=sorted(set([0,max_x]+list(range(0,max_x,max(1,int(size['client']*.9))))))
     for offset in offsets:
      box.evaluate('(x,left)=>x.scrollLeft=left',offset)
      for index,y in enumerate(range(int(size['top']),int(size['top']+size['height']),900)):
       page.evaluate('(y)=>window.scrollTo(0,y)',y);page.wait_for_timeout(80)
       filename=f'table_x{offset}_{width}_{i}_{index:03d}.png';page.screenshot(path=str(out/filename))
       tiles.append({'path':filename,'table':i,'scroll_left':box.evaluate('(x)=>x.scrollLeft'),'actual_y':page.evaluate('scrollY')})
     box.evaluate('(x)=>x.scrollLeft=0')
   (out/f'tiles_{width}.json').write_text(json.dumps(tiles,ensure_ascii=False,indent=2)+'\n')
   widths.append({'width':width,'page_overflow':page.evaluate('document.documentElement.scrollWidth>innerWidth'),'scroll_tables':page.locator('.scroll').evaluate_all('(xs)=>xs.map(x=>{x.scrollLeft=x.scrollWidth;return {client:x.clientWidth,scroll:x.scrollWidth,reached:x.scrollLeft}})')})
  text=page.locator('body').inner_text();(out/'displayed_text.txt').write_text(text)
  records.append({'report':source.parent.name,'path':str(source),'output_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'missing_images':missing,'images_loaded':page.locator('img').evaluate_all('(xs)=>xs.every(x=>x.complete&&x.naturalWidth>0)'),'widths':widths,'displayed_text':str(out/'displayed_text.txt'),'scope':'full-page browser artifacts and technical rendering checks; source semantics reviewed separately; screenshots alone do not certify all cells'})
  page.close()
 browser.close()
(base/'render_summary.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
assert not any(r['missing_images'] or not r['images_loaded'] or any(x['page_overflow'] for x in r['widths']) for r in records)
print('Captured viewport tiles for 13 working files at 1440 and390; full-page captures retained as unreliable evidence')
