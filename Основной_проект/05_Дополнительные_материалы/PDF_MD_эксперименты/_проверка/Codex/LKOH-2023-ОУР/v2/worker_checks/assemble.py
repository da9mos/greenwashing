import json,re,hashlib,collections,html
from pathlib import Path
import pymupdf
out=Path('result');s=json.load(open('source.json'));d=pymupdf.open(s['source_pdf']);meta=json.load(open(out/'_проверка/pages.json'))
# These spreads contain matrix tables, schemas or dense data: preserve their spatial relationships.
layout_halves={5:[1],6:[1],11:[1],12:[0],15:[0,1],16:[0],17:[1],18:[1],19:[1],20:[1],21:[0],22:[0],23:[1],25:[1],26:[0],27:[1],28:[0],29:[1],30:[0],31:[1],32:[1],33:[1],34:[0,1],37:[1],38:[0],40:[0,1],42:[1],45:[1],46:[1],47:[1],48:[0],49:[1],50:[1],52:[0],54:[1],55:[0],56:[1],57:[0],58:[0,1],59:[1],60:[0,1],61:[1],62:[0],63:[1]}
# Refined per-half output is retained; replace only table-heavy halves by positional transcription.
# Split is reconstructed from independently extracted half-page markdown only where needed.
import pymupdf4llm
pymupdf4llm.use_layout(False)
for n,halves in layout_halves.items():
 p=d[n-1];parts=[]
 for k in [0,1]:
  if k in halves:
   lay=(out/'_проверка/pages'/f'{n:04}-layout{k+1}.txt').read_text().replace('\f','').strip();parts.append('```text\n'+lay+'\n```')
  else:
   temp=pymupdf.open();q=temp.new_page(width=p.rect.width/2,height=p.rect.height);q.show_pdf_page(q.rect,d,n-1,clip=pymupdf.Rect(k*p.rect.width/2,0,(k+1)*p.rect.width/2,p.rect.height))
   parts.append(pymupdf4llm.to_markdown(temp,ignore_graphics=True,ignore_images=True,show_progress=False));temp.close()
 old=(out/'_проверка/pages'/f'{n:04}.md').read_text();link=old.find('<details>')
 text='\n\n'.join(parts)+(('\n\n'+old[link:]) if link>=0 else '')
 (out/'_проверка/pages'/f'{n:04}.md').write_text(text)
 print(n,flush=True)
(out/'_проверка/pages/0001.md').write_text('ЛУКОЙЛ\n\nОтчет об устойчивом развитии Группы «ЛУКОЙЛ»\n\n## Люди − Устойчивость Компании\n\n2023\n')
parts=['# Отчет об устойчивом развитии Группы «ЛУКОЙЛ»\n\n> Техническое примечание: рабочая версия полной постраничной конвертации. Все 115 физических страниц включены. Полная визуальная сверка содержания не выполнена; см. `_проверка/pages.json`. Плотные таблицы и схемы представлены моноширинным текстом с сохранением расположения полей, изображения — отдельной визуальной опорой. OCR заключения аудитора требует вычитки.\n']
for e in meta['pages']:
 n=e['pdf_page'];p=d[n-1];r=json.load(open(out/'_проверка/pages'/f'{n:04}.meta.json'));text=(out/'_проверка/pages'/f'{n:04}.md').read_text()
 labels=[]
 for word in p.get_text('words'):
  if word[1]>p.rect.height-28 and (word[0]<65 or word[0]>p.rect.width-65) and re.fullmatch(r'\d{1,3}',word[4]):labels.append(word[4])
 e['printed_page_labels']=labels or None;e['markdown_chars']=len(text);e['issues']+=r['issues'];e['review_status']='pending';e['conversion_status']='converted'
 e['layout_overview']='viewed_for_structure_only'
 if n==1:
  e['review_status']='checked';e['issues']=[];e['review_scope']='Весь видимый текст обложки и иллюстрация просмотрены по исходному изображению; название, слоган, год и логотип сохранены.'
 if n in [114,115]:e['content_type']='mixed_text_and_scanned_body';e['conversion_method']='text_layer + Tesseract rus+eng for scanned body'
 else:e['conversion_method']='text_layer; two-page spread divided after overview; Markdown and positional text for tables'
 if n in layout_halves or 66<=n<=84 or 87<=n<=113:
  e['issues'].append('Таблицы/схемы сохранены позиционным текстом, без полной ячеечной сверки. Многострочные и объединённые поля требуют проверки по изображению.')
 parts.append(f'\n<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+text+f'\n\n![Исходная физическая страница {n}](assets/page_{n:04}.png)\n')
meta['method']='Local PyMuPDF4LLM legacy without layout model; per-half extraction; Poppler positional transcription for dense tables; local Tesseract rus+eng for scanned audit body'
meta['review_summary']={'checked_pages':[1],'pending_pages':list(range(2,116)),'structure_overview_pages':list(range(1,116)),'note':'Контактные листы использованы только для устройства и разворотов. Они не считаются полной сверкой текста.'}
(out/'report.md').write_text('\n'.join(parts));(out/'_проверка/pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
