from pathlib import Path
import sys,re,json
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1]
s=(root/'report.md').read_text();sections=[]
for n,t in re.findall(r'<!-- pdf_page: (\d+) -->(.*?)(?=<!-- pdf_page:|\Z)',s,re.S):
 out=MarkdownIt('commonmark',{'html':True}).enable('table').render(t)
 out=out.replace('src="assets/','src="../assets/')
 out=out.replace('<table>','<div class="wide"><table>').replace('</table>','</table></div>')
 sections.append(f'<section id="review-{n}"><div class="page-label">Физическая страница {n}</div>'+out+'</section>')
css='body{font:16px/1.5 Arial,sans-serif;margin:32px;color:#17212c}section{margin-bottom:80px;border-top:2px solid #567;padding-top:20px}p{margin:10px 0}th,td{padding:8px;border:1px solid #b8c1ca;vertical-align:top;min-width:85px}table{border-collapse:collapse;min-width:70%}.wide{overflow-x:auto;max-width:100%;margin:20px 0}img{max-width:100%}.page-label{font-size:12px;color:#567}details{margin:15px 0}sup{font-size:.7em}'
(root/'_проверка/preview.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Годовой отчет 2025 — проверка конвертации</title><style>'+css+'</style><h1>ГОДОВОЙ ОТЧЕТ 2025</h1>'+''.join(sections)+'</html>')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 page=browser.new_page(viewport={'width':1600,'height':1100})
 page.route('**/*',lambda route:route.continue_() if route.request.url.startswith(('file:','data:')) else route.abort())
 page.goto((root/'_проверка/preview.html').as_uri(),wait_until='load')
 for n in [1,2,3,60,104,188]:
  loc=page.locator(f'#review-{n}');loc.screenshot(path=str(root/f'_проверка/render_{n:04}.png'),timeout=60000)
 print('rendered',page.locator('section').count(),'sections',page.locator('table').count(),'tables')
 print('page errors',page.evaluate('Array.from(document.images).filter(x=>!x.complete || x.naturalWidth===0).map(x=>x.src)'))
 browser.close()
