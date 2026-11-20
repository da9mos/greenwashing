import json,re,shutil,subprocess,os,collections,html
from pathlib import Path
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
out=Path('result');check=out/'_проверка';s=json.load(open('source.json'));d=pymupdf.open(s['source_pdf']);meta=json.load(open(check/'pages.json'))
shutil.copy2(out/'report.md',check/'report.initial.md')
coverage=[]
for i,p in enumerate(d):
 n=i+1;rec=meta['pages'][i];old=(check/'pages'/f'{n:04}.md').read_text();tail=old[old.index('<details><summary>Ссылки'):] if '<details><summary>Ссылки' in old else old[old.index('<details><summary>Оригинал'):]
 halves=[p.rect] if p.rect.width<800 else [pymupdf.Rect(0,0,p.rect.width/2,p.rect.height),pymupdf.Rect(p.rect.width/2,0,p.rect.width,p.rect.height)]
 if n in [146,147,148,149]:
  if n==149:
   for j,r in enumerate(halves):
    im=check/'pages'/f'{n:04}_{j+1}_ocr.png';p.get_pixmap(matrix=pymupdf.Matrix(3,3),clip=r).save(im)
    proc=subprocess.run(['tesseract',str(im),'stdout','-l','rus+eng','--psm','3'],capture_output=True,text=True,env={**os.environ,'OMP_THREAD_LIMIT':'2'})
    (check/'pages'/f'{n:04}_{j+1}_ocr.txt').write_text(proc.stdout)
  body='> Техническая пометка: текст тела сканированного заключения распознан локальным OCR; возможны ошибки распознавания, полная сверка не выполнена.\n\n'+'\n\n'.join((check/'pages'/f'{n:04}_{j+1}_ocr.txt').read_text().strip() for j in range(2))
  rec['content_type']='mixed_scan';rec['issues']=['Полная визуальная сверка OCR тела заключения не выполнена. Возможны ошибки букв, чисел, подписей и списков.']
 else:
  parts=[];layouts=[];cnt=0
  for j,r in enumerate(halves):
   sub=pymupdf.open();sub.new_page(width=r.width,height=r.height).show_pdf_page(pymupdf.Rect(0,0,r.width,r.height),d,i,clip=r)
   md=pymupdf4llm.to_markdown(sub,ignore_images=True,ignore_graphics=True,table_strategy=None,show_progress=False)
   md=''.join(c for c in md if c in '\n\t' or ord(c)>=32);md=re.sub(r'\n{4,}','\n\n\n',md).strip();parts.append(md)
   raw=sub[0].get_text();numerics=len(re.findall(r'(?m)^\s*[–−+\d][\d\s,.%–−+]*\s*$',raw))
   tabs=len(sub[0].find_tables().tables);cnt+=tabs
   if tabs or numerics>=12:
    temp=check/'pages'/f'{n:04}_{j+1}.pdf';sub.save(temp)
    proc=subprocess.run(['pdftotext','-layout','-enc','UTF-8',str(temp),'-'],capture_output=True,text=True)
    layout=proc.stdout.replace('\f','').rstrip();(check/'pages'/f'{n:04}_{j+1}_layout.txt').write_text(layout);temp.unlink()
    layouts.append(f'<details><summary>Техническое представление: исходное расположение текста и табличных колонок, часть {j+1}</summary>\n\n<pre>\n{html.escape(layout)}\n</pre>\n\n</details>')
   sub.close()
  body='\n\n'.join(parts)
  # Character multiset is only a loss detector, never a source review.
  norm=lambda t:collections.Counter(re.sub(r'[^\w]','',t.lower()))
  missing=norm(p.get_text())-norm(body)
  coverage.append({'pdf_page':n,'missing_character_multiset_count':sum(missing.values()),'note':'Механический индикатор охвата; не подтверждает точность и порядок чтения.'})
  if sum(missing.values())>15:
   rec['issues'].append(f'Механический индикатор: {sum(missing.values())} символов текстового слоя отсутствуют в основном представлении; см. альтернативный текст и оригинал.')
   if not layouts:
    # Retain a fallback transcription for any mechanically uncovered text.
    layouts.append('<details><summary>Техническое представление текстового слоя для проверки охвата</summary>\n\n<pre>'+html.escape(p.get_text())+'</pre>\n\n</details>')
  if layouts:
   body+='\n\n'+'\n\n'.join(layouts);rec['issues'].append('Таблицы/числовая вёрстка сохранены также моноширинным текстом с расположением колонок. Связи ячеек и многоуровневые шапки полностью не сверены.')
  rec['detected_tables']=cnt
 body+='\n\n'+tail
 (check/'pages'/f'{n:04}.md').write_text(body);rec['markdown_chars']=len(body)
 (check/'pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2));print(n,flush=True)
head='# Отчет о социальной деятельности Группы Газпром\n\n2025\n\n> Техническое примечание: рабочая полная конвертация 152 физических страниц. Текстовый слой извлечён; тело сканов на физических страницах 146–149 распознано локальным OCR. Полная визуальная сверка не выполнена. Статусы и ограничения каждой страницы — в `_проверка/pages.json`. Дополнительные моноширинные представления сохраняют расположение табличных колонок; изображения оригиналов служат визуальной опорой.\n\n'
(out/'report.md').write_text(head+'\n\n'.join(f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+(check/'pages'/f'{n:04}.md').read_text() for n in range(1,153)))
(check/'coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2))
