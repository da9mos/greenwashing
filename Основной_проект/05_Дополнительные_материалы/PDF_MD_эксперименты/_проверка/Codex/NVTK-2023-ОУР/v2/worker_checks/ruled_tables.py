import sys,json,collections,re,html
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf
pymupdf._layout_enabled=False
src=json.load(open('source.json'));d=pymupdf.open(src['source_pdf']);root=Path('result/_проверка'); inventory=[]
def cell(p,box):
 lines=[]
 for b in PAGE_DICT['blocks']:
  for ln in b.get('lines',[]):
   spans=[]
   for sp in ln['spans']:
    r=pymupdf.Rect(sp['bbox']); x=(r.x0+r.x1)/2;y=(r.y0+r.y1)/2
    if box.x0<=x<box.x1 and box.y0<=y<box.y1: spans.append(('<sup>'+html.escape(sp['text'])+'</sup>') if sp.get('flags',0)&1 else html.escape(sp['text']))
   if spans: lines.append(''.join(spans).strip())
 return '<br>'.join(t for t in lines if t)
for n in list(range(105,133))+[134,135,136]:
 p=d[n-1]; PAGE_DICT=p.get_text('dict'); rows=collections.defaultdict(list)
 for dr in p.get_drawings():
  for it in dr['items']:
   if it[0]=='l':
    a,b=it[1:3]
    if abs(a.y-b.y)<.15 and abs(a.x-b.x)>5 and a.y>70:
     rows[round(a.y,1)].append((round(min(a.x,b.x),1),round(max(a.x,b.x),1)))
 groups=collections.defaultdict(list)
 for y,segs in rows.items():
  chunks=[]
  for a,b in sorted(segs):
   if chunks and a<=chunks[-1][-1]+.3: chunks[-1].extend([a,b])
   else: chunks.append([a,b])
  for ch in chunks:
   if ch[-1]-ch[0]>200: groups[(ch[0],ch[-1])].append((y,sorted(set(ch))))
 tables=[]
 for (x0,x1),rs in groups.items():
  if len(rs)<3:continue
  freq=collections.Counter(x for y,xs in rs for x in xs)
  xs=sorted(x for x,c in freq.items() if c>=max(3,len(rs)*.45))
  if len(xs)<3 or xs[0]!=x0 or xs[-1]!=x1:continue
  rs.sort();sets=[]
  for y,xx in rs:
   if sets and y-sets[-1][-1]>48: sets.append([y])
   elif sets:sets[-1].append(y)
   else:sets.append([y])
  for ys in sets:
   if len(ys)<3:continue
   # The first rule is normally under the column header.
   top=ys[0]-15
   box=pymupdf.Rect(x0,top,x1,ys[-1]+.2)
   if any(box.intersects(t['rect']) for t in tables):continue
   edges=[top]+ys;data=[]
   for a,b in zip(edges,edges[1:]):
    data.append([cell(p,pymupdf.Rect(l,a,r,b)) for l,r in zip(xs,xs[1:])])
   if not any(any(c for c in row) for row in data):continue
   h=['<table>']
   for j,row in enumerate(data):
    tag='th' if j==0 else 'td';h.append('<tr>'+''.join(f'<{tag}>{c}</{tag}>' for c in row)+'</tr>')
   h.append('</table>');tables.append({'rect':box,'html':'\n'.join(h),'rows':len(data),'cols':len(xs)-1})
 if not tables:continue
 # Keep all non-table text; split at span level so adjoining notes cannot disappear.
 els=[]
 for b in PAGE_DICT['blocks']:
  for ln in b.get('lines',[]):
   spans=[]
   for sp in ln['spans']:
    r=pymupdf.Rect(sp['bbox']);center=pymupdf.Point((r.x0+r.x1)/2,(r.y0+r.y1)/2)
    if not any(center in t['rect'] for t in tables):spans.append(sp)
   if spans:
    txt=''.join(s['text'] for s in spans).replace('\x07','').strip()
    if txt:els.append((pymupdf.Rect(ln['bbox']),txt))
 for t in tables:els.append((t['rect'],t['html']))
 # A table crossing the gutter is kept whole. Otherwise read left then right.
 if not any(r.x0<p.rect.width/2-20 and r.x1>p.rect.width/2+20 for r,t in els):
  els.sort(key=lambda e:(int((e[0].x0+e[0].x1)/2>p.rect.width/2),e[0].y0,e[0].x0))
 else:els.sort(key=lambda e:(round(e[0].y0/3),e[0].x0))
 text='\n\n'.join(t for r,t in els)+'\n'
 (root/'pages'/f'tables_{n:04}.md').write_text(text)
 inventory.append({'pdf_page':n,'tables':[{'bbox':list(t['rect']),'rows':t['rows'],'columns':t['cols']} for t in tables]})
 print(n,[(t['rows'],t['cols']) for t in tables],flush=True)
(root/'tables.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2))
