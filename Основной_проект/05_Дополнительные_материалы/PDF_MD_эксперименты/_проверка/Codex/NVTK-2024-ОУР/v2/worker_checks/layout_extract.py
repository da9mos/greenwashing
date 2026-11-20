import sys,json,re,html
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)

def order(items,depth=0):
 if len(items)<2:return items
 # Recursive XY cut: use full block rectangles, not global line sorting.
 for axis in [0,1]:
  spans=sorted((a['bbox'][axis],a['bbox'][axis+2]) for a in items)
  end=spans[0][1]; gaps=[]
  for lo,hi in spans[1:]:
   if lo-end>(10 if axis==0 else 2):gaps.append((lo-end,(lo+end)/2))
   end=max(end,hi)
  if gaps:
   _,cut=max(gaps)
   left=[a for a in items if a['bbox'][axis+2]<=cut];right=[a for a in items if a['bbox'][axis]>=cut]
   if left and right and len(left)+len(right)==len(items):return order(left,depth+1)+order(right,depth+1)
 return sorted(items,key=lambda a:(round(a['bbox'][1]/3),a['bbox'][0]))

def clean(s):return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',s).replace('\u00ad','')
def block_text(b):
 lines=[]
 for l in b['lines']:
  t=''
  for sp in l['spans']:
   x=clean(sp['text'])
   if sp['flags']&1 and x.strip(): x='<sup>'+html.escape(x)+'</sup>'
   t+=x
  lines.append(t.strip())
 t=' '.join(lines)
 # Preserve literal hyphens: no speculative dehyphenation.
 sizes=[s['size'] for l in b['lines'] for s in l['spans']]
 if sizes and max(sizes)>=19:t='## '+t
 return t

def extract(p):
 from ruled_tables import tables as ruled
 special=ruled(p)
 tables=p.find_tables(strategy='lines_strict').tables if not special and p.number!=1 else []
 items=list(special); tinfo=[{k:v for k,v in t.items() if k!='text'} for t in special]
 for t in tables:
  if t.row_count<2 or t.col_count<2:continue
  rows=t.extract();rect=pymupdf.Rect(t.bbox)
  if not any(any(c for c in row) for row in rows):continue
  markup='<table>\n'+''.join('<tr>'+''.join('<td>'+html.escape(clean(c or '')).replace('\n','<br>')+'</td>' for c in row)+'</tr>\n' for row in rows)+'</table>'
  items.append({'bbox':tuple(rect),'text':markup});tinfo.append({'bbox':tuple(rect),'rows':t.row_count,'columns':t.col_count})
 for b in p.get_text('dict')['blocks']:
  if b['type']!=0:continue
  if b['bbox'][3]<42:continue # established repeating navigation bar
  # keep blocks outside tables; split lines intersecting table regions
  keep=[]
  for l in b['lines']:
   lr=pymupdf.Rect(l['bbox']); center=(lr.tl+lr.br)/2
   if not any(center in pymupdf.Rect(t['bbox']) for t in tinfo):keep.append(l)
  if keep:
   b=dict(b);b['lines']=keep;b['bbox']=tuple(pymupdf.Rect(keep[0]['bbox']))
   r=pymupdf.Rect(b['bbox'])
   for l in keep:r|=pymupdf.Rect(l['bbox'])
   b['bbox']=tuple(r)
   items.append({'bbox':b['bbox'],'text':block_text(b)})
 return '\n\n'.join(x['text'] for x in order(items)),tinfo
if __name__=='__main__':
 s=json.load(open('source.json'));d=pymupdf.open(s['source_pdf'])
 for n in map(int,sys.argv[1:]):
  text,t=extract(d[n-1]);Path(f'result/_проверка/test-{n}.md').write_text(text);print(n,t,text[:2000])
