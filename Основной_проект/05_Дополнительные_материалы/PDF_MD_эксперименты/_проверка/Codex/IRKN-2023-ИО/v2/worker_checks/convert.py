import sys,json,hashlib,re,shutil,subprocess,time,html
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
base=Path.cwd(); out=base/'result'; s=json.load(open('source.json')); src=Path(s['source_pdf']); root=Path(s['index']).parents[3]; reg=json.load(open(s['index'])); doc=pymupdf.open(src)
manifest={'source_pdf':str(src),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'physical_pages':len(doc),'method':'PyMuPDF / pymupdf4llm legacy (layout model disabled); Tesseract rus+eng for raster regions','pages':[]}
for idx,p in enumerate(doc):
 n=idx+1; issues=['Полная визуальная сверка страницы по оригиналу не выполнена.']; imagefile=out/'assets'/f'page_{n:04}.png'; entry=reg['pages'][idx]; ip=root/entry['image'];shutil.copy2(ip,imagefile)
 try:
  md=pymupdf4llm.to_markdown(doc,pages=[idx],show_progress=False,force_text=True,ignore_images=True,write_images=False,table_strategy='lines_strict')
 except Exception as e:
  md=p.get_text(sort=True);issues.append('Резервное извлечение текстового слоя: '+str(e))
 # Preserve source reading of raster text separately, without replacing body by an image.
 ocr=[]
 for k,im in enumerate(p.get_image_info(xrefs=True)):
  r=pymupdf.Rect(im['bbox']) & p.rect
  if r.is_empty or r.width<35 or r.height<20:continue
  crop=out/'_проверка/pages'/f'{n:04}_image_{k:02}.png';p.get_pixmap(matrix=pymupdf.Matrix(3,3),clip=r).save(crop)
  proc=subprocess.run(['tesseract',str(crop),'stdout','-l','rus+eng','--psm','3'],capture_output=True,text=True)
  txt=proc.stdout.strip();(crop.with_suffix('.txt')).write_text(txt)
  if txt:
   ocr.append((k,txt)); issues.append(f'Текст растрового блока {k+1} распознан OCR; порядок и символы требуют сверки.')
 if ocr:
  md+='\n\n> Техническая пометка: ниже приведено OCR-чтение текста из растровых блоков; возможны ошибки распознавания.\n\n'
  for k,txt in ocr:md+=f'\n<!-- raster_block: {k+1} -->\n\n'+txt+'\n'
 if p.get_images():issues.append('Смешанная страница: растровая графика сохранена в полном изображении страницы.')
 tables=p.find_tables(strategy='lines_strict').tables
 if tables:issues.append('Таблицы извлечены автоматически; объединённые ячейки и соответствие столбцов требуют визуальной сверки.')
 # save links as annotations, retaining exact targets, without guessing visible-text associations
 links=[]
 for link in p.get_links():
  if link.get('uri'):links.append((link['uri'],link['uri']))
  elif link.get('page',-1)>=0:links.append((f"Переход на физическую страницу {link['page']+1}",f"#pdf-page-{link['page']+1}"))
 if links:
  md+='\n\n<!-- PDF link annotations -->\n\n'+'\n'.join(f'- [{html.escape(a)}]({b})' for a,b in dict.fromkeys(links))+'\n'
 md+=f'\n\n<details><summary>Изображение исходной страницы {n}</summary>\n\n![Страница {n}](assets/page_{n:04}.png)\n\n</details>\n'
 (out/'_проверка/pages'/f'{n:04}.md').write_text(md)
 chars=len(p.get_text().strip()); body=sum(len(t) for _,t in ocr)
 row={'pdf_page':n,'printed_page':None,'content_type':'mixed' if p.get_images() else 'text','text_layer_chars':chars,'ocr_chars':body,'tables_detected':len(tables),'conversion_status':'converted','review_status':'pending','issues':issues}
 if p.get_images() and chars<150 and body<30:row['conversion_status']='pending';row['issues'].append('Недостаточно распознанного текста растровой области; требуется визуальное чтение.')
 manifest['pages'].append(row)
 (out/'_проверка/pages.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 parts=['# Интегрированный годовой отчет АО «ИНК-Капитал» за 2023 год\n\n> Техническая пометка: рабочая конвертация всех физических страниц. Непроверенные OCR-блоки помечены; полная сверка с оригиналом не выполнена. Состояние каждой страницы — в `_проверка/pages.json`.\n']
 for q in manifest['pages']:
  nn=q['pdf_page'];parts.append(f'\n<!-- pdf_page: {nn} -->\n<a id="pdf-page-{nn}"></a>\n\n'+(out/'_проверка/pages'/f'{nn:04}.md').read_text())
 (out/'report.md').write_text('\n'.join(parts))
 print(n,chars,body,len(tables),flush=True)
