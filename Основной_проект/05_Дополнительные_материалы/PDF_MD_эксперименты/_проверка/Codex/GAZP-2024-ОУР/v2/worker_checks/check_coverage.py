import pathlib,json,re,html,collections
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
A=pathlib.Path('result/_проверка');D=pymupdf.open(json.load(open('source.json'))['source_pdf'])
trans={0xf639:'0',0xf6dc:'1',0xf63a:'2',0xf63b:'3',0xf63c:'4',0xf63d:'5',0xf63e:'6',0xf63f:'7',0xf640:'8',0xf641:'9'}
def norm(t):
 t=html.unescape(re.sub('<[^>]+>','',t)).translate(trans).lower().replace('ё','е')
 return re.sub(r'[^\w]','',t)
miss=[]
for n,p in enumerate(D,1):
 text=(A/'pages'/f'{n:04}.md').read_text();z=norm(text)
 for b in p.get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   x,y,xx,yy=l['bbox'];t=''.join(s['text'] for s in l['spans']);k=norm(t)
   if p.rect.width>800 and(y<65 or y>795):continue
   if len(k)>3 and k not in z:
    miss.append({'pdf_page':n,'bbox':l['bbox'],'text':t})
(A/'coverage_missing.json').write_text(json.dumps(miss,ensure_ascii=False,indent=2))
print('Unmatched native lines',len(miss),'pages',collections.Counter(m['pdf_page'] for m in miss))
for m in miss[:60]:print(m['pdf_page'],m['text'])
