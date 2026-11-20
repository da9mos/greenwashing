from pathlib import Path
import sys,json,hashlib,urllib.parse
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE/'tools'))
from render_results import CSS
AUDIT=Path(__file__).resolve().parent
rids=json.loads((AUDIT/'launch.json').read_text())['reports']
records={}
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 for rid in rids:
  source=BASE/'Codex'/rid.split('-')[0]/rid/'report.md'
  if not source.is_file():continue
  digest=hashlib.sha256(source.read_bytes()).hexdigest()
  out=AUDIT/'render'/rid;out.mkdir(parents=True,exist_ok=True)
  receipt=out/'render_check.json'
  if receipt.is_file():
   old=json.loads(receipt.read_text())
   if old.get('sha256')==digest:records[rid]=old;continue
  soup=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).enable('table').render(source.read_text()),'html.parser')
  for el in soup.find_all(['script','iframe','object','embed']):el.decompose()
  for el in soup.find_all(True):
   for attr in list(el.attrs):
    if attr.lower().startswith('on'):del el[attr]
  missing=[]
  for image in soup.find_all('img'):
   target=(source.parent/urllib.parse.unquote(image.get('src',''))).resolve()
   if target.is_file() and target.is_relative_to(source.parent.resolve()):image['src']=target.as_uri();image['loading']='lazy'
   else:missing.append(image.get('src'))
  for table in list(soup.find_all('table')):
   wrapper=soup.new_tag('div');wrapper['class']='scroll';table.wrap(wrapper)
  (out/'report.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+CSS+'</style>'+str(soup))
  page=browser.new_page(viewport={'width':1440,'height':1000})
  page.route('http://**/*',lambda r:r.abort());page.route('https://**/*',lambda r:r.abort())
  page.goto((out/'report.html').as_uri(),wait_until='domcontentloaded',timeout=120000)
  widths=[]
  for width in [1440,390]:
   page.set_viewport_size({'width':width,'height':1000});page.screenshot(path=str(out/f'width_{width}.png'))
   widths.append({'width':width,'document_overflow':page.evaluate('document.documentElement.scrollWidth>innerWidth')})
  record={'report_id':rid,'sha256':digest,'anchors':page.locator('[id^="pdf-page-"]').count(),'tables':page.locator('table').count(),'images':page.locator('img').count(),'missing_images':missing,'widths':widths,'scope':'Browser parsing and two viewport screenshots; not full PDF content verification'}
  receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');records[rid]=record;page.close();print(rid,record['anchors'],flush=True)
 browser.close()
(AUDIT/'render_summary.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
