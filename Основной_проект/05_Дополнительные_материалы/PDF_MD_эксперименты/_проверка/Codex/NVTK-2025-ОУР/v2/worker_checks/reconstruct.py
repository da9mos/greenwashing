import sys,json,re,html,hashlib,collections
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
root=Path.cwd();out=root/'result';check=out/'_проверка';dest=check/'reconstructed';dest.mkdir(exist_ok=True)
s=json.load(open('source.json'));doc=pymupdf.open(s['source_pdf']);registry=json.load(open(check/'pages.json')); audit=[]
def esc(t):
 return html.escape(t,quote=False).replace('|','&#124;').replace('*','&#42;').replace('_','&#95;').replace('`','&#96;').replace('[','&#91;').replace(']','&#93;').replace('\ue000','<sup>').replace('\ue001','</sup>')
def textof(chars):
 lines={}
 for c in chars:lines.setdefault(c['line'],[]).append(c)
 return '\n'.join(''.join(('\ue000'+c['c']+'\ue001') if c.get('sup') else c['c'] for c in sorted(v,key=lambda c:c['idx'])).strip() for v in lines.values()).strip()
def inside(c,b):
 x,y=c['center'];return b[0]<=x<b[2] and b[1]<=y<b[3]
for n,p in enumerate(doc,1):
 chars=[]; blocks=[]
 for bi,b in enumerate(p.get_text('rawdict')['blocks']):
  if b['type']!=0:continue
  bc=[]
  for li,l in enumerate(b['lines']):
   for sp in l['spans']:
    for c in sp['chars']:
     box=c['bbox'];v=dict(c=c['c'],bbox=box,center=((box[0]+box[2])/2,(box[1]+box[3])/2),size=sp['size'],sup=bool(sp['flags']&1),idx=len(chars),block=bi,line=(bi,li));chars.append(v);bc.append(v)
  blocks.append((bi,b['bbox'],bc))
 removed={c['idx'] for c in chars if n>1 and c['center'][1]<80}
 tables=[]
 if n>1:
  for t in p.find_tables(strategy='lines').tables:
   if t.row_count<2 or t.col_count<2:continue
   tc=[c for c in chars if inside(c,t.bbox)]
   if len(tc)<40 or t.bbox[1]<100 or any(c['size']>=32 for c in tc):continue
   # Reconstruct column boundaries from geometric cells, rather than accepting false row-wide merges.
   xs=sorted(set(round(x,1) for cell in t.cells if cell for x in (cell[0],cell[2])))
   xs=[x for i,x in enumerate(xs) if i==0 or x-xs[i-1]>2]
   ys=sorted(set(round(y,1) for row in t.rows for y in (row.bbox[1],row.bbox[3])))
   ys=[y for i,y in enumerate(ys) if i==0 or y-ys[i-1]>2]
   if len(xs)>25 or len(ys)>100:continue
   rows=[];used=[]
   for ri,(y0,y1) in enumerate(zip(ys,ys[1:])):
    cells=[]
    # Join adjacent cells when a boundary would bisect an actual word.
    rowchars=[c for c in tc if y0-.05<=c['center'][1]<y1-.05]
    bounds=[xs[0]]
    for x in xs[1:-1]:
     crossing=False
     for c1,c2 in zip(rowchars,rowchars[1:]):
      if c1['line']==c2['line'] and c1['c'].isalnum() and c2['c'].isalnum() and c1['center'][0]<x<=c2['center'][0] and c2['bbox'][0]-c1['bbox'][2]<2:
       crossing=True;break
     if not crossing:bounds.append(x)
    bounds.append(xs[-1])
    if len({c['line'] for c in rowchars})==1 and len(rowchars)<100 and any(cell and cell[0]<=xs[0]+2 and cell[2]>=xs[-1]-2 and cell[1]<=y0+2 and cell[3]>=y1-2 for cell in t.cells):bounds=[xs[0],xs[-1]]
    for x0,x1 in zip(bounds,bounds[1:]):
     cc=[c for c in tc if x0-.05<=c['center'][0]<x1-.05 and y0-.05<=c['center'][1]<y1-.05];used.extend(c['idx'] for c in cc)
     span=sum(x0<=x<x1 for x in xs[:-1]);cells.append('<td'+(f' colspan="{span}"' if span>1 else '')+'>'+esc(textof(cc)).replace('\n','<br>')+'</td>')
    rows.append('<tr>'+''.join(cells)+'</tr>')
   if set(used)!=set(c['idx'] for c in tc):continue
   tables.append({'bbox':t.bbox,'text':'<table>\n'+'\n'.join(rows)+'\n</table>','ids':set(used),'index':min(used),'rows':len(ys)-1,'columns':len(xs)-1})
 claimed=set(); accepted=[]
 for t in tables:
  if t['ids']&claimed:continue
  claimed|=t['ids'];accepted.append(t)
 objects=[]
 for bi,bbox,bc in blocks:
  cc=[c for c in bc if c['idx'] not in claimed and c['idx'] not in removed]
  if not cc:continue
  text=textof(cc)
  if not text:continue
  size=max(c['size'] for c in cc);prefix='## ' if size>=34 and len(text)<450 else ''
  objects.append({'bbox':bbox,'text':prefix+esc(text).replace('\n','  \n'),'index':min(c['idx'] for c in cc),'ids':set(c['idx'] for c in cc)})
 objects+=accepted
 # Native content-stream order is retained within each spread half. Cross-spread blocks stay intact.
 objects.sort(key=lambda o:o['index'])
 text='\n\n'.join(o['text'] for o in objects)
 included=set().union(*(o['ids'] for o in objects))
 missing=[c for c in chars if c['idx'] not in included and c['idx'] not in removed and not c['c'].isspace()]
 assert not missing,(n,missing[:5])
 (dest/f'{n:04}.md').write_text(text+'\n')
 e=registry['pages'][n-1];e['markdown_chars']=len(text);e['tables']=len(accepted);e['table_shapes']=[{'rows':t['rows'],'columns':t['columns']} for t in accepted];e['text_layer_coverage']={'source_characters':len(chars),'unassigned_nonspace_characters':len(missing),'excluded_top_navigation_characters':len(removed)}
 # Extract actual printed labels from margin text, never infer by offset.
 labels=[]
 for bi,bbox,bc in blocks:
  if bbox[1]<80:
   for l in textof(bc).splitlines():
    if re.fullmatch(r'\d{1,3}',l.strip()):labels.append(l.strip())
 e['printed_page_labels']=labels
 e['issues']=['Полная построчная визуальная сверка не выполнена.','Порядок блоков сохранен по текстовому потоку PDF; сложные колонки и схемы требуют визуальной сверки.']
 if accepted:e['issues'].append('Табличные ячейки восстановлены по геометрии; все значения и объединения не сверены визуально.')
 audit.append({'pdf_page':n,'chars':len(chars),'tables':len(accepted),'missing_nonspace':len(missing)})
 (check/'pages.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2))
 print(n,'tables',len(accepted),'chars',len(chars),flush=True)
(check/'coverage.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
