import re,json,sys,hashlib,collections,shutil
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs');sys.path.insert(0,'/private/tmp/sber-diff-libs')
import pymupdf
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
r=Path('result');a=r/'_проверка';s=(r/'report.md').read_text();source=json.load(open('source.json'));pdf=pymupdf.open(source['source_pdf'])
if not (a/'pages.native.json').exists():shutil.copy2(a/'pages.json',a/'pages.native.json')
reg=json.loads((a/'pages.native.json').read_text());old=reg['pages'];chunks=re.split(r'<!-- pdf_page: \d+ -->',s);intro=chunks[0];parts=chunks[1:]
titles={2:['Содержание'],3:['Обращение Председателя Совета директоров'],4:['Обращение Генерального директора'],5:['О Компании'],6:['Ключевые результаты 2023 года'],7:['География бизнеса'],8:['Основная продукция'],9:['Ключевые тренды в области устойчивого развития'],10:['ESG-стратегия 2027 и вклад в достижение ЦУР ООН'],13:['Управление устойчивым развитием','Взаимодействие с заинтересованными сторонами'],14:['Экологический аспект','Изменение климата'],18:['Охрана водных ресурсов'],19:['Обращение с отходами'],20:['Охрана атмосферного воздуха'],21:['Сохранение биоразнообразия','Устойчивое сельское хозяйство'],22:['Социальный аспект','Охрана труда и промышленная безопасность'],28:['Сотрудники'],33:['Права человека'],34:['Развитие местных сообществ'],39:['Корпоративное управление'],43:['Управление рисками и внутренний контроль'],44:['Кибербезопасность'],45:['Деловая этика и противодействие коррупции'],47:['Цепочка поставок'],49:['Приложение 1. Об Отчете'],51:['Приложение 2. Таблица GRI'],54:['Приложение 3. Таблица SASB','Контактная информация']}
normal=lambda t:' '.join(t.replace('\xa0',' ').split())
charts={7,8,15,18,19,20,24,25,29,30,31,32,35,41,42,43,48,50}
for n,p in enumerate(parts,1):
 def heading(m):
  t=normal(BeautifulSoup(m.group(1),'html.parser').get_text(' '))
  return '<h2>'+m.group(1)+'</h2>' if t in titles.get(n,[]) else m.group()
 p=re.sub(r'<p>(.*?)</p>',heading,p,flags=re.S)
 p=p.replace('<table>','<div style="overflow-x:auto; max-width:100%">\n<table>').replace('</table>','</table>\n</div>')
 if n>1:
  note='> Служебная пометка о сверке: текст страницы конвертирован; полная построчная сверка с оригиналом не завершена.'
  if n in charts:note+=' Связи отдельных значений диаграмм с рядами, категориями и периодами требуют дополнительной сверки; исходная графика сохранена в изображении страницы ниже.'
  p=p.replace('<details>',note+'\n\n<details>',1)
 parts[n-1]=p
s=intro+''.join(f'<!-- pdf_page: {n} -->'+p for n,p in enumerate(parts,1));(r/'report.md').write_text(s)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert len(pdf)==54 and sha(source['source_pdf'])==json.loads((a/'native_coverage.json').read_text())['source_sha256']
checked_objects={16:['Таблица мероприятий по энергосбережению: все строки, подписи предприятий, объединения'],41:['Матрица компетенций: 9 членов × 10 областей и два оттенка легенды'],49:['Таблица границ существенных тем: все 9 строк × 4 компании, пустоты, сноска 4'],50:['Продолжение таблицы границ существенных тем: все 12 строк × 4 компании']}
for n,x in enumerate(old,1):
 x['conversion_status']='converted';x['review_status']='checked' if n==1 else 'pending';x['semantic_source_review_completed']=n==1
 x['verification_scope']='Вся обложка визуально сверена' if n==1 else 'Просмотр макета исходной страницы; выборочная сверка отмеченных объектов, без полной построчной проверки'
 x['source_layout_viewed']=True;x['source_text_fully_reviewed']=n==1
 x['native_accounting_scope']='Поля native_* и rendered_native_character_inventory_matches относятся к исходному механическому кандидату report.native.md, до ручных исправлений.'
 x['printed_labels']=list(dict.fromkeys(b[4].strip() for b in pdf[n-1].get_text('blocks') if b[1]>795 and b[2]-b[0]<100 and b[4].strip().isdigit()))
 x['content_type']='native_text_with_tables_and_graphics' if x['tables'] or n==41 else 'native_text_with_graphics'
 x['resolved_diagnostics']=x['issues'];x['issues']=[] if n==1 else ['Полная построчная сверка текста, порядка чтения, сносок и всех таблиц по оригиналу не завершена.']
 if n in charts:x['issues'].append('Не все извлечённые значения диаграмм проверены на связь с рядами, категориями и периодами; исходная графика сохранена.')
 if n in checked_objects:x['checked_objects']=checked_objects[n]
 if n==1:x['ocr_verified']=True;x['ocr_correction']='Ошибочная OCR-буква Я удалена по изображению логотипа; сохранено АКРОН.'
 x['unresolved_unicode_final']=0
reg['document_status']='working_version';reg['report_sha256']=sha(r/'report.md');reg['pages_total']=54;reg['full_source_review_completed']=False
(a/'pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n')
cov=json.loads((a/'native_coverage.json').read_text());cov['applies_to']='_проверка/report.native.md';cov['final_report_sha256']=sha(r/'report.md');cov['final_report_has_documented_manual_edits']=True;cov['warning']='Native accounting is baseline evidence only; it does not assert final ordering, table relations or full source review.';(a/'native_coverage.json').write_text(json.dumps(cov,ensure_ascii=False,indent=2)+'\n')
soup=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).render(s),'html.parser');ids=[x['id'] for x in soup.find_all(id=True)];missing=[];internal=[]
for im in soup.find_all('img'):
 if not (r/im['src']).is_file():missing.append(im['src'])
for link in soup.find_all('a',href=True):
 if link['href'].startswith('#') and link['href'][1:] not in ids:internal.append(link['href'])
markers=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',s)));assert markers==list(range(1,55));assert not missing and not internal
# Check effective table widths, respecting merged cells.
errors=[]
for ti,t in enumerate(soup.find_all('table')):
 active={};widths=[]
 for ri,row in enumerate(t.find_all('tr')):
  occupied={c for c,end in active.items() if end>ri};c=0
  for cell in row.find_all(['td','th'],recursive=False):
   while c in occupied:c+=1
   cs=int(cell.get('colspan',1));rs=int(cell.get('rowspan',1))
   for col in range(c,c+cs):occupied.add(col);active[col]=ri+rs
   c+=cs
  widths.append(max(occupied)+1 if occupied else 0)
 if len(set(widths))>1:errors.append({'table':ti,'widths':widths})
assert not errors,errors
result={'source_sha256':sha(source['source_pdf']),'report_sha256':sha(r/'report.md'),'physical_pages':54,'page_markers_in_order':True,'images':len(soup.find_all('img')),'tables':len(soup.find_all('table')),'missing_local_images':missing,'broken_internal_anchors':internal,'table_grid_width_errors':errors,'source_review':'Cover fully reviewed; selected tables and Unicode diagnostics reviewed; all other full-page reviews pending','external_links':'Preserved from PDF annotations; not opened or tested','browser_render':'blocked: Chrome SIGABRT','native_accounting':'baseline only'}
(a/'final_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
(a/'review.md').write_text('''# Протокол конвертации и ограничения

Источник: AKRN-2023-ОУР.pdf, 54 физические страницы. SHA-256: '''+result['source_sha256']+'''.

Использован уже подготовленный механический кандидат native_candidate.py. Его версия сохранена в report.native.md, начальный реестр — pages.native.json. Ответы других моделей, старые транскрипции, внешние API и загрузки не использовались.

Все 54 страницы представлены текстом; на каждой странице сохранено исходное полностраничное изображение как визуальная опора. Основной документ содержит 54 последовательных маркера страниц. Текстовый слой имеется на всех страницах; на обложке проверен дополнительный OCR логотипа.

Просмотрены макеты всех страниц на контактных листах. Это проверка устройства страниц, а не чтение всего мелкого текста. Весь текст обложки прочитан по оригиналу. Отдельно просмотрены диагностические страницы 6, 10, 22, 25, 47, 49, 50. Сверены исправляемые таблицы на страницах 16, 41, 49 и 50, включая пустоты и объединения. Исходные таблицы на остальных контактных листах просмотрены по структуре, но их ячейки полностью не сверены.

В corrections.json описаны исправления. Восстановлены потерянные подписи объединённых строк таблицы энергосбережения, последний столбец таблицы границ тем, цветовая матрица компетенций. Исправлены ошибочная OCR-буква логотипа и символы шрифта. Порядок исходных текстовых объектов переставлен по областям макета; строки одного исходного абзаца объединены с сохранением переносов. Полная сверка последовательности всех абзацев после перестановки не выполнена, поэтому страницы 2–54 остаются converted/pending.

В диаграммах сохранены извлечённые подписи и числа, но не все их связи с рядами и периодами сверены. Часть переносов слов оставлена как в источнике, без догадок о написании. Навигационные повторы сохранены. Проверка суммарного набора символов исходного кандидата не считается доказательством правильного порядка или связей. Печатные номера извлечены из нижних колонтитулов, без расчёта постоянного смещения.

Команда render_bundle.py создала HTML, но Chrome headless завершился SIGABRT. Браузерные снимки 1440/390 не получены. Вместо них созданы и просмотрены отдельные локальные превью MuPDF: обложка и таблицы 16, 41, 49, 50; для обложки и таблицы 49 — также ширина 390. На узком превью MuPDF широкая таблица обрезается, этот движок не проверяет браузерную прокрутку. В HTML и Markdown добавлены контейнеры overflow-x:auto; их фактическая работа в Chrome не проверена. Эти превью не подтверждают отображение всего документа и не заменяют сверку PDF.

final_checks.json содержит проверки маркеров, существования всех изображений, внутренних якорей и согласованности ширины HTML-таблиц. Внешние адреса перенесены из PDF и не открывались. Статусы каждой страницы и оставшиеся вопросы — pages.json.
''')
(a/'error_rules.md').write_text('''# Повторяемые классы дефектов

1. Специальный шрифт: private-use и управляющие коды могут скрывать видимый знак или не отображаться. Признак — Unicode Co/Cc или пустой знак в рендере. Действие — чтение исходного изображения, точечная замена с журналом. Приёмка — совпадение знака и его позиции по оригиналу. Контроль: неверная буква вместо логотипа отклоняется; визуально подтверждённый текст принимается; неясный знак остаётся pending.

2. Неполная сетка: детектор таблиц может вынести крайние ячейки и объединённые подписи в отдельные текстовые объекты. Признак — разная эффективная ширина строк, отдельные галочки и названия рядом с таблицей. Действие — проверить все строки и восстановить ячейки по оригиналу, включая пустые. Приёмка — совпадение компаний/категорий и всех значений, а не только набора символов. Контроль: сдвинутая галочка отклоняется; подтверждённая пустая ячейка принимается; неясное объединение остаётся pending.

3. Цветовая таблица: информация может передаваться заливкой без текстового знака. Признак — сетка с пустыми извлечёнными ячейками и цветовой легендой. Действие — прочитать каждую заливку по изображению, перевести в явные коды с легендой. Приёмка — проверены все ячейки и соответствие оттенков легенде. Контроль: исчезнувшие цвета отклоняются; проверенные коды принимаются; неразличимые оттенки отмечаются pending.

4. Колонки: сохранение каждого глифа не устанавливает порядок чтения. Признак — чередование продолжений разных абзацев или подписи, отделённые от числа. Действие — установить области по макету и переставлять исходные объекты без переписывания чисел, затем сверить абзацы. Приёмка — прочитаны все затронутые связи. Контроль: чередующиеся колонки отклоняются; последовательность по оригиналу принимается; один лишь просмотр макета оставляет review_status=pending.
''')
print(json.dumps(result,ensure_ascii=False,indent=2))
