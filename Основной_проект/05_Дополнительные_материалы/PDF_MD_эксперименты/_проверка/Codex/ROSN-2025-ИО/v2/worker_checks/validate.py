import sys,json,re,pathlib,hashlib,collections
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
R=pathlib.Path('result');Q=R/'_проверка';md=(R/'report.md').read_text();src=json.load(open('source.json'))
assert re.findall(r'<!-- pdf_page: (\d+) -->',md)==[str(i) for i in range(1,69)]
body=MarkdownIt('commonmark',{'html':True}).render(md);soup=BeautifulSoup(body,'html.parser');ids={a['id'] for a in soup.find_all(id=True)}
for a in soup.find_all(href=True):
 if a['href'].startswith('#'):assert a['href'][1:] in ids,a
for img in soup.find_all('img'):assert (R/img['src']).is_file(),img
assert '\ufffd' not in md and '\x08' not in md
source_sha=hashlib.sha256(pathlib.Path(src['source_pdf']).read_bytes()).hexdigest();cov=json.load(open(Q/'native_coverage.json'));assert source_sha==cov['source_sha256']
preview='<!doctype html><html lang="ru"><meta charset="utf-8"><style>body{font:16px/1.5 sans-serif;margin:32px;max-width:1500px}table{border-collapse:collapse;display:block;overflow-x:auto;max-width:100%}td{border:1px solid #aaa;padding:6px;vertical-align:top;min-width:55px}img{max-width:100%}details{margin:20px 0}blockquote{color:#555;border-left:3px solid #bbb;padding-left:14px}</style>'+body+'</html>'
# Asset paths in preview are relative to its directory.
preview=preview.replace('src="assets/','src="../assets/');(Q/'preview.html').write_text(preview)
result={'physical_pages':68,'source_sha256':source_sha,'report_sha256':hashlib.sha256((R/'report.md').read_bytes()).hexdigest(),'all_page_markers_once_in_order':True,'all_internal_targets_exist':True,'all_image_files_exist':True,'unresolved_unicode_in_report':0,'tables':len(soup.find_all('table')),'images':len(soup.find_all('img')),'rendering':'pending'}
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True, executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome");page=browser.new_page(viewport={'width':1500,'height':1100});page.goto((Q/'preview.html').resolve().as_uri());page.screenshot(path=str(Q/'render_cover.png'))
  for n in [2,10,49,54,55,66]:
   page.locator('#pdf-page-'+str(n)).scroll_into_view_if_needed();page.screenshot(path=str(Q/('render_'+str(n)+'.png')))
  result['rendering']='Local Chromium loaded complete saved Markdown rendered as HTML; screenshots for cover and pages 2, 10, 49, 54, 55, 66. Visual inspection recorded separately.'
  browser.close()
except Exception as e:result['rendering_error']=str(e)
(Q/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
