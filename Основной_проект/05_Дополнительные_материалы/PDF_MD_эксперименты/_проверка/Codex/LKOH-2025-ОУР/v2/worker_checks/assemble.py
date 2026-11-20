import json,re,hashlib,collections
from pathlib import Path
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
c=Path('result/_проверка');out=c.parent;src=json.load(open('source.json'));doc=pymupdf.open(src['source_pdf'])
meta=json.load(open(c/'pages-complete.json'));chunks=[]
for item in meta['pages']:
 n=item['pdf_page'];p=doc[n-1];text=(c/'pages-complete'/f'page_{n:04}.md').read_text()
 links=text[text.index('<details>'):] if '<details>' in text else ''
 if n==29:text=(c/'manual29-full.md').read_text()+'\n\n'+links
 if n==56:text=(c/'manual56.md').read_text().replace('покультуре','по культуре')+'\n\n'+links
 if n==112:text=text[:text.index('<details>')] if '<details>' in text else text;text+='\n\n'+(c/'ocr-112.md').read_text()+'\n\n'+links
 if n==113:text=(c/'ocr-113.md').read_text()+'\n\n'+links
 if n==11:text='# Управление в области устойчивого развития\n\n'+text
 if n==61:text=text.replace('социальноэкономическое','социально-экономическое')
 # Escape literal inequality signs that Markdown would parse as quote markers.
 text=re.sub(r'(?m)^(>+)(?=\s*\d)',lambda m:'&gt;'*len(m[1]),text)
 text=re.sub(r'\n{3,}','\n\n',text).strip()
 # No extraction placeholders belong in the deliverable.
 text=re.sub(r'(?:<mark>)?ZZ(?:</mark>)?\s*TABLE\d+ZZ','',text)
 item['printed_page_labels']=list(dict.fromkeys(w[4] for w in p.get_text('words') if w[1]>800 and re.fullmatch(r'\d{1,3}',w[4])))
 item['conversion_status']='converted';item['review_status']='checked' if n in [1,113] else 'pending'
 item['issues']=[] if n in [1,113] else ['Полная сверка текста, порядка чтения, сносок и всех ячеек по оригиналу не выполнена.']
 item['reviewed_objects']=[]
 if n in [29,56,92]:item['reviewed_objects']=['Выборочная сверка структуры таблиц / инфографики по изображению; страница целиком не подтверждена.']
 if n==112:item['issues'].append('Мелкий регистрационный номер организации-заказчика на скане прочитан неуверенно; помечен в тексте.');item['reviewed_objects']=['Тело сканированного заключения прочитано по изображению; исправлен OCR.']
 if n in [112,113]:item['ocr']='Tesseract rus+eng, локально; исправления по изображениям'
 if item['review_status']=='pending':note='> **Техническая пометка:** рабочая транскрипция; полная сверка этой страницы с оригиналом — pending.\n\n'
 else:note=''
 item['markdown_chars']=len(text);item['output_text_sha256']=hashlib.sha256(text.encode()).hexdigest()
 (c/'pages-complete'/f'page_{n:04}.final.md').write_text(text+'\n')
 chunks.append(f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+note+text+f'\n\n![Исходная физическая страница {n}](assets/page_{n:04}.png)\n')
report='\n\n'.join(chunks)
# Keep the document title as the first visible line while retaining the page boundary.
title='# Отчет об устойчивом развитии Группы «ЛУКОЙЛ»'
report=report.replace(title+'\n\n','',1)
intro=title+'\n\n> **Технические сведения о переносе:** рабочая версия полной постраничной конвертации, 114 физических страниц. Текстовый слой дополнен OCR заключения на страницах 112–113. Изображения служат визуальной опорой. Полная сверка документа не выполнена; состояния каждой страницы перечислены в `_проверка/pages.json`. Сложные таблицы используют HTML.\n\n'
(out/'report.md').write_text(intro+report+'\n')
meta['status']='working_version';meta['review_summary']={'checked_pages':[1,113],'pending_pages':[n for n in range(1,115) if n not in [1,113]],'contact_sheets':'Все 114 страниц просмотрены в миниатюрах для классификации макета; это не построчная сверка.','targeted_review':[29,56,92,112,113]}
meta['method']='Нативный текст PyMuPDF; PyMuPDF4LLM legacy с отключённой layout-моделью для основного извлечения; геометрия ячеек; локальный Tesseract для сканов 112–113.'
(c/'pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
print('Saved',len(report),'characters;',len(meta['pages']),'pages')
