import sys,json,hashlib,shutil,re,html,subprocess,os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf
s=json.loads(Path('source.json').read_text()); src=Path(s['source_pdf']); idx=json.loads(Path(s['index']).read_text()); base=Path(s['index']).parents[3]; out=Path('result'); d=pymupdf.open(src)
meta={'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'physical_pages':len(d),'method':'Native PDF blocks in source order; ruled tables via PyMuPDF; local Tesseract rus+eng supplemental OCR','pages':[]}
def table_rows(t):
 return [[d[t.page.number].get_text(clip=pymupdf.Rect(c)).strip() if c else '' for c in row.cells] for row in t.rows]
def esc(t):return html.escape(t).replace('\n','<br>')
for i,p in enumerate(d):
 n=i+1; target=out/'assets'/f'page_{n:04}.png';shutil.copy2(base/idx['pages'][i]['image'],target)
 raw=p.get_text();(out/'_проверка/pages'/f'{n:04}.txt').write_text(raw)
 tables=p.find_tables(strategy='lines_strict').tables
 tables=[t for t in tables if t.row_count>=2 and t.col_count>=2]
 emitted=set(); parts=[]; blocks=p.get_text('blocks')
 for block in blocks:
  if block[6]!=0:continue
  rect=pymupdf.Rect(block[:4]); text=block[4].strip()
  overlaps=[j for j,t in enumerate(tables) if (rect&pymupdf.Rect(t.bbox)).get_area()>.6*rect.get_area()]
  if overlaps:
   for j in overlaps:
    if j in emitted:continue
    emitted.add(j);t=tables[j];rows=table_rows(t)
    table='<table>\n'+'\n'.join('<tr>'+''.join('<td>'+esc(c or '')+'</td>' for c in row)+'</tr>' for row in rows)+'\n</table>'
    parts.append(table)
  else:
   # Preserve original line breaks and hyphens; no guessed word repair.
   parts.append(esc(text).replace('<br>','  \n'))
 for j,t in enumerate(tables):
  if j not in emitted:parts.append('<table>\n'+'\n'.join('<tr>'+''.join('<td>'+esc(c or '')+'</td>' for c in row)+'</tr>' for row in table_rows(t))+'\n</table>')
 links=[]
 for link in p.get_links():
  if link.get('uri'):links.append('['+link['uri'].replace(']','\\]')+']('+link['uri']+')')
  elif link.get('page',-1)>=0: links.append(f'[Переход из PDF](#pdf-page-{link["page"]+1})')
 if links:parts.append('<details><summary>Ссылки и переходы страницы</summary>\n\n'+' · '.join(dict.fromkeys(links))+'\n</details>')
 md='\n\n'.join(parts)+'\n\n'+f'![Страница {n}: визуальная опора](assets/page_{n:04}.png)\n'
 (out/'_проверка/pages'/f'{n:04}.md').write_text(md)
 meta['pages'].append({'pdf_page':n,'printed_page':None,'content_type':'text_and_graphics' if p.get_images() else 'text_and_tables','conversion_status':'converted','review_status':'pending','issues':['Полная визуальная сверка не выполнена; порядок блоков, таблицы и графика требуют проверки.'],'text_chars':len(raw),'tables_detected':len(tables),'source_image':f'assets/page_{n:04}.png'})
 pass
 if n%20==0:print('converted',n,flush=True)
