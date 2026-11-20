import os,sys,json,hashlib,shutil,re,time,subprocess
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf as fitz,pymupdf4llm
pymupdf4llm.use_layout(False)
root=Path.cwd(); out=root/'result'; s=json.loads((root/'source.json').read_text()); doc=fitz.open(s['source_pdf']); index=json.loads(Path(s['index']).read_text()); src=Path(s['index']).parent
sha=hashlib.sha256(Path(s['source_pdf']).read_bytes()).hexdigest()
state={'source_pdf':s['source_pdf'],'source_sha256':sha,'physical_pages':len(doc),'method':'pymupdf4llm legacy; no layout models; local Tesseract for image-only cover; source-page images retained','pages':[]}
for i,page in enumerate(doc):
 n=i+1; image=f'page_{n:04}.png'; shutil.copy2(src/image,out/'assets'/image)
 raw=page.get_text(); (out/'_проверка/pages'/f'{n:04}.txt').write_text(raw)
 issues=['Полная визуальная сверка текста, таблиц, сносок и порядка колонок не выполнена.']
 try:
  md=pymupdf4llm.to_markdown(doc,pages=[i],show_progress=False,force_text=True,ignore_images=True,ignore_graphics=True,table_output='html')
 except Exception as e:
  md='\n\n'.join(b[4] for b in page.get_text('blocks') if len(b)>4);issues.append('Резервное извлечение блоков: '+str(e))
 if len(raw.strip())<30:
  ocr=subprocess.run(['tesseract',str(src/image),'stdout','-l','rus+eng','--psm','11'],capture_output=True,text=True).stdout
  (out/'_проверка/pages'/f'{n:04}.ocr.txt').write_text(ocr)
  md=ocr;issues.append('Текст изображения извлечён локальным OCR; требуется визуальная сверка.')
 # strip control characters, keep visible text and word continuity for soft hyphens
 md=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',md)
 md=re.sub('\u00ad[ \t]*\n[ \t]*','',md).replace('\u00ad','')
 md=re.sub(r'\[([^\]]+)\]\(#page-(\d+)\)',r'\1',md)
 links=[]
 for l in page.get_links():
  if l.get('uri'): links.append({'text':page.get_textbox(l['from']).strip(),'uri':l['uri']})
  elif 'page' in l and l['page']>=0: links.append({'text':page.get_textbox(l['from']).strip(),'target_pdf_page':l['page']+1})
 if links:
  md+='\n\n<details><summary>Ссылки этой страницы (из аннотаций PDF)</summary>\n\n'
  for l in links:
   label=l['text'].replace('\n',' ').replace('[','\\[').replace(']','\\]') or 'Переход'
   target=l.get('uri') or '#pdf-page-'+str(l['target_pdf_page'])
   md+=f'- [{label}]({target})\n'
  md+='\n</details>\n'
 note='> **Примечание к конвертации:** рабочая транскрипция; полная сверка страницы по оригиналу не завершена. Изображение ниже сохраняет исходную вёрстку и графику.\n\n'
 chunk=f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+note+md.strip()+f'\n\n![Оригинал физической страницы {n}](assets/{image})\n'
 (out/'_проверка/pages'/f'{n:04}.md').write_text(chunk)
 tables=page.find_tables().tables
 state['pages'].append({'pdf_page':n,'printed_page_label':None,'printed_page_label_note':'Не установлено визуально; смещение не применялось.','content_type':'image / OCR' if len(raw.strip())<30 else 'text layer with graphics; tables' if tables else 'text layer with graphics','text_layer_chars':len(raw),'extracted_markdown_chars':len(md),'detected_tables':len(tables),'conversion_status':'converted','review_status':'pending','issues':issues,'source_image':f'assets/{image}','links':links})
 (out/'_проверка/pages.json').write_text(json.dumps(state,ensure_ascii=False,indent=2))
 print(n,len(raw),len(md),len(tables),flush=True)
(out/'report.md').write_text('# ОДНА КОМАНДА — ОБЩИЕ ЦЕЛИ\n\nОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ 2023\n\n'+ '\n\n'.join((out/'_проверка/pages'/f'{n:04}.md').read_text() for n in range(1,len(doc)+1)))
