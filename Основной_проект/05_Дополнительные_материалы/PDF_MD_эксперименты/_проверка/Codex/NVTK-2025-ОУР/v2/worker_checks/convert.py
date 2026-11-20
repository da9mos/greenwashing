import os,sys,json,hashlib,re,shutil,time
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
root=Path.cwd(); out=root/'result'; check=out/'_проверка'; parts=check/'pages';parts.mkdir(exist_ok=True)
s=json.loads((root/'source.json').read_text()); idxpath=Path(s['index']);idx=json.loads(idxpath.read_text());base=idxpath.parents[3];doc=pymupdf.open(s['source_pdf'])
sha=hashlib.sha256(Path(s['source_pdf']).read_bytes()).hexdigest()
(check/'source.json').write_text(json.dumps({'source_pdf':s['source_pdf'],'sha256':sha,'physical_pages':len(doc),'method':'pymupdf4llm legacy; no layout models; native PDF text; page images as visual support'},ensure_ascii=False,indent=2))
entries=[]
for n,p in enumerate(doc,1):
 target=parts/f'{n:04}.md'; raw=p.get_text(); issues=['Полная визуальная сверка страницы не выполнена; порядок блоков, числовые связи и сноски требуют проверки.']
 if not target.exists():
  # Verified source consists of a cover and two-page spreads. Preserve each half independently.
  sub=pymupdf.open()
  rects=[p.rect] if n==1 else [pymupdf.Rect(0,0,1417,p.rect.height),pymupdf.Rect(1417,0,p.rect.width,p.rect.height)]
  chunks=[]
  for r in rects:
   q=sub.new_page(width=r.width,height=r.height);q.show_pdf_page(q.rect,doc,n-1,clip=r)
  try:
   text=pymupdf4llm.to_markdown(sub,force_text=True,ignore_images=True,ignore_graphics=False,table_output='html',show_progress=False)
  except Exception as e:
   text='\n\n'.join(subpage.get_text(sort=True) for subpage in sub);issues.append('Ошибка структурного извлечения: '+str(e))
  target.write_text(text)
 img=base/idx['pages'][n-1]['image']; dest=out/'assets'/f'page_{n:04}.png';shutil.copy2(img,dest)
 links=[]
 for link in p.get_links():
  if link.get('uri'):links.append({'bbox':list(link['from']),'uri':link['uri']})
  elif link.get('page',-1)>=0:links.append({'bbox':list(link['from']),'target_pdf_page':link['page']+1})
 (parts/f'{n:04}.links.json').write_text(json.dumps(links,ensure_ascii=False,indent=2))
 text=target.read_text(); entry={'pdf_page':n,'printed_page_labels':[], 'content_type':'native_text_cover' if n==1 else 'native_text_spread','conversion_status':'converted','review_status':'pending','issues':issues,'source_text_chars':len(raw),'markdown_chars':len(text),'image':f'assets/page_{n:04}.png','tables':text.count('<table')+len(re.findall(r'^\|.*\|$',text,re.M))}
 entries.append(entry)
 (check/'pages.json').write_text(json.dumps({'source_sha256':sha,'pages':entries},ensure_ascii=False,indent=2))
 print(n,len(raw),len(text),flush=True)
