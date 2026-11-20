import json,re,collections,html
from pathlib import Path
import pymupdf,pymupdf4llm
from table_geometry import render
pymupdf4llm.use_layout(False)
out=Path('result');check=out/'_проверка';dest=check/'pages-complete';dest.mkdir(exist_ok=True)
s=json.load(open('source.json'));doc=pymupdf.open(s['source_pdf']);meta=json.load(open(check/'pages.json'));meta=json.load(open(check/'pages-complete.json')) if (check/'pages-complete.json').exists() else dict(meta,pages=[]); done=len(meta['pages'])
for i,p in enumerate(doc):
 n=i+1;w=p.rect.width
 if n<=done:continue
 split=n>=9 and n not in [11,16,28,48,53,56,61,114]
 clips=[pymupdf.Rect(0,65,w/2,p.rect.height-25),pymupdf.Rect(w/2,65,w,p.rect.height-25)] if split else [p.rect+(0,65,0,-25)]
 if n==1:clips=[p.rect]
 tables=[]
 if n>=9 and n not in [11,16,28,48,53,61,113,114]:
  for clip in clips:
   found=[t for t in p.find_tables(clip=clip,strategy='lines').tables if t.row_count>=2 and t.col_count>=2]
   groups=[]
   for t in sorted(found,key=lambda t:(t.bbox[1],t.bbox[0])):
    group=next((g for g in groups if abs(g[0].bbox[1]-t.bbox[1])<1 and abs(g[0].bbox[3]-t.bbox[3])<1 and 0<=t.bbox[0]-g[-1].bbox[2]<10),None)
    if group is None:groups.append([t])
    else:group.append(t)
   for group in groups:
    rect=pymupdf.Rect(group[0].bbox)
    for t in group[1:]:rect|=pymupdf.Rect(t.bbox)
    candidate=render(p,group)
    source_tokens=collections.Counter(re.findall(r'\w+',p.get_textbox(rect).lower()))
    table_tokens=collections.Counter(re.findall(r'\w+',html.unescape(re.sub('<[^>]*>',' ',candidate)).lower()))
    coverage=1-sum((source_tokens-table_tokens).values())/max(1,sum(source_tokens.values()))
    if coverage>=.94:tables.append((rect,candidate))
 clone=pymupdf.open();clone.insert_pdf(doc,from_page=i,to_page=i);q=clone[0]
 for rect,md in tables:q.add_redact_annot(rect,fill=False)
 if tables:q.apply_redactions(images=0,graphics=0,text=0)
 for j,(rect,md) in enumerate(tables):q.insert_text((rect.x0+1,rect.y0+8),f'ZZTABLE{j:03}ZZ',fontsize=7)
 chunks=[]
 for clip in clips:
  margin=(clip.x0,clip.y0,w-clip.x1,p.rect.height-clip.y1)
  chunks.append(pymupdf4llm.to_markdown(clone,pages=[0],margins=margin,force_text=True,ignore_images=True,ignore_graphics=True,show_progress=False))
 text='\n\n'.join(chunks)
 for j,(rect,md) in enumerate(tables):
  tag=f'ZZTABLE{j:03}ZZ'
  if tag not in text:text+='\n\n'+tag
  text=text.replace(tag,'\n\n'+md+'\n\n')
 text=re.sub(r'\n{3,}','\n\n',text).strip()
 if n==1:text='# Отчет об устойчивом развитии Группы «ЛУКОЙЛ»\n\n2025\n\n35 лет в движении:\nэффективно, экологично, ответственно'
 # Attach extracted original annotation links from first pass.
 old=(check/'pages'/f'page_{n:04}.md').read_text()
 if '<details>' in old:text+='\n\n'+old[old.index('<details>'):].strip()
 raw='\n'.join(p.get_text(clip=c) for c in clips)
 def tok(s):return re.findall(r'\w+',s.lower())
 a=collections.Counter(tok(raw));b=collections.Counter(tok(re.sub('<[^>]*>',' ',text)));missing=a-b
 item={'pdf_page':n,'printed_page_labels':[b[4].strip() for b in p.get_text('blocks') if b[1]>800 and re.fullmatch(r'\d+',b[4].strip())],'content_type':'mixed' if p.get_images() else 'text_and_vector','layout':'spread' if split else 'full_width','conversion_status':'pending' if n in [112,113] else 'converted','review_status':'pending','issues':['Полная построчная и поячеечная сверка с оригиналом не выполнена.'],'native_text_chars':len(p.get_text()),'native_word_coverage':round(1-sum(missing.values())/max(1,sum(a.values())),4),'missing_tokens':dict(missing),'table_count':len(tables),'image':f'assets/page_{n:04}.png'}
 (dest/f'page_{n:04}.md').write_text(text+'\n');meta['pages'].append(item)
 (check/'pages-complete.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2));print(n,len(tables),item['native_word_coverage'],flush=True)
