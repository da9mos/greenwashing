import os,sys,json,hashlib,shutil,re,time
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
s=json.load(open('source.json')); src=Path(s['source_pdf']); idx=json.load(open(s['index'])); base=Path(s['index']).parent
out=Path('result'); ck=out/'_проверка'; doc=pymupdf.open(src)
meta={'source_pdf':str(src),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'physical_pages':len(doc),'method':'PyMuPDF4LLM legacy, no layout model; native text; page images from input registry','pages':[]}
(ck/'source.json').write_text(json.dumps({k:v for k,v in meta.items() if k!='pages'},ensure_ascii=False,indent=2))
for i,p in enumerate(doc):
 n=i+1; f=ck/'pages'/f'{n:04}.md'
 if not f.exists():
  try: text=pymupdf4llm.to_markdown(doc,pages=[i],force_text=True,write_images=False,ignore_images=True,ignore_graphics=False,margins=0,table_strategy='lines_strict',show_progress=False)
  except Exception as e: text=p.get_text(sort=True); print('fallback',n,e,flush=True)
  text=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',text)
  f.write_text(text)
 image=base/f'page_{n:04}.png'; target=out/'assets'/image.name
 if not target.exists():shutil.copy2(image,target)
 links=[]
 for l in p.get_links():
  if l.get('uri'): links.append({'text':p.get_textbox(l['from']).strip(),'uri':l['uri']})
  elif l.get('page',-1)>=0:links.append({'text':p.get_textbox(l['from']).strip(),'page':l['page']+1})
 rec={'pdf_page':n,'printed_page_labels':[],'content_type':'native text with graphics / spread' if p.rect.width>p.rect.height else 'native text with graphics','conversion_status':'converted','review_status':'pending','issues':['Полная визуальная сверка текста, таблиц, порядка колонок и подписей графики не завершена.'],'native_text_chars':len(p.get_text()),'markdown_chars':len(f.read_text()),'image':f'assets/{image.name}','links':links}
 meta['pages'].append(rec)
 (ck/'pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
 if n%5==0: print('saved',n,flush=True)
print('DONE',flush=True)
