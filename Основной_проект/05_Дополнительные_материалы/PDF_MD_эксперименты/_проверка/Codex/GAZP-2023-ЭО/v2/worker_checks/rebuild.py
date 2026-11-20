import sys,json,re,html,collections
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
root=Path(__file__).resolve().parents[2];out=root/'result';check=out/'_проверка';d=pymupdf.open(json.loads((root/'source.json').read_text())['source_pdf'])
states=json.loads((check/'pages.json').read_text())['pages']
def esc(s):return html.escape(s).replace('\n','<br>')
def tablemd(t):
 data=t.extract();keep=[j for j in range(t.col_count) if any(row[j] and row[j].strip() for row in data)]
 if len(keep)<2:return None
 data=[[row[j] for j in keep] for row in data]
 parts=['<table>','<tbody>']
 for row in data:
  if not any(row):continue
  parts.append('<tr>')
  if row[0] and all(v is None for v in row[1:]):parts.append(f'<td colspan="{len(keep)}">{esc(row[0])}</td>')
  else:
   for c in row:parts.append('<td>'+esc(c or '')+'</td>')
  parts.append('</tr>')
 parts+=['</tbody>','</table>'];return '\n'.join(parts)
def layout(p,rect):
 # Spatial text as fallback for graphics without an unambiguous table grid.
 words=p.get_text('words',clip=rect);lines=[]
 for w in sorted(words,key=lambda w:(round(w[3]/2)*2,w[0])):
  found=next((l for l in lines if abs(l[0]-w[3])<2.5),None)
  if found is None:lines.append([w[3],[w]])
  else:found[1].append(w)
 output=[];step=2.4
 for _,ws in sorted(lines):
  line=''
  for w in sorted(ws,key=lambda w:w[0]):
   pos=round((w[0]-rect.x0)/step);line+=' '*max(1 if line else 0,pos-len(line))+w[4]
  output.append(line.rstrip())
 return '```text\n'+'\n'.join(output)+'\n```'
def line_text(l):
 spans=sorted(l['spans'],key=lambda s:s['bbox'][0]);parts=[]
 for s in spans:
  txt=html.escape(s['text'],quote=False)
  if s['flags']&1:txt='<sup>'+txt+'</sup>'
  parts.append(txt)
 return ''.join(parts).strip()
def block_text(lines):
 texts=[line_text(l) for l in lines];text=''
 for txt in texts:
  if not txt:continue
  if not text:text=txt
  elif re.match(r'^[–—]\s',txt):text+='\n\n'+txt
  elif text.endswith('\u00ad'):text=text[:-1]+txt
  elif text.endswith('-'):text+='\n'+txt
  else:text+=' '+txt
 text=text.replace('\u00ad','')
 if len(texts)>3 and sum(bool(re.match(r'^(?:ООО|АО|ПАО|ОАО|ЗАО|ОсОО|МКООО|Группа|Газпром)',t)) for t in texts)>len(texts)/2:
  text='\n'.join('- '+t for t in texts)
 size=max((s['size'] for l in lines for s in l['spans']),default=8)
 if size>=11:text='## '+text
 return text
for n in range(3,76):
 p=d[n-1];mid=314.5 if n%2 else 280.5
 ts=p.find_tables(strategy='lines').tables
 ts=sorted(ts,key=lambda t:pymupdf.Rect(t.bbox).get_area(),reverse=True)
 chosen=[]
 for candidate in ts:
  r=pymupdf.Rect(candidate.bbox)
  if not any((r & pymupdf.Rect(other.bbox)).get_area()>0.25*r.get_area() for other in chosen):chosen.append(candidate)
 ts=chosen
 if n in {10,11,39}:ts=[]
 objects=[];rects=[];tables=[]
 for t in ts:
  r=pymupdf.Rect(t.bbox)
  if r.y0>801 or r.height<5:continue
  md=tablemd(t)
  if md:
   rects.append(r);tables.append((r,md,t))
 # Diagrams are preserved spatially, avoiding false table grids that split words.
 if n in {10,11,39}:
  for drawing in p.get_drawings():
   rr=drawing['rect'];fill=drawing.get('fill')
   if fill and rr.width>450 and rr.height>100 and .89<fill[0]<.93 and .92<fill[1]<.96:
    rects.append(rr);objects.append((rr,layout(p,rr),'diagram'))
 # Keep all text in detected tables. Fallback if mechanical table omitted any characters.
 for r,md,t in tables:
  a=collections.Counter(c for c in p.get_text(clip=r) if not c.isspace());b=collections.Counter(c for row in t.extract() for cell in row for c in (cell or '') if not c.isspace())
  missing=sum((a-b).values())
  if missing:md+='\n\n'+layout(p,r)
  objects.append((r,md,'table'))
 for b in p.get_text('dict')['blocks']:
  if b['type']!=0:continue
  remaining=[]
  for l in b['lines']:
   r=pymupdf.Rect(l['bbox']);cx=(r.x0+r.x1)/2;cy=(r.y0+r.y1)/2
   if l['dir'][0]<0.5:continue # vertical running report title
   if r.y0>803:continue # folio
   if any(rr.contains(pymupdf.Point(cx,cy)) for rr in rects):continue
   remaining.append(l)
  if remaining:
   r=pymupdf.Rect(remaining[0]['bbox'])
   for l in remaining[1:]:r|=pymupdf.Rect(l['bbox'])
   objects.append((r,block_text(remaining),'text'))
 # Full-width objects separate reading bands; narrow blocks read by column within each band.
 wide=[o for o in objects if o[0].x0<mid-10 and o[0].x1>mid+10]
 narrow=[o for o in objects if o not in wide]
 wide.sort(key=lambda o:(o[0].y0,o[0].x0))
 result=[];bottom=0
 def band(items):
  return sorted(items,key=lambda o:(0 if (o[0].x0+o[0].x1)/2<mid else 1,o[0].y0,o[0].x0))
 for w in wide:
  before=[o for o in narrow if (o[0].y0+o[0].y1)/2<w[0].y0+1]
  result.extend(band(before));narrow=[o for o in narrow if o not in before];result.append(w)
 result.extend(band(narrow))
 # Page 9 has rowwise cross-column continuation defined by horizontal separators.
 if n==9:
  headers=[o for o in objects if o[0].y0<130];result=sorted(headers,key=lambda o:o[0].y0)
  for low,high in [(130,260),(260,380),(380,801)]:result+=band([o for o in objects if low<=o[0].y0<high])
 text='\n\n'.join(o[1] for o in result if o[1].strip())+'\n'
 old=check/'pages'/f'{n:04}.md';old.rename(check/'pages'/f'{n:04}.legacy.md');old.write_text(text)
 st=states[n-1];st['method']='PDF text blocks; coordinate reading bands and columns; vector-line table extraction';st['tables_extracted']=len(tables);st['converted_chars']=len(text)
 st['issues'].append('Порядок колонок восстановлен по координатам; сложные объединения, сноски и связь значений графиков требуют полной сверки.')
 # Actual printed folio comes from source, never inferred from an offset.
 folios=[p.get_text(clip=(0,804,p.rect.width,p.rect.height)).strip()];st['printed_page']=folios[0] or None
 print(n,len(text),len(tables),flush=True)
(check/'pages.json').write_text(json.dumps({'pages':states},ensure_ascii=False,indent=2))
