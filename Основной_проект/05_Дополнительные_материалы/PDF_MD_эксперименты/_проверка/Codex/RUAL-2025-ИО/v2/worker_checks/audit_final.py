import sys,json,re,hashlib
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf
from bs4 import BeautifulSoup
s=json.load(open('source.json'));doc=pymupdf.open(s['source_pdf']);reg=json.load(open('result/_проверка/pages.json'));parts=re.split(r'<!-- pdf_page: \d+ -->',Path('result/report.md').read_text());audits=[]
for entry,page in zip(reg['pages'],doc):
 n=entry['pdf_page'];w,h=page.rect.width,page.rect.height
 footer=[v[4] for v in page.get_text('words') if v[1]>.92*h and re.fullmatch(r'\d{1,3}',v[4])]
 entry['printed_page_labels_observed']=footer;entry['printed_page_labels_method']='Цифровые слова из нижней области оригинала; не вычислены по смещению. Кандидаты не являются подтверждённой визуальной нумерацией.'
 entry['content_type']='native_text_with_graphics' if page.get_images() else 'native_text_and_vector_layout'
 entry['layout']='spread' if w>h else 'single_page'
 entry['source_image']=f'assets/page_{n:04}.png'
 ts=BeautifulSoup(parts[n],'html.parser').find_all('table');stats=[]
 for t in ts:
  rows=t.find_all('tr');cells=t.find_all('td');count=len(cells);empty=sum(not x.get_text(strip=True) for x in cells);widths=[sum(int(c.get('colspan',1)) for c in row.find_all('td',recursive=False)) for row in rows]
  stats.append({'rows':len(rows),'cells':count,'empty_cells':empty,'max_row_colspan_sum':max(widths,default=0)})
 if stats:audits.append({'page':n,'tables':stats})
 if any(x['max_row_colspan_sum']>15 and x['empty_cells']>x['cells']*.4 for x in stats):
  entry['issues'].append('Автоматический аудит: широкая разреженная таблица; возможны ложные колонки/строки. Связи ячеек требуют сверки.')
Path('result/_проверка/pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n');Path('result/_проверка/table_structure_audit.json').write_text(json.dumps(audits,ensure_ascii=False,indent=2)+'\n')
# Every saved source image agrees with the mechanical input registry.
index=json.load(open(s['index']));bad=[]
for p in index['pages']:
 n=p['pdf_page'];asset=Path(f'result/assets/page_{n:04}.png')
 if hashlib.sha256(asset.read_bytes()).hexdigest()!=p['image_sha256']:bad.append(n)
assert not bad,bad
v=json.load(open('result/_проверка/validation.json'));v['source_asset_hashes_match_all_294']=True;v['table_pages_audited']=len(audits);Path('result/_проверка/validation.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
html=Path('result/preview.html').read_text();head=html[:html.index('<h1>')]
from markdown_it import MarkdownIt
sample='\n\n'.join('<!-- pdf_page: '+str(n)+' -->'+parts[n] for n in [1,2,32,181]);sample_html=MarkdownIt('commonmark',{'html':True}).render(sample).replace('src="assets/','src="../assets/')
Path('result/_проверка/render_sample.html').write_text(head+sample_html)
print('Assets checked:',len(index['pages']),'Table pages:',len(audits))
