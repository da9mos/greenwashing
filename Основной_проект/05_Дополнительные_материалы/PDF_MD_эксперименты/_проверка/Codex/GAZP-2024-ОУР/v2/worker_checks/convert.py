import json, pathlib, hashlib, shutil, re, collections, html, time
import pymupdf, pymupdf4llm
pymupdf4llm.use_layout(False)  # only geometry and text; no layout model
ROOT=pathlib.Path.cwd(); OUT=ROOT/'result'; AUD=OUT/'_проверка'; AS=OUT/'assets'; AS.mkdir(exist_ok=True)
s=json.load(open(ROOT/'source.json')); idx=json.load(open(s['index'])); base=pathlib.Path(s['index']).parent
D=pymupdf.open(s['source_pdf']); sha=hashlib.sha256(pathlib.Path(s['source_pdf']).read_bytes()).hexdigest()
assert len(D)==150 and sha==idx['source_sha256']

def norm(t):
 t=html.unescape(re.sub(r'<[^>]+>','',t)).lower().replace('ё','е')
 return re.sub(r'[^\w]','',t)

def clean(t):
 t=t.replace('\x07','').replace('\x08','').replace('\ufeff','').replace('\u00ad','')
 # remove only standalone converter artifacts (arrow glyph mapped to 2)
 t=re.sub(r'^#{1,6} 2\s*$', '', t, flags=re.M)
 t=re.sub(r'\n{3,}','\n\n',t)
 return t.strip()

def get_half(p,side):
 w=p.rect.width
 clip=pymupdf.Rect(side*w/2,65,(side+1)*w/2,795) if w>800 else p.rect
 q=pymupdf.open(); t=q.new_page(width=clip.width,height=clip.height)
 t.show_pdf_page(t.rect,D,p.number,clip=clip)
 return q,clip

pages=[]; parts=[]
for n,p in enumerate(D,1):
 t0=time.time(); record={'pdf_page':n,'printed_labels':[], 'content_type':[], 'conversion_status':'converted','review_status':'pending','issues':[], 'method':'native text; geometry-only pymupdf4llm legacy', 'text_chars':len(p.get_text())}
 image=f'page_{n:04}.png'; shutil.copy2(base/image,AS/image)
 native=p.get_text('dict'); topnums=[]
 for b in native['blocks']:
  for l in b.get('lines',[]):
   text=''.join(x['text'] for x in l['spans']).strip()
   if l['bbox'][1]>795 and re.fullmatch(r'\d{1,3}',text):topnums.append((l['bbox'][0],text))
 record['printed_labels']=[x[1] for x in sorted(topnums)]
 record['content_type']=['spread' if p.rect.width>800 else 'single_page','native_text']
 if p.get_images():record['content_type'].append('raster_images')
 chapter=[]; omitted=[]; tablecount=0
 for side in range(2 if p.rect.width>800 else 1):
  q,clip=get_half(p,side); qp=q[0]
  tabs=qp.find_tables(strategy='lines_strict');tablecount+=len(tabs.tables)
  try:
   md=pymupdf4llm.to_markdown(q,ignore_images=True,ignore_graphics=True,detect_bg_color=False,ignore_alpha=True,show_progress=False,ignore_code=True,fontsize_limit=0,table_strategy='lines_strict')
  except Exception as e:
   md=qp.get_text(sort=True);record['issues'].append('Markdown extraction fallback: '+str(e))
  md=clean(md)
  # Detect native lines not represented in Markdown. Keep them explicitly, not silently discard.
  z=norm(md); missing=[]
  for b in qp.get_text('dict')['blocks']:
   ls=[]
   for l in b.get('lines',[]):
    txt=''.join(x['text'] for x in l['spans']).strip();k=norm(txt)
    if len(k)>2 and k not in z:ls.append(txt)
   if ls:missing.append({'bbox':[round(v,2) for v in b['bbox']], 'text':'\n'.join(ls)})
  if missing:
   omitted.extend([dict(side=side+1,**b) for b in missing])
   md+='\n\n> **Техническое примечание к конвертации.** Следующие фрагменты текстового слоя не сопоставлены с основным извлечением. Их положение и связи требуют сверки по изображению этой страницы.\n\n'
   for b in missing:
    md+='\n'+html.escape(b['text']).replace('\n','  \n')+'\n'
  # Read scanned embedded documents using local Tesseract, separately inserted at the correct half.
  if 144<=n<=147:
   crops=[]
   for j,im in enumerate(p.get_image_info(xrefs=True)):
    r=pymupdf.Rect(im['bbox'])
    if r.get_area()>40000 and (r.x0+r.x1)/2>=clip.x0 and (r.x0+r.x1)/2<clip.x1:
     crops.append((j,r,im))
   for j,r,im in crops:
    import subprocess
    fn=AUD/f'ocr_{n:04}_{side+1}.png'; pix=p.get_pixmap(matrix=pymupdf.Matrix(3,3),clip=r&p.rect);pix.save(fn)
    op=AUD/f'ocr_{n:04}_{side+1}'
    subprocess.run(['tesseract',str(fn),str(op),'-l','rus+eng','--psm','3'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    ocr=op.with_suffix('.txt').read_text().strip(); record.setdefault('ocr',[]).append({'side':side+1,'chars':len(ocr),'file':op.with_suffix('.txt').name})
    md+='\n\n> **Техническое примечание:** текст вложенного сканированного документа ниже распознан локально (Tesseract, rus+eng); OCR ещё не полностью сверен с изображением. Подписи и печати доступны на изображении физической страницы.\n\n'+ocr+'\n'
   record['content_type'].append('scanned_body');record['method']+='; local Tesseract rus+eng'
  chapter.append(md)
  q.close()
 if tablecount: record['content_type'].append('tables');record['detected_tables']=tablecount
 if omitted:
  record['unmatched_native_blocks']=omitted;record['issues'].append('Фрагменты текстового слоя добавлены отдельно; проверить порядок и отсутствие повторов.')
 record['issues'].append('Полная постраничная визуальная сверка текста, таблиц, сносок и графики не завершена.')
 # Keep all destinations exactly from PDF annotations, no inferred printed-page offsets.
 links=[]
 for l in p.get_links():
  target=None
  if l.get('uri'):target=l['uri']
  elif l.get('kind')==pymupdf.LINK_GOTO and l.get('page',-1)>=0:target=f'#pdf-page-{l["page"]+1}'
  if target and target not in [x['target'] for x in links]:
   visible=p.get_textbox(l['from']).strip().replace('\n',' ')
   links.append({'text':visible,'target':target})
 record['links']=links
 md='\n\n'.join(chapter)
 if links:
  md+='\n\n<details><summary>Ссылки из аннотаций PDF (технический реестр страницы)</summary>\n\n'
  for l in links:
   label=l['text'] or 'Переход из аннотации';label=label.replace('[','\\[').replace(']','\\]')
   md+=f'- [{label}](<{l["target"]}>)\n'
  md+='\n</details>'
 md=f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+md+f'\n\n<details><summary>Оригинал физической страницы {n} — визуальная опора</summary>\n\n![Оригинал физической страницы {n}](assets/{image})\n\n</details>\n'
 (AUD/'pages'/f'{n:04}.md').write_text(md)
 parts.append(md);pages.append(record)
 (AUD/'pages.json').write_text(json.dumps({'source_sha256':sha,'page_count':150,'pages':pages},ensure_ascii=False,indent=2))
 (OUT/'report.md').write_text('# Отчет о социальной деятельности Группы Газпром\n\n2024\n\n> **Техническая пометка:** рабочая версия полной конвертации. Текст извлечён постранично; полная сверка по оригиналу не завершена. Статусы и нерешённые места: `_проверка/pages.json`. Изображения страниц служат визуальной опорой.\n\n'+'\n\n'.join(parts))
 print(f'{n}/150: {len(md)} chars, {tablecount} tables, {len(omitted)} unmatched blocks, {time.time()-t0:.1f}s',flush=True)
(AUD/'provenance.json').write_text(json.dumps({'source_pdf':s['source_pdf'],'source_index':s['index'],'sha256':sha,'pages':len(D),'extractor':'pymupdf4llm legacy, use_layout(False)','ocr':'local tesseract rus+eng for embedded scans, no downloads or external API'},ensure_ascii=False,indent=2))
