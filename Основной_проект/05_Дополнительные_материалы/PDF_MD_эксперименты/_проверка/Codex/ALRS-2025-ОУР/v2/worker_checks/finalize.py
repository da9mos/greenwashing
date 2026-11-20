from pathlib import Path
import re,json,hashlib,sys,collections
import pymupdf as fitz
sys.path.insert(0,'/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
R=Path('result');src=json.load(open('source.json'));pdf=fitz.open(src['source_pdf']);registry=json.loads((R/'_проверка/pages.json').read_text());text=(R/'report.md').read_text();parts=re.split(r'<!-- pdf_page: (\d+) -->',text)
for x,page in zip(registry['pages'],pdf):
 n=x['pdf_page'];x['native_text_characters']=len(page.get_text());x['raster_images']=len(page.get_images());x['render_review_status']='blocked'
 nums=[b[4].strip() for b in page.get_text('blocks') if b[0]>1800 and b[3]<100 and b[4].strip().isdigit()]
 x['printed_page']=nums[0] if len(nums)==1 else None;x['printed_page_basis']='Native PDF number in top-right navigation strip' if nums else 'No printed page number established; chapter number is separate'
 soup=BeautifulSoup(parts[2*n],'html.parser');table_issues=[]
 for i,table in enumerate(soup.find_all('table'),1):
  counts=[sum(int(c.get('colspan',1)) for c in row.find_all(['td','th'],recursive=False)) for row in table.find_all('tr')]
  # These are signals for review, never proof of source semantic errors.
  cells=table.find_all(['td','th']);empty=sum(not c.get_text().strip() for c in cells)
  table_issues.append({'table':i,'rows':len(counts),'max_grid_columns':max(counts,default=0),'empty_cells':empty,'total_cells':len(cells),'semantic_review_status':'checked' if n in {9,244} else 'pending'})
 x['table_diagnostics']=table_issues
 if any(z['max_grid_columns']>10 for z in table_issues) and x['review_status']!='checked':
  x['issues'].append('Механическая сетка содержит более 10 колонок; возможна фрагментация смысловых полей.')
(R/'_проверка/pages.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n')
# Source raster bytes match the input registry, not another transcription.
idx=json.load(open(src['index']));bad=[]
for row in idx['pages']:
 n=row['pdf_page'];p=R/f'assets/page_{n:04}.png'
 if hashlib.sha256(p.read_bytes()).hexdigest()!=row['image_sha256']:bad.append(n)
ids={x['id'] for x in BeautifulSoup(text,'html.parser').select('[id]')};soup=BeautifulSoup(text,'html.parser');missing=[]
for p in re.findall(r'\]\((assets/[^)]+)\)',text):
 if not(R/p).is_file():missing.append(p)
broken=[a.get('href') for a in soup.find_all('a') if a.get('href','').startswith('#') and a['href'][1:] not in ids]
result={'source_sha256':hashlib.sha256(Path(src['source_pdf']).read_bytes()).hexdigest(),'report_sha256':hashlib.sha256((R/'report.md').read_bytes()).hexdigest(),'pdf_physical_pages':len(pdf),'page_markers_exactly_1_to_247':list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',text)))==list(range(1,248)),'registry_pages':len(registry['pages']),'source_image_hash_mismatches':bad,'missing_assets':missing,'unresolved_internal_anchors':broken,'tables':len(soup.find_all('table')),'content_review_counts':dict(collections.Counter(x['review_status'] for x in registry['pages'])),'render_status':'blocked','scope':'Mechanical integrity, not proof of full PDF transcription fidelity.'}
(R/'_проверка/integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
assert result['page_markers_exactly_1_to_247'] and not bad and not missing and not broken
# Rebuild final HTML using exactly the supplied renderer's preparation, without retrying the blocked Chrome launch.
base=Path(src['index']).parents[3];sys.path.insert(0,str(base/'tools'))
from markdown_it import MarkdownIt
from render_results import CSS
from urllib.parse import unquote
soup=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).enable('table').render(text),'html.parser')
for im in soup.find_all('img'):im['src']=(R/unquote(im['src'])).resolve().as_uri();im['loading']='lazy'
for table in list(soup.find_all('table')):
 wrapper=soup.new_tag('div');wrapper['class']='scroll';table.wrap(wrapper)
(R/'_проверка/render/report.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+CSS+'</style>'+str(soup))
(R/'_проверка/render/render_check.json').write_text(json.dumps({'report_sha256':result['report_sha256'],'html_generated':True,'browser_screenshots_generated':False,'visual_render_review_status':'blocked','reason':'Supplied render_bundle.py failed at Chrome headless launch: TargetClosedError; process SIGABRT; kill EPERM in sandbox. No browser screenshots were available to inspect.','scope':'HTML generation only; no claim of browser or source review.'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
