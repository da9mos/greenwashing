import sys,json,hashlib,re,shutil,time,subprocess,collections,html
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf as fitz
import pymupdf4llm
pymupdf4llm.use_layout(False)
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'result'; AUD=OUT/'_проверка'; AS=OUT/'assets'; CH=AUD/'pages'
AS.mkdir(exist_ok=True);CH.mkdir(exist_ok=True)
s=json.loads((ROOT/'source.json').read_text());doc=fitz.open(s['source_pdf']);index=json.loads(Path(s['index']).read_text()); inp=Path(s['index']).parent
sha=hashlib.sha256(Path(s['source_pdf']).read_bytes()).hexdigest()

def clean(t):
 return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',t).replace('\u00ad','').replace('\u00a0',' ')

def positional(page,rect):
 # Keep source lines and relative horizontal positions; avoid proportional-font collision.
 lines=[]
 for b in page.get_text('dict',clip=rect)['blocks']:
  for l in b.get('lines',[]):
   if abs(l['dir'][1])>.1:continue
   txt=clean(''.join(s['text'] for s in l['spans'])).strip()
   if txt:lines.append((l['bbox'][1],l['bbox'][0],l['bbox'][3],txt))
 rows=[]
 for y,x,y1,t in sorted(lines):
  if rows and abs(rows[-1][0]-y)<2.0: rows[-1][1].append((x,t))
  else:rows.append([y,[(x,t)]])
 result=[];prev=None
 for y,cells in rows:
  if prev is not None and y-prev>18:result.append('')
  line=''
  for x,t in sorted(cells):
   col=round((x-rect.x0)/2.65)
   if line:col=max(col,len(line)+2)
   line+=' '*max(0,col-len(line))+t
  result.append(line.rstrip());prev=y
 # remove constant left padding
 nonempty=[len(x)-len(x.lstrip()) for x in result if x.strip()]; pad=min(nonempty,default=0)
 return '\n'.join(x[pad:] for x in result).strip('\n')

def fenced(t):return '\n```text\n'+t+'\n```\n'

def table_strips(p,r):
 groups=collections.defaultdict(list)
 for d in p.get_drawings():
  z=d['rect']
  if z.width>160 and z.height<1 and r.x0<=z.x0 and z.x1<=r.x1:
   groups[(round(z.x0/5),round(z.x1/5))].append(z.y0)
 intervals=[]
 for ys in groups.values():
  ys=sorted(set(round(y,1) for y in ys));runs=[]
  for y in ys:
   if runs and y-runs[-1][-1]<48:runs[-1].append(y)
   else:runs.append([y])
  for run in runs:
   if len(run)>=3 and run[-1]-run[0]>16:
    a=max(r.y0,run[0]-25);b=min(r.y1,run[-1]+3)
    intervals.append((a,b))
 merged=[]
 for a,b in sorted(intervals):
  if merged and a<=merged[-1][1]+3:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
  else:merged.append((a,b))
 return merged

def mdclip(n,r):
 p=doc[n-1];m=(float(r.x0),float(r.y0),float(p.rect.width-r.x1),float(p.rect.height-r.y1))
 return clean(pymupdf4llm.to_markdown(doc,pages=[n-1],margins=m,ignore_images=True,force_text=True,show_progress=False)).strip()

def norm(t):return re.sub(r'[^\w]','',clean(t).lower())

def convert(n):
 p=doc[n-1];w=p.rect.width;h=p.rect.height;issues=[];modes=[];parts=[]
 if n==1: parts=['# ВРЕМЯ БЫТЬ ВМЕСТЕ\n\nОтчет о социальной деятельности Группы Газпром за 2023 год'];modes=['cover_manual']
 elif n in (132,133):
  parts=[clean(p.get_text(sort=False))];modes=['text_layer','tesseract_rus_eng']
  for k,im in enumerate(p.get_image_info()):
   r=fitz.Rect(im['bbox'])
   if r.get_area()/p.rect.get_area()<.1:continue
   pix=p.get_pixmap(matrix=fitz.Matrix(3,3),clip=r);impath=AUD/f'ocr-{n}-{k}.png';pix.save(impath)
   base=AUD/f'ocr-{n}-{k}'
   subprocess.run(['tesseract',str(impath),str(base),'-l','rus+eng','--psm','3'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   text=clean(base.with_suffix('.txt').read_text());parts.append(text)
  issues.append('OCR текста сканов выполнен; посимвольная сверка, печати и подписи требуют проверки по изображению.')
 else:
  wide=n in (9,10,108,109,110,111,112,113)
  rects=[p.rect] if wide else [fitz.Rect(0,0,w/2,h),fitz.Rect(w/2,0,w,h)]
  for k,r in enumerate(rects):
   if wide or 114<=n<=127 or n==135:
    parts.append(fenced(positional(p,r)));modes.append('coordinate_text')
   else:
    strips=table_strips(p,r);top=r.y0;sub=[]
    for a,b in strips:
     if a>top+2:sub.append(mdclip(n,fitz.Rect(r.x0,top,r.x1,a)))
     sub.append(fenced(positional(p,fitz.Rect(r.x0,a,r.x1,b))));top=b
    if top<r.y1-2:sub.append(mdclip(n,fitz.Rect(r.x0,top,r.x1,r.y1)))
    text='\n\n'.join(t for t in sub if t.strip());modes.append('markdown_with_coordinate_tables' if strips else 'markdown')
    # Audit lexical coverage; missing source blocks are not silently dropped.
    src=clean(p.get_text(clip=r)); words=re.findall(r'[\w]{3,}',src.lower()); cand=norm(text)
    missing=[word for word in words if norm(word) not in cand]
    ratio=len(missing)/max(1,len(words))
    if ratio>.025:
     text=fenced(positional(p,r));modes[-1]='coordinate_text_coverage_fallback'
     issues.append(f'Половина {k+1}: Markdown-экстракт пропускал {len(missing)}/{len(words)} слов; заменён координатным текстом.')
    parts.append(text)
  if any('coordinate' in x for x in modes):issues.append('Координатное текстовое представление сохраняет расположение ячеек; структура таблиц и порядок блоков полностью визуально не сверены.')
 if n!=1:issues.append('Полная визуальная сверка всей страницы не выполнена.')
 img=inp/f'page_{n:04d}.png'
 if not img.exists():raise FileNotFoundError(img)
 dest=AS/f'page-{n:03d}.png';shutil.copyfile(img,dest)
 content='\n\n'.join(parts)
 note='> Техническая пометка: рабочая транскрипция; полная сверка страницы по оригиналу ожидается.\n\n' if n!=1 else ''
 chunk=f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+note+content+f'\n\n[Изображение физической страницы {n}](assets/page-{n:03d}.png)\n'
 # Preserve annotation destinations without guessing labels.
 links=[]
 for l in p.get_links():
  if l.get('uri'):links.append(l['uri'])
  elif l.get('page',-1)>=0:links.append('#pdf-page-'+str(l['page']+1))
 if links:
  chunk+='\n<!-- Ссылки из аннотаций PDF; привязка к исходной области сохранена в реестре. -->\n\n'
  for j,l in enumerate(dict.fromkeys(links),1):chunk+=f'- [Переход {j}]({l})\n'
 (CH/f'{n:03d}.md').write_text(chunk)
 printed=[]
 for b in p.get_text('blocks'):
  if b[1]<45 and re.fullmatch(r'\s*\d+\s*[–−-]\s*\d+\s*',b[4]):printed.append(b[4].strip())
 return dict(pdf_page=n,printed_label=printed or None,content_type='mixed_scan' if n in (132,133) else 'cover' if n==1 else 'text_with_graphics',conversion_status='converted',review_status='pending',issues=issues,extraction_methods=modes,text_chars=len(content),asset=f'assets/page-{n:03d}.png',links=[{k:v for k,v in l.items() if k in ('kind','uri','page','from','to')} for l in []])

records=[]
for n in range(1,len(doc)+1):
 rec=convert(n);records.append(rec)
 (AUD/'pages.json').write_text(json.dumps(dict(source_pdf=s['source_pdf'],source_sha256=sha,physical_pages=len(doc),pages=records),ensure_ascii=False,indent=2))
 (OUT/'report.md').write_text('\n\n'.join((CH/f'{i:03d}.md').read_text() for i in range(1,n+1)))
 print(n,rec['text_chars'],rec['extraction_methods'],flush=True)
(AUD/'source-metadata.json').write_text(json.dumps(dict(source_pdf=s['source_pdf'],source_sha256=sha,physical_pages=len(doc),metadata=doc.metadata),ensure_ascii=False,indent=2))
