import sys,re,json,hashlib,collections,html
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-diff-libs']
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
r=Path(__file__).resolve().parents[1];p=r/'_проверка';reg=json.loads((p/'pages.json').read_text());s=(r/'report.md').read_text()
# Printed URL recovered from the source image, not from guessing an annotation.
parts=re.split(r'<!-- pdf_page: (\d+) -->',s);i=parts.index('18')+1;t=parts[i]
u='https://www.eia.gov/totalenergy/data/monthly/pdf/mer.pdf'
if 'href="'+u+'"' not in t:
 t=t.replace('> Служебная информация: ссылки исходного PDF','> Служебная информация: ссылки исходного PDF\n\n[Адрес EIA, прочитанный в примечании источника]('+u+')',1);parts[i]=t
s=''.join(parts[j] if j%2==0 else '<!-- pdf_page: '+parts[j]+' -->' for j in range(len(parts)));(r/'report.md').write_text(s)
soup=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).enable('table').render(s),'html.parser')
image_refs=[x.get('src') for x in soup.find_all('img')];missing=[v for v in image_refs if not (r/v).is_file()]
anchors={x.get('id') for x in soup.find_all(id=True)};broken=[x['href'] for x in soup.find_all('a',href=True) if x['href'].startswith('#') and x['href'][1:] not in anchors]
sha=hashlib.sha256(s.encode()).hexdigest();table_status=[]
for j in range(1,len(parts),2):
 n=int(parts[j]);rec=reg['pages'][n-1];sp=BeautifulSoup(parts[j+1],'html.parser');tables=sp.find_all('table')
 rec['display_review_status']='pending';rec['display_review_issue']='Chrome завершился при запуске SIGABRT; снимки 1440/390 не получены.'
 rec['issues']=[x for x in rec['issues'] if 'шапка/заголовок частично вне' not in x]
 if n in [5,7,15,38,45,66,87,92,93,94]:rec['header_structure_refined']=True
 for k,ta in enumerate(tables,1):
  legend=(n,k) in [(14,2),(55,1),(82,1),(84,1)]
  table_status.append({'pdf_page':n,'table':k,'rows':len(ta.find_all('tr')),'header_in_table':bool(ta.find('th')),'is_chart_legend':legend,'source_review_status':'checked' if n in [9,13] else 'pending'})
  if not ta.find('th') and not legend:rec['issues'].append(f'Таблица {k}: требуется сверка шапки и принадлежности строк/колонок по оригиналу.')
# Preserve baseline diagnostics without interpreting their glyph inventory as final review.
coverage=json.loads((p/'native_coverage.json').read_text());coverage['report_path']='report.native.md';coverage['scope']='Учёт глифов механического кандидата report.native.md; не подтверждает порядок чтения и связи итогового report.md.'
coverage['final_report_sha256']=sha;coverage['final_source_checked_pages']=[1,10,69,86];coverage['final_source_review_pending_pages']=[x['pdf_page'] for x in reg['pages'] if x['review_status']=='pending']
(p/'native_coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n')
(p/'pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n');(p/'table_structure.json').write_text(json.dumps(table_status,ensure_ascii=False,indent=2)+'\n')
# Recreate HTML for the exact final Markdown without making a second failed browser launch.
for im in soup.find_all('img'):im['src']='../../'+im['src']
for ta in list(soup.find_all('table')):
 wrapper=soup.new_tag('div');wrapper['class']='scroll';ta.wrap(wrapper)
css='body{font:16px/1.6 system-ui,sans-serif;max-width:1100px;margin:auto;padding:24px;color:#182230}p{margin:0 0 1em}img{max-width:100%;height:auto}img[width="12"]{width:12px;height:12px}table{border-collapse:collapse;font-size:14px;min-width:600px}th,td{border:1px solid #b7c5ce;padding:8px;vertical-align:top}th{background:#eaf0f3}.scroll{overflow-x:auto;max-width:100%}blockquote{border-left:3px solid #94a3b8;padding-left:16px;color:#475569}details{margin:24px 0}a{overflow-wrap:anywhere}'
(p/'render/report.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+css+'</style><body>'+str(soup)+'</body></html>')
check={'report_sha256':sha,'html_generated':True,'browser_render_status':'blocked','error':'Playwright BrowserType.launch TargetClosedError; Chrome process SIGABRT.','screenshots_created':False,'widths_requested':[1440,390],'missing_assets':missing,'broken_internal_links':broken,'scope':'HTML собран. Визуальная проверка отображения в браузере не выполнена.'}
(p/'render/render_check.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n')
(p/'progress.json').write_text(json.dumps({'last_page':96,'conversion_complete':True,'source_review_complete':False,'source_checked_pages':[1,10,69,86],'source_review_pending_pages':coverage['final_source_review_pending_pages'],'render_status':'blocked','report_sha256':sha},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'pages':len(reg['pages']),'review_statuses':dict(collections.Counter(x['review_status'] for x in reg['pages'])),'tables':len(table_status),'image_references':len(image_refs),'missing_assets':missing,'broken_links':broken,'report_sha256':sha},ensure_ascii=False))
