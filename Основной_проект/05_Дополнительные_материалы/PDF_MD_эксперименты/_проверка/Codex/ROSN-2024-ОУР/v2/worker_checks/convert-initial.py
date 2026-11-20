import sys,json,hashlib,shutil,re,time
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf as fitz
from pymupdf4llm.helpers.pymupdf_rag import to_markdown
s=json.load(open('source.json')); src=Path(s['source_pdf']); d=fitz.open(src); idx=json.load(open(s['index'])); base=Path(s['index']).parents[3]; out=Path('result'); records=[]
meta={'source_pdf':str(src),'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'physical_pages':len(d),'method':'pymupdf4llm legacy, без моделей; текст PDF; отдельное визуальное чтение страниц без текста','pages':records}
for i,p in enumerate(d):
 n=i+1; image=out/'assets'/f'page_{n:04}.png'; shutil.copyfile(base/idx['pages'][i]['image'],image)
 raw=p.get_text(); (out/'_проверка/pages'/f'{n:04}.txt').write_text(raw)
 try: md=to_markdown(d,pages=[i],force_text=True,ignore_images=True,ignore_graphics=True,table_output='html',show_progress=False)
 except Exception as e: md=raw; print(n,str(e),flush=True)
 md=md.replace('\u00ad\n','').replace('\u00ad','')
 (out/'_проверка/pages'/f'{n:04}.md').write_text(md)
 links=[]
 for l in p.get_links():
  if l.get('uri'): links.append({'text':p.get_textbox(l['from']).strip(),'uri':l['uri']})
  elif l.get('page',-1)>=0: links.append({'text':p.get_textbox(l['from']).strip(),'target_pdf_page':l['page']+1})
 rec={'pdf_page':n,'printed_page':None,'content_type':'spread_text_graphics' if p.rect.width>900 else 'cover','text_chars':len(raw),'conversion_status':'converted' if len(raw)>100 else 'pending','review_status':'pending','issues':['Полная визуальная сверка текста, порядка колонок, таблиц и графических подписей не завершена.'],'links':links}
 records.append(rec); (out/'_проверка/pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)); print(f'{n}/135 {len(md)}',flush=True)
