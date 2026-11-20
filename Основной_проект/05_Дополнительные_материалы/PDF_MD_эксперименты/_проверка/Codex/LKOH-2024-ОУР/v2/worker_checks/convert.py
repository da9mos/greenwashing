import sys,json,hashlib,re,shutil,statistics,html
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf as fitz
fitz._layout_enabled=False
ROOT=Path(__file__).resolve().parents[2]
s=json.loads((ROOT/'source.json').read_text()); src=Path(s['source_pdf']); base=Path(s['index']).parent
out=ROOT/'result'; work=out/'_проверка'; assets=out/'assets'; doc=fitz.open(src)
registry={'source_pdf':str(src),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'physical_pages':len(doc),'method':'PyMuPDF native text and vector table geometry; no inference for text; full page images retained','pages':[]}

def clean(t):
 t=re.sub(r'(?<=[А-Яа-яЁё])[-\u00ad]\s*\n\s*(?=[а-яё])','',t)
 t=t.replace('\u00ad','').replace('\xa0',' ').replace('\x07','')
 t=re.sub(r'(?<=[А-Яа-яЁё])-\n(?=[а-яё])','',t)
 return re.sub(r'\s+',' ',t).strip()
def esc(t):return html.escape(t)
def chars_text(cs):
 groups={}
 for c in cs:groups.setdefault(c['line'],[]).append(c)
 return '\n'.join(''.join(c['c'] for c in sorted(v,key=lambda c:c['seq'])) for k,v in sorted(groups.items()))

def process(p,n):
 raw=p.get_text('rawdict'); chars=[]; blocks=[]; lines=[]
 for bi,b in enumerate(raw['blocks']):
  if b['type']!=0:continue
  bc=[]
  for li,l in enumerate(b['lines']):
   lc=[]
   for sp in l['spans']:
    for c in sp['chars']:
     r=fitz.Rect(c['bbox']); q={'c':c['c'],'bbox':tuple(r),'x':(r.x0+r.x1)/2,'y':(r.y0+r.y1)/2,'line':(bi,li),'seq':len(chars),'size':sp['size'],'flags':sp['flags'],'font':sp['font'],'color':sp['color']}
     chars.append(q);bc.append(q);lc.append(q)
   lines.append({'bbox':l['bbox'],'chars':lc})
  blocks.append({'i':bi,'bbox':b['bbox'],'chars':bc})
 # Exclude only established recurring navigation and printed folios; keep in audit.
 excluded={c['seq'] for c in chars if c['font']=='icon_font_lukoil' or (n not in (1,116) and (c['y']<45 or c['y']>735))}
 active=[c for c in chars if c['seq'] not in excluded]
 tables=[];used=set();issues=[]
 try:
  finder=p.find_tables(strategy='lines')
  for tb in finder.tables:
   if tb.col_count<2:continue
   cells=[r for row in tb.rows for r in row.cells if r]
   xs=sorted(set(round(x,2) for r in cells for x in (r[0],r[2])))
   ys=sorted(set(round(y,2) for r in cells for y in (r[1],r[3])))
   # Coalesce subpoint discrepancies from vector strokes.
   def merge(v):
    z=[]
    for a in v:
     if not z or a-z[-1]>1:z.append(a)
    return z
   xs,ys=merge(xs),merge(ys)
   if len(xs)<3 or len(ys)<2:continue
   # Header-only detections: use actual aligned horizontal vector separators.
   stop=min([other.bbox[1] for other in finder.tables if other.bbox[1]>tb.bbox[1]+3 and abs(other.bbox[0]-tb.bbox[0])<3]+[725])
   extra=[]
   for drawing in p.get_drawings():
    for it in drawing['items']:
     if it[0]!='l':continue
     a,b=it[1],it[2]
     if abs(a.y-b.y)>.15 or not tb.bbox[1]+1<a.y<stop:continue
     lo,hi=sorted([a.x,b.x])
     if hi-lo<20:continue
     if min(abs(lo-x) for x in xs)<1 and min(abs(hi-x) for x in xs)<1:extra.append(a.y)
   ys=merge(sorted(ys+extra))
   if len(ys)<3:continue
   # Borderless last rows: extend only if a visible row below contains several numeric cells.
   bottom=ys[-1]; nearby=[c for c in active if xs[0]<=c['x']<=xs[-1] and bottom<c['y']<bottom+18]
   numcols=set()
   for c in nearby:
    if c['c'].isdigit():
     k=next((j for j in range(len(xs)-1) if xs[j]<=c['x']<xs[j+1]),-1)
     if k>0:numcols.add(k)
   if len(numcols)>=2 and nearby and statistics.median(c['size'] for c in nearby)>=7.2 and not any(clean(chars_text(b['chars'])).startswith('Примечан') and bottom-2<b['bbox'][1]<bottom+20 for b in blocks):
    dy=statistics.median([ys[j+1]-ys[j] for j in range(len(ys)-1)])
    ys.append(bottom+max(16,min(30,dy)))
   cs=[c for c in active if c['seq'] not in used and xs[0]-.1<=c['x']<=xs[-1]+.1 and ys[0]-.1<=c['y']<=ys[-1]+.1]
   if len(cs)<20:continue
   grid=[[[] for _ in range(len(xs)-1)] for _ in range(len(ys)-1)]
   for c in cs:
    col=next((j for j in range(len(xs)-1) if c['x']<xs[j+1]+.01),len(xs)-2)
    row=next((j for j in range(len(ys)-1) if c['y']<ys[j+1]+.01),len(ys)-2)
    grid[row][col].append(c);used.add(c['seq'])
   # Reconstruct merged phrases by native line extent rather than splitting characters.
   spans_by_row={}
   linegroups={}
   for c in cs:linegroups.setdefault(c['line'],[]).append(c)
   for lc in linegroups.values():
    lc=sorted(lc,key=lambda c:c['x'])
    if not lc:continue
    if any(b['bbox'][0]-a['bbox'][2]>max(5,a['size']*.8) for a,b in zip(lc,lc[1:])):continue
    r=next((j for j in range(len(ys)-1) if lc[0]['y']<ys[j+1]+.01),len(ys)-2)
    a=next((j for j in range(len(xs)-1) if lc[0]['x']<xs[j+1]+.01),len(xs)-2)
    b=next((j for j in range(len(xs)-1) if lc[-1]['x']<xs[j+1]+.01),len(xs)-2)
    if b>a:spans_by_row.setdefault(r,[]).append((a,b))
   h=['<div style="overflow-x:auto">','<table>']
   for ri,row in enumerate(grid):
    joins=[{j} for j in range(len(row))]
    for a,b in spans_by_row.get(ri,[]):
     union=set().union(*joins[a:b+1])
     for j in union:joins[j]=union
    cells=[];j=0
    while j<len(row):
     group=joins[j];end=max(group);cc=[c for k in sorted(group) for c in row[k]]
     span=f' colspan="{end-j+1}"' if end>j else ''
     cells.append('<td'+span+'>'+esc(clean(chars_text(cc)))+'</td>');j=end+1
    h.append('<tr>'+''.join(cells)+'</tr>')
   h+=['</table>','</div>']
   tables.append({'bbox':(xs[0],ys[0],xs[-1],ys[-1]),'i':min(c['line'][0] for c in cs),'text':'\n'.join(h),'char_count':len(cs),'columns':len(xs)-1,'rows':len(ys)-1})
 except Exception as e:issues.append('Ошибка геометрического извлечения таблиц: '+str(e))
 # Original PDF object sequence preserves paragraphs and column order; separate logical leaves first.
 leaves=1 if p.rect.width<900 else (4 if p.rect.width>2000 else 2)
 width=p.rect.width/leaves
 def leaf(x):return min(leaves-1,max(0,int(x/width)))
 items=[]
 for b in blocks:
  cs=[c for c in b['chars'] if c['seq'] not in used and c['seq'] not in excluded]
  if not cs:continue
  # Split blocks crossing logical leaf boundaries without sorting unrelated lines by height.
  for k in range(leaves):
   cc=[c for c in cs if leaf(c['x'])==k]
   if not cc:continue
   t=clean(chars_text(cc))
   if not t:continue
   size=max(c['size'] for c in cc);y=min(c['bbox'][1] for c in cc)
   foot=(statistics.median(c['size'] for c in cc)<7.5 and y>570)
   if size>=15: t='## '+t
   elif size>=10.5 and len(t)<240:t='### '+t
   elif all(c['flags']&16 for c in cc if c['c'].strip()) and len(t)<240:t='**'+t+'**'
   else:t=t.replace('΅','•')
   items.append((k,1 if foot else 0,b['i'],t,(min(c['bbox'][0] for c in cc),min(c['bbox'][1] for c in cc),max(c['bbox'][2] for c in cc),max(c['bbox'][3] for c in cc))))
 for tb in tables:items.append((leaf((tb['bbox'][0]+tb['bbox'][2])/2),0,tb['i'],tb['text'],tb['bbox']))
 def spatial(nodes):
  if len(nodes)<2:return nodes
  for axis,gaplimit in [(0,7),(1,4)]:
   intervals=sorted((q[4][axis],q[4][axis+2]) for q in nodes)
   end=intervals[0][1];gaps=[]
   for start,stop in intervals[1:]:
    if start-end>gaplimit:gaps.append((start-end,(start+end)/2))
    end=max(end,stop)
   if gaps:
    cut=max(gaps)[1]
    left=[q for q in nodes if q[4][axis+2]<cut]
    right=[q for q in nodes if q[4][axis]>cut]
    if left and right and len(left)+len(right)==len(nodes):return spatial(left)+spatial(right)
  return sorted(nodes,key=lambda q:(q[4][1],q[4][0],q[2]))
 ordered=[]
 for k in range(leaves):
  for footer in [0,1]:ordered+=spatial([q for q in items if q[0]==k and q[1]==footer])
 items=ordered
 body='\n\n'.join(x[3] for x in items)
 printed=[clean(chars_text(b['chars'])) for b in blocks if b['bbox'][1]>730 and clean(chars_text(b['chars'])).isdigit()]
 image_name=f'page_{n:04}.png';shutil.copy2(base/image_name,assets/image_name)
 links=[]
 for l in p.get_links():
  rect=l.get('from');vis=clean(p.get_textbox(rect)) if rect else ''
  if l.get('uri'):links.append((vis,l['uri']))
  elif l.get('kind')==fitz.LINK_GOTO and l.get('page',-1)>=0:links.append((vis,f"#pdf-page-{l['page']+1}"))
 # Keep annotation destinations separately to avoid guessing inline placement.
 seen=set();linkmd=[]
 for label,dest in links:
  if (label,dest) in seen:continue
  seen.add((label,dest));label=label or 'Ссылка из аннотации PDF'
  linkmd.append('- ['+label.replace('[','\\[').replace(']','\\]')+']('+dest.replace(' ','%20')+')')
 note='> **Техническая пометка.** Рабочая транскрипция: полная постраничная сверка не выполнена; порядок сложных блоков, ячейки таблиц и подписи графиков требуют проверки по изображению.'
 part=f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+note+'\n\n'+body
 if linkmd:part+='\n\n<details><summary>Ссылки из аннотаций PDF (техническое представление)</summary>\n\n'+'\n'.join(linkmd)+'\n\n</details>'
 part+=f'\n\n![Физическая страница {n}: оригинальная вёрстка и графика](assets/{image_name})\n'
 (work/'pages'/f'{n:04}.md').write_text(part)
 (work/'pages'/f'{n:04}.txt').write_text(p.get_text())
 record={'pdf_page':n,'printed_labels':printed,'content_type':'native_text_with_graphics' if p.get_images() else 'native_text','logical_leaves':leaves,'conversion_status':'converted','review_status':'pending','issues':issues+['Полная сверка текста, порядка чтения, графики и сносок по оригиналу не выполнена.']+(['Геометрическая реконструкция таблиц не сверена по всем ячейкам.'] if tables else []),'native_characters':len(chars),'body_characters':len(active),'table_characters':len(used),'table_count':len(tables),'tables':[{'bbox':t['bbox'],'rows':t['rows'],'columns':t['columns']} for t in tables],'image':f'assets/{image_name}','excluded_navigation_folios_and_pictogram_codes':clean(chars_text([c for c in chars if c['seq'] in excluded]))}
 return record

for i,p in enumerate(doc):
 n=i+1;registry['pages'].append(process(p,n))
 (work/'pages.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2))
 print(f'{n}/116 saved',flush=True)
parts=[(work/'pages'/f'{n:04}.md').read_text() for n in range(1,len(doc)+1)]
(out/'report.md').write_text('# ИСКУССТВО СОЗДАВАТЬ ЭНЕРГИЮ\n\nОтчет об устойчивом развитии Группы «ЛУКОЙЛ»\n\n2024\n\n'+'\n\n'.join(parts))
print('COMPLETE',flush=True)
