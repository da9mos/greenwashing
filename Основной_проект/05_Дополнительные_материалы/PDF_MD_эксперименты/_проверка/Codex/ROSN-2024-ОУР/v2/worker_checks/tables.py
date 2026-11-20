import sys,json,re,html,collections,shutil
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs');import pymupdf as f
r=Path('result');s=json.load(open('source.json'));d=f.open(s['source_pdf']);report=(r/'report.md').read_text();parts=re.split(r'(?=<!-- pdf_page: \d+ -->)',report);parts=[p for p in parts if p.strip()];assert len(parts)==135
for path in (r/'_проверка/before-tables').glob('*.md'):shutil.copyfile(path,r/'_проверка/pages'/path.name)
def clean(t):return html.escape(t.strip()).replace('\n','<br>')
def grid(p,xs,ymin=95,ymax=800):
 groups=collections.defaultdict(list)
 for dr in p.get_drawings():
  for item in dr['items']:
   if item[0]=='l':
    a,b=item[1:3]
    if abs(a.y-b.y)<.5 and ymin<a.y<ymax:groups[round(a.y,1)].append((min(a.x,b.x),max(a.x,b.x)))
   elif item[0]=='re':
    q=item[1]
    if q.width>xs[-1]-xs[0]-5:
     for y in [q.y0,q.y1]:
      if ymin<y<ymax:groups[round(y,1)].append((q.x0,q.x1))
 ys=[y for y,segs in groups.items() if sum(max(0,min(b,xs[-1])-max(a,xs[0])) for a,b in segs)> (xs[-1]-xs[0])*.94]
 ys=sorted(set([ymin]+ys));ys=[y for j,y in enumerate(ys) if not j or y-ys[j-1]>1]
 # Последняя линия таблицы, а не произвольная нижняя граница.
 if len(ys)<3:return ''
 rows=[]
 for ya,yb in zip(ys,ys[1:]):
  cells=[p.get_textbox(f.Rect(xa+.2,ya+.2,xb-.2,yb-.2)) for xa,xb in zip(xs,xs[1:])]
  if any(t.strip() for t in cells):rows.append('<tr>'+''.join('<td>'+clean(t)+'</td>' for t in cells)+'</tr>')
 return '<table>\n'+'\n'.join(rows)+'\n</table>'
def detected_html(p,t):
 xs=sorted(set(round(c[v],2) for c in t.cells for v in [0,2]));ys=sorted(set(round(c[v],2) for c in t.cells for v in [1,3]));seen=set();rows=[]
 for row in t.rows:
  cells=[]
  for c in row.cells:
   if c is None:continue
   q=tuple(round(v,2) for v in c)
   if q in seen:continue
   seen.add(q);cs=max(1,xs.index(q[2])-xs.index(q[0]));rs=max(1,ys.index(q[3])-ys.index(q[1]));text=p.get_textbox(f.Rect(c))
   cells.append(f'<td colspan="{cs}" rowspan="{rs}">'+clean(text)+'</td>')
  rows.append('<tr>'+''.join(cells)+'</tr>')
 return '<table>\n'+'\n'.join(rows)+'\n</table>'
counts={};records=[]
for n,p in enumerate(d,1):
 sec=parts[n-1];extra=[]
 if 117<=n<=127:
  xs=[39.685,113.5,654.9,1150.87] if n<=118 else [39.685,181.417,651.024,857.857,1150.87]
  ymin=238 if n==117 else 94
  table=grid(p,xs,ymin)
  if table:
   old=(r/f'_проверка/pages/{n:04}.md').read_text().strip()
   prefix=p.get_text(clip=f.Rect(0,70,p.rect.width,ymin)).strip() if n==117 else ''
   new=prefix+'\n\n'+table;sec=sec.replace(old,new,1);(r/f'_проверка/pages/{n:04}.md').write_text(new+'\n');counts[n]=1
 else:
  try:
   for t in p.find_tables(clip=f.Rect(0,70,p.rect.width,805),strategy='lines').tables:
    if t.row_count>=2 and t.col_count>=2 and (t.bbox[2]-t.bbox[0])>120:
     extra.append(detected_html(p,t))
  except Exception as e:print(n,e,flush=True)
  if extra:
   addition='\n\n<details><summary>Техническое приложение: табличная структура, извлечённая автоматически; требует сверки</summary>\n\n'+'\n\n'.join(extra)+'\n\n</details>\n\n'
   sec=sec.replace(f'![Оригинал физической страницы {n}]',addition+f'![Оригинал физической страницы {n}]');counts[n]=len(extra)
 parts[n-1]=sec
 raw=p.get_text();nums=[]
 for b in p.get_text('blocks'):
  if b[1]>800:nums+=re.findall(r'(?m)^\s*(\d{1,3})\s*$',b[4])
 issues=[] if n in [1,135] else ['Полная сверка текста, чисел, таблиц, сносок и порядка блоков по оригиналу не завершена. Возможны ошибки переноса слов и дефисов.']
 if n==113:issues+=['Тело скана распознано Tesseract rus+eng; полная сверка OCR не завершена.']
 if n in counts:issues+=['Табличная структура получена по координатам и линиям PDF; все ячейки и объединения требуют сверки.']
 records.append({'pdf_page':n,'printed_page':nums or None,'content_type':'mixed_scan_text' if n==113 else ('raster_cover' if n in [1,135] else 'text_graphics_tables'),'conversion_status':'converted','review_status':'checked' if n in [1,135] else 'pending','issues':issues,'text_chars':len(raw),'tables_extracted':counts.get(n,0),'visual_review_scope':'Полностью прочитана обложка' if n in [1,135] else ('Просмотр отдельных областей; полной сверки нет' if n in [3,8,31,113,114,120] else 'Полная визуальная сверка не выполнена')})
 print(n,counts.get(n,0),flush=True)
(r/'report.md').write_text('\n\n'.join(parts));(r/'_проверка/pages.json').write_text(json.dumps({'source_pdf':s['source_pdf'],'sha256':__import__('hashlib').sha256(Path(s['source_pdf']).read_bytes()).hexdigest(),'physical_pages':135,'status':'working_version','pages':records},ensure_ascii=False,indent=2));(r/'_проверка/table-counts.json').write_text(json.dumps(counts,indent=2));print('tables',sum(counts.values()))
