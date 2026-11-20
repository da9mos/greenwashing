import re,html
import pymupdf

def cell_text(page,rect):
 # Read characters in visual lines; keep lowered digits with the surrounding line.
 chars=[]
 for b in page.get_text('rawdict',clip=pymupdf.Rect(rect)+(.1,.1,-.1,-.1))['blocks']:
  for l in b.get('lines',[]):
   for s in l['spans']:
    for c in s['chars']:
     if c['c'] not in '\x07':chars.append(c)
 groups=[]
 for c in sorted(chars,key=lambda c:((c['bbox'][1]+c['bbox'][3])/2,c['bbox'][0])):
  cy=(c['bbox'][1]+c['bbox'][3])/2
  g=next((g for g in groups if abs(g[0]-cy)<3.5),None)
  if g is None:groups.append([cy,[c]])
  else:g[1].append(c)
 lines=[]
 for _,cs in groups:
  cs.sort(key=lambda c:c['bbox'][0]);line='';end=None;ht=None
  for c in cs:
   if end is not None and c['bbox'][0]-end>1.6 and not line.endswith(' ') and c['c']!=' ':line+=' '
   line+=c['c'];end=c['bbox'][2]
  lines.append(line.strip())
 return '\n'.join(lines).strip()

def render(page,ts):
 # Adjacent numerical and reporting-standard areas share the same visual rows.
 ts=sorted(ts,key=lambda t:t.bbox[0]);cells=[];offset=0;end=None
 for t in ts:
  if end is not None:offset=t.bbox[0]-end
  for cell in t.cells:
   if cell is None:continue
   x0,y0,x1,y1=cell
   cells.append(((x0-offset,y0,x1-offset,y1),cell_text(page,cell)))
  end=t.bbox[2]-offset
 def unique(vals):
  u=[]
  for v in sorted(vals):
   if not u or v-u[-1]>1:u.append(v)
  return u
 xs=unique([c[0][j] for c in cells for j in [0,2]]);ys=unique([c[0][j] for c in cells for j in [1,3]])
 def ix(a,v):return min(range(len(a)),key=lambda k:abs(a[k]-v))
 grid={};covered=set()
 for (x0,y0,x1,y1),text in cells:
  x,xx=ix(xs,x0),ix(xs,x1);y,yy=ix(ys,y0),ix(ys,y1)
  if (y,x) in grid:continue
  grid[(y,x)]=(max(1,yy-y),max(1,xx-x),text)
  covered.update((r,c) for r in range(y,yy) for c in range(x,xx) if (r,c)!=(y,x))
 rows=[]
 for y in range(len(ys)-1):
  row=[]
  for x in range(len(xs)-1):
   if (y,x) in covered:continue
   rs,cs,text=grid.get((y,x),(1,1,''));attrs=(f' rowspan="{rs}"' if rs>1 else '')+(f' colspan="{cs}"' if cs>1 else '')
   row.append('<td'+attrs+'>'+html.escape(text).replace('\n','<br>')+'</td>')
  rows.append('<tr>'+''.join(row)+'</tr>')
 return '<table>\n'+'\n'.join(rows)+'\n</table>'
