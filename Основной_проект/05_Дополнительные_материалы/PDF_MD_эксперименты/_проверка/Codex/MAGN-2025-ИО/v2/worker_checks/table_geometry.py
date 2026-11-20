import fitz,collections

def augmented_tables(page):
 initial=page.find_tables(strategy='lines').tables
 horizontals=[]
 for dr in page.get_drawings():
  for it in dr['items']:
   if it[0]=='l' and abs(it[1].y-it[2].y)<.2:
    x0,x1=sorted([it[1].x,it[2].x]);y=it[1].y
    if x1-x0>20:horizontals.append((x0,y,x1))
 adds=[];changes=[]
 for t in initial:
  x0,y0,x1,y1=t.bbox
  if y0<100 or y1-y0>300:continue
  next_top=min([q.bbox[1] for q in initial if q.bbox[1]>y1+2 and min(q.bbox[2],x1)-max(q.bbox[0],x0)>.5*(x1-x0)]+[page.rect.height-40])
  lines=[(a,y,b) for a,y,b in horizontals if a>=x0-2 and b<=x1+2 and y1-1<=y<next_top]
  if not lines:continue
  bottom=max(y for a,y,b in lines)
  if bottom<y1+10:continue
  # Stop at a gap separating distinct tables, without extending through headings.
  ys=sorted(set(round(y,1) for a,y,b in lines));end=ys[0]
  for y in ys[1:]:
   if y-end>85:break
   end=y
  lines=[(a,y,b) for a,y,b in lines if y<=end+.2]
  endpoints=collections.defaultdict(list)
  for a,y,b in lines:
   endpoints[round(a,1)].append(y);endpoints[round(b,1)].append(y)
  for x,ys in endpoints.items():
   if len(set(round(y,1) for y in ys))>=2:
    adds.append(((x,y1),(x,max(ys))))
  changes.append({'header_bbox':list(t.bbox),'body_bottom':end,'added_vertical_segments':len(endpoints)})
 return page.find_tables(strategy='lines',add_lines=adds).tables,changes

class Proxy:
 def __init__(self,page):self.page=page;self.changes=[]
 def __getattr__(self,k):return getattr(self.page,k)
 def find_tables(self,**kwargs):
  ts,self.changes=augmented_tables(self.page)
  class Result:pass
  r=Result();r.tables=ts;return r
