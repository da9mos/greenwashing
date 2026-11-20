import json,hashlib,shutil,re,time,collections,subprocess,os
from pathlib import Path
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
ROOT=Path.cwd(); out=ROOT/'result';check=out/'_проверка';assets=out/'assets';assets.mkdir(exist_ok=True)
s=json.load(open('source.json'));src=Path(s['source_pdf']); idx=json.load(open(s['index']));base=Path(s['index']).parents[3]
d=pymupdf.open(src)
meta={'source_pdf':str(src),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'physical_page_count':len(d),'method':'PyMuPDF4LLM legacy, layout model disabled; separate left/right logical pages; local Tesseract rus+eng for scans','pages':[]}
(check/'source.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
for i,p in enumerate(d):
 n=i+1; png=assets/f'page_{n:04}.png'; origin=Path(s['index']).parent/f'page_{n:04}.png'
 shutil.copy2(origin,png)
 raw=p.get_text(); (check/'pages'/f'{n:04}.txt').write_text(raw)
 halves=[p.rect] if p.rect.width<800 else [pymupdf.Rect(0,0,p.rect.width/2,p.rect.height),pymupdf.Rect(p.rect.width/2,0,p.rect.width,p.rect.height)]
 texts=[];tables=0;issues=['Полная визуальная сверка текста, таблиц, примечаний и графики не выполнена.']
 for j,r in enumerate(halves):
  sub=pymupdf.open();sub.new_page(width=r.width,height=r.height).show_pdf_page(pymupdf.Rect(0,0,r.width,r.height),d,i,clip=r)
  try:
   md=pymupdf4llm.to_markdown(sub,ignore_images=True,ignore_graphics=False,show_progress=False,table_output='markdown',margins=0)
  except Exception as e:
   md=sub[0].get_text(sort=True);issues.append('Резервное извлечение текстового слоя: '+str(e))
  # Remove only invisible control characters, retain word punctuation and line wraps.
  md=''.join(c for c in md if c in '\n\t' or ord(c)>=32)
  md=re.sub(r'\n{4,}','\n\n\n',md).strip()
  texts.append(md)
  tables+=len(sub[0].find_tables().tables)
  sub.close()
 if n in [146,147,148]:
  ocr=[]
  for j,r in enumerate(halves):
   im=check/'pages'/f'{n:04}_{j+1}_ocr.png';p.get_pixmap(matrix=pymupdf.Matrix(3,3),clip=r).save(im)
   proc=subprocess.run(['tesseract',str(im),'stdout','-l','rus+eng','--psm','3'],capture_output=True,text=True,env={**os.environ,'OMP_THREAD_LIMIT':'2'})
   (check/'pages'/f'{n:04}_{j+1}_ocr.txt').write_text(proc.stdout)
   ocr.append(proc.stdout.strip())
  # Header/footer text layer is repeated by OCR; use OCR of the entire body as primary transcript.
  texts=['> Техническая пометка: текст сканированного заключения распознан локальным OCR; посимвольная сверка не завершена.\n\n'+'\n\n'.join(ocr)]
  issues.append('OCR сканированного тела заключения; возможны ошибки букв, чисел и структуры списков.')
 links=[]
 for l in p.get_links():
  if l.get('uri'):links.append(l['uri'])
  elif l.get('page',-1)>=0:links.append('#pdf-page-'+str(l['page']+1))
 links=list(dict.fromkeys(links))
 body='\n\n'.join(texts)
 if links:
  body+='\n\n<details><summary>Ссылки и переходы из аннотаций PDF</summary>\n\n'+'\n\n'.join(f'- [{x}]({x})' for x in links)+'\n\n</details>'
 body+=f'\n\n<details><summary>Оригинал физической страницы {n} — графика и визуальная опора</summary>\n\n![Оригинал физической страницы {n}](assets/page_{n:04}.png)\n\n</details>\n'
 (check/'pages'/f'{n:04}.md').write_text(body)
 footer=[]
 for b in p.get_text('blocks'):
  if b[1]>p.rect.height-40:
   footer+=re.findall(r'(?m)^\d{1,3}\s*$',b[4])
 rec={'pdf_page':n,'printed_labels':[x.strip() for x in footer],'content_type':'mixed_scan' if n in [146,147,148] else ('text_and_graphics' if p.get_images() else 'text_tables_vectors'),'text_layer_chars':len(raw),'logical_parts':len(halves),'detected_tables':tables,'conversion_status':'converted','review_status':'pending','issues':issues,'source_image':f'assets/page_{n:04}.png','markdown_chars':len(body)}
 meta['pages'].append(rec);(check/'pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
 print(f'{n}/152 {len(body)} chars tables={tables}',flush=True)
# Assembly is recoverable from one saved file per physical page.
head='# Отчет о социальной деятельности Группы Газпром\n\n2025\n\n> Техническое примечание: рабочая полная конвертация 152 физических страниц. Текстовый слой извлечён, тело сканов 146–148 распознано локальным OCR. Полная визуальная сверка не выполнена; подробные статусы и ограничения — в `_проверка/pages.json`. Оригиналы страниц сохранены как визуальная опора.\n\n'
report=head+'\n\n'.join(f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+(check/'pages'/f'{n:04}.md').read_text() for n in range(1,153))
(out/'report.md').write_text(report)
print('ASSEMBLED',len(report))
