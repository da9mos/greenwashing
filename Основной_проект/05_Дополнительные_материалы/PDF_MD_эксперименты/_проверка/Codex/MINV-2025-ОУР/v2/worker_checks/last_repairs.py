from pathlib import Path
import re,json,hashlib,sys
r=Path('result');f=r/'report.md';s=f.read_text();start=s.index('<!-- pdf_page: 183 -->');end=s.index('<!-- pdf_page: 184 -->');t=s[start:end]
for a,b in [('1115035','115035'),('какиелибо','какие-либо'),('п. 5 cr. 2','п. 5 ст. 2'),('CPO ААС','СРО ААС'),('применимых законодательных и нормативных требований\n','применимых законодательных и нормативных требований.\n'),('включенные в Отчет,','включенные в Отчет.'),('Садовническая наб,','Садовническая наб.,')]:t=t.replace(a,b)
t=t.replace('НОВЫЕ ВЫЗОВЫ Факс:','Факс:').replace('НОВЫЕ РЕШЕНИЯ ОГРН:','ОГРН:')
t=t.replace('ООО «Б1 – Аудит»\n','Б1 — НОВЫЕ ВЫЗОВЫ, НОВЫЕ РЕШЕНИЯ\n\nООО «Б1 – Аудит»\n',1)
t=t.replace('КПП: 770501001\n','КПП: 770501001\n\n').replace('www.b1.ru\n','www.b1.ru\n\n')
t=t.replace('за 2025 год\nАкционерам','за 2025 год\n\nАкционерам')
t=t.replace('\n&gt;','\n\n-')
t=t.replace('\nОтдельные наблюдения относительно некоторых\nаспектов выполненного задания\n','\n\n### Отдельные наблюдения относительно некоторых аспектов выполненного задания\n\n')
t=t.replace('\nЛежанкова Елена Николаевна,','\n\nЛежанкова Елена Николаевна,').replace('\n7 мая 2026 г.','\n\n7 мая 2026 г.')
# Keep ordinary line wraps as spaces, but delineate original paragraphs and list items.
for phrase in ['В рамках настоящего задания','Кроме того, руководство','МСЗОУ 3000 требует','Мы соблюдаем требования','Хотя мы принимали','На основании п. 5','Задание, обеспечивающее ограниченную','Наши процедуры включали:','Выполненное задание, обеспечивающее','Мы полагаем, что','Запись внесена в Единый','Местонахождение:','Общество с ограниченной ответственностью «Б1 - Аудит» является']:
 t=t.replace('\n'+phrase,'\n\n'+phrase)
s=s[:start]+t+s[end:];f.write_text(s)
h=hashlib.sha256(s.encode()).hexdigest()
for name in ['native_coverage.json','integrity.json']:
 p=r/'_проверка'/name;d=json.loads(p.read_text());d['final_report_sha256' if name=='native_coverage.json' else 'report_sha256']=h;p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
# Refresh HTML using the same Markdown parser and CSS, without claiming a successful Chrome render.
sys.path[:0]=['/private/tmp/sber-diff-libs',str(Path(json.load(open('source.json'))['index']).parents[3]/'tools')]
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
import importlib.util
source=json.load(open('source.json'));tools_dir=Path(source['index']).parents[3]/'tools'
spec=importlib.util.spec_from_file_location('render_results',tools_dir/'render_results.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
soup=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).enable('table').render(s),'html.parser')
for img in soup.find_all('img'):img['src']=(r/img['src']).resolve().as_uri();img['loading']='lazy'
for table in list(soup.find_all('table')):
 wrapper=soup.new_tag('div');wrapper['class']='scroll';table.wrap(wrapper)
(r/'_проверка/render/report.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+mod.CSS+'</style>'+str(soup))
(r/'_проверка/render/render_check.json').write_text(json.dumps({'report_sha256':h,'html_created':True,'browser_render_status':'blocked','error':'Chrome exited on launch: SIGABRT / Playwright TargetClosedError; process kill EPERM in managed sandbox.','screenshots_created':False,'widths_1440_390_reviewed':False,'scope':'HTML generated; browser appearance NOT verified'},ensure_ascii=False,indent=2)+'\n')
print('Final hash',h,'tables',len(soup.find_all('table')))
