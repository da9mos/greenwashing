from pathlib import Path
import sys,json,re,hashlib,collections
import fitz
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
r=Path(__file__).resolve().parents[1];s=(r/'report.md').read_text();src=json.load(open('source.json'));d=fitz.open(src['source_pdf']);reg=json.load(open(r/'_проверка/pages.json'))
for row,p in zip(reg['pages'],d):
 labels=[]
 for b in p.get_text('dict')['blocks']:
  for line in b.get('lines',[]):
   t=''.join(x['text'] for x in line['spans']).strip()
   if line['bbox'][1]>p.rect.height*.94 and re.fullmatch(r'\d{1,3}',t):labels.append(t)
 if row['pdf_page']!=125:row['printed_page_labels_observed']=labels
 row['content_type']='raster' if row['native_glyphs']==0 else ('mixed' if p.get_images() else 'native_text_and_vector_graphics')
 row['has_detected_tables']=row['tables']>0
 row['conversion_status']='converted'
 if row['pdf_page']==178:
  row['ambiguous_assignment_review']='The sole ambiguous glyph is a space on a cell boundary; no visible character or value is missing. Full table review pending.'
html=MarkdownIt('commonmark',{'html':True}).render(s);soup=BeautifulSoup(html,'html.parser')
ids=[a.get('id') for a in soup.select('[id]')];missing=[]
for x in soup.select('[href], [src]'):
 u=x.get('href',x.get('src',''))
 if u.startswith('#'):
  if u[1:] not in ids:missing.append(u)
 elif not re.match(r'^[a-z]+:',u) and not (r/u).is_file():missing.append(u)
page_nums=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',s)))
assert page_nums==list(range(1,243));assert not missing;assert len(ids)==len(set(ids))
# Structural check of every HTML grid, including rowspans.
table_problems=[]
for ti,t in enumerate(soup.find_all('table')):
 active={};widths=[]
 for ri,tr in enumerate(t.find_all('tr',recursive=False)):
  occupied={k for k,v in active.items() if v>ri};col=0
  for c in tr.find_all(['td','th'],recursive=False):
   while col in occupied:col+=1
   cs=int(c.get('colspan',1));rs=int(c.get('rowspan',1))
   for k in range(col,col+cs):
    if k in occupied:table_problems.append({'table':ti,'row':ri,'issue':'overlap'})
    active[k]=ri+rs;occupied.add(k)
   col+=cs
  widths.append(max(occupied)+1 if occupied else 0)
 if len(set(widths))>1:table_problems.append({'table':ti,'issue':'variable grid width','widths':widths})
style='<style>body{font:16px sans-serif;margin:32px;line-height:1.5}table{border-collapse:collapse;display:block;overflow-x:auto;max-width:100%}td,th{border:1px solid #aaa;padding:6px;min-width:90px}img{max-width:100%}blockquote{color:#666}</style>'
(r/'_проверка/rendered.html').write_text('<!doctype html><meta charset="utf-8">'+style+html.replace('src="assets/','src="../assets/'))
res={'physical_pages':len(d),'page_markers_in_exact_order':True,'local_links_missing':missing,'anchors_unique':True,'html_tables':len(soup.find_all('table')),'table_grid_diagnostics':table_problems,'control_characters_remaining':sorted(set(ord(c) for c in s if ord(c)<32 and c not in '\n\r\t')),'render_scope':'Markdown parsed to HTML and DOM checked; browser visual display not checked','checked_pages':[1,125],'pending_full_review_pages':[i for i in range(1,243) if i not in [1,125]]}
(r/'_проверка/validation.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n');(r/'_проверка/pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n')
cov=json.load(open(r/'_проверка/native_coverage.json'));(r/'_проверка/baseline/native_coverage.json').write_text(json.dumps(cov,indent=2)+'\n');cov.update({'baseline_report_sha256':cov['report_sha256'],'report_sha256':hashlib.sha256(s.encode()).hexdigest(),'review_status':'pending','semantic_source_review_completed':False,'checked_pages':[1,125],'pending_pages':res['pending_full_review_pages'],'scope':'Native glyph accounting refers to mechanical baseline. Final repairs documented in corrections.json; glyph accounting is not semantic acceptance.'});(r/'_проверка/native_coverage.json').write_text(json.dumps(cov,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in res.items() if k not in ['pending_full_review_pages','table_grid_diagnostics']},ensure_ascii=False));print('Table grid diagnostics:',len(table_problems))
