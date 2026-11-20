import sys,json,hashlib,shutil,re,time
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
# Table detection in this library version has an independent layout switch.
_orig=pymupdf.Page.find_tables
def geometric_tables(self,**kw):
 kw['use_layout']=False
 return _orig(self,**kw)
pymupdf.Page.find_tables=geometric_tables
s=json.load(open('source.json')); src=Path(s['source_pdf']); idx=json.load(open(s['index'])); base=Path(s['index']).parent
out=Path('result'); check=out/'_проверка'; doc=pymupdf.open(src)
metadata={'source_pdf':str(src),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'physical_pages':len(doc),'method':'PyMuPDF4LLM legacy; geometric table detection use_layout=False; no external services','pages':[]}
headers=pymupdf4llm.IdentifyHeaders(doc)
for i,p in enumerate(doc):
 n=i+1; target=check/'pages'/f'page_{n:04}.md'; im=out/'assets'/f'page_{n:04}.png'
 shutil.copy2(base/f'page_{n:04}.png',im)
 packet=json.load(open(base/f'page_{n:04}.json')); raw=p.get_text(); issues=[]
 if target.exists(): text=target.read_text()
 else:
  try:
   text=pymupdf4llm.to_markdown(doc,pages=[i],hdr_info=headers,force_text=True,ignore_images=True,ignore_graphics=False,show_progress=False,table_strategy='lines_strict')
  except Exception as e:
   text='\n\n'.join(b[4] for b in p.get_text('blocks') if len(b)>4 and isinstance(b[4],str)); issues.append('Ошибка Markdown-конвертера: '+str(e))
  target.write_text(text)
 # Preserve text omitted by automatic layout extraction as explicitly separated blocks.
 norm=lambda x: re.sub(r'[^\w]','',x).lower()
 from collections import Counter
 full=Counter(norm(raw)); got=Counter(norm(text)); deficit=sum((full-got).values())
 missing=[]
 nt=norm(text)
 for b in packet.get('text_blocks',[]):
  bt=b['text']; bn=norm(bt)
  if len(bn)>12 and bn not in nt:
   bc=Counter(bn); absent=sum((bc-got).values())
   if absent>max(8,len(bn)*0.2): missing.append(bt)
 # Raw layer retained independently for coverage audit, not silently merged / duplicated.
 (check/'pages'/f'page_{n:04}.txt').write_text(raw)
 links=[]
 for l in packet.get('links',[]):
  if l.get('uri'): links.append({'label':l.get('text') or l['uri'],'uri':l['uri']})
  elif isinstance(l.get('page'),int) and 0<=l['page']<len(doc): links.append({'label':l.get('text') or 'Внутренний переход','page':l['page']+1})
 footnums=[]
 for b in packet.get('text_blocks',[]):
  bb=b['bbox']; t=b['text'].strip()
  if bb[1]<45 and re.fullmatch(r'\d{1,3}',t): footnums.append(t)
 # Mixed content is identified conservatively; full-page support is always saved.
 imgs=p.get_image_info(); area=sum(max(0,(a['bbox'][2]-a['bbox'][0])*(a['bbox'][3]-a['bbox'][1])) for a in imgs)
 record={'pdf_page':n,'printed_labels':footnums,'content_type':'text_and_graphics' if imgs or p.get_drawings() else 'text','conversion_status':'converted','review_status':'pending','issues':issues+['Полная визуальная сверка страницы не выполнена; проверить колонки, таблицы, сноски и текст внутри графики.'],'text_layer_chars':len(raw),'markdown_chars':len(text),'character_deficit':deficit,'image_count':len(imgs),'image_area_ratio':round(area/p.rect.get_area(),3),'source_image':f'assets/page_{n:04}.png','links':links,'possible_omitted_blocks':missing}
 metadata['pages'].append(record)
 (check/'pages.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
 print(n,len(raw),len(text),'deficit',deficit,flush=True)
print('DONE',flush=True)
