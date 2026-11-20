from pathlib import Path
import sys,re,json,hashlib
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];s=(root/'report.md').read_text();p=json.loads((root/'_проверка/pages.json').read_text())['pages']
nums=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',s)));assert nums==list(range(1,190));assert len(p)==189
soup=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).enable('table').render(s),'html.parser')
missing=[]
for im in soup.find_all('img'):
 if not (root/im['src']).is_file():missing.append(im['src'])
anchors={x['id'] for x in soup.find_all(id=True)}
broken=[a['href'] for a in soup.find_all('a',href=True) if a['href'].startswith('#') and a['href'][1:] not in anchors]
assert not missing and not broken
controls=[(i,ord(c)) for i,c in enumerate(s) if ord(c)<32 and c not in '\n\r\t'];assert not controls
body=str(soup)
css='body{font:16px sans-serif;line-height:1.45;margin:30px;max-width:1600px} table{border-collapse:collapse;display:block;overflow-x:auto;max-width:100%}td,th{border:1px solid #aaa;padding:8px;min-width:130px;vertical-align:top}img{max-width:100%}blockquote{color:#555;background:#eee;padding:10px}'
preview=root/'_проверка/preview.html';preview.write_text('<!doctype html><meta charset="utf-8"><base href="../"><style>'+css+'</style>'+body)
result={'pages':len(nums),'page_order_ok':True,'assets_references':len(soup.find_all('img')),'missing_assets':missing,'broken_internal_links':broken,'control_characters':len(controls),'checked_pages':[x['pdf_page'] for x in p if x['review_status']=='checked'],'pending_pages':sum(x['review_status']=='pending' for x in p),'source_sha256':hashlib.file_digest(open(json.load(open(root.parent/'source.json'))['source_pdf'],'rb'),'sha256').hexdigest(),'report_sha256':hashlib.sha256(s.encode()).hexdigest(),'render_status':'pending'}
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,args=['--no-sandbox','--disable-gpu'])
  page=browser.new_page(viewport={'width':1500,'height':1050});page.goto(preview.as_uri());page.locator('#pdf-page-154').scroll_into_view_if_needed();page.screenshot(path=str(root/'_проверка/render_page154.png'));result['render_status']='local Chrome HTML render, page 154 screenshot';browser.close()
except Exception as e:result['render_status']='unavailable: '+str(e)[:600]
(root/'_проверка/validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
