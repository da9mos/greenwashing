from pathlib import Path
import re,json,sys,hashlib,collections
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf as fitz
from bs4 import BeautifulSoup
root=Path('result'); old=(root/'_проверка/before/report.md').read_text(); records=json.loads((root/'_проверка/before/pages.json').read_text())['pages']
chunks={int(m[1]):m[2] for m in re.finditer(r'<!-- pdf_page: (\d+) -->(.*?)(?=<!-- pdf_page:|\Z)',old,re.S)}
changes=[]
def note(n,t): changes.append({'pdf_page':n,'change':t,'basis':'Визуальное чтение исходного изображения страницы; текстовый слой PDF.'})
def replacebody(n,body):
 c=chunks[n]; details=c[c.index('<details>'):]; links=''
 if '> Служебная информация: ссылки исходного PDF' in c:
  links=c[c.index('> Служебная информация: ссылки исходного PDF'):c.index('<details>')]
 chunks[n]=f'\n<a id="pdf-page-{n}"></a>\n\n{body}\n\n{links}{details}'
def mdtable(headers,rows):
 return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(row)+' |' for row in rows])
# Verified cover, not the decorative OCR dash.
replacebody(1,'# ОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ 2023\n\nМеталлоинвест\n\n## Новые вызовы — новые перспективы')
note(1,'Восстановлены название, логотипное имя и порядок чтения обложки; удалён ложный OCR-дефис.')
# Reject OCR duplicates and text hallucinated from photographs. Keep photo evidence.
for n in [6,17,24,33,83]:
 chunks[n]=re.sub(r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\..*?(?=<details>)','',chunks[n],flags=re.S)
 note(n,'Удалены ложные OCR-добавки: дубли текста слоя и фрагменты фотографий; фотография сохранена.')
# Section icons: numbers are visible in the original.
for n,labels in {17:['8 — достойная работа и экономический рост','11 — УСТОЙЧИВЫЕ ГОРОДА И НАСЕЛЕННЫЕ ПУНКТЫ','16 — мир, правосудие и эффективные институты'],33:['8 — достойная работа и экономический рост','16 — мир, правосудие и эффективные институты','17 — партнерство в интересах устойчивого развития'],83:['8 — достойная работа и экономический рост']}.items():
 c=chunks[n]; start=c.index('<p>достойная работа</p>'); end=c.index('<p>-36%</p>') if n==83 else c.index('<details>')
 chunks[n]=c[:start]+'\n\nЦУР: '+ '; '.join(labels)+'.\n\n'+c[end:]
 note(n,'Восстановлены номера и связи подписей значков ЦУР.')
# Remove empty markup without touching empty table cells.
for n,c in chunks.items(): chunks[n]=re.sub(r'<p>\s*</p>\s*','',c)
# Source symbol font maps the round bullet to Latin y. Apply only with per-page accounting.
doc=fitz.open(json.load(open('source.json'))['source_pdf'])
for n,c in chunks.items():
 bullets=sum(s['text'].count('y') for b in doc[n-1].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if s['font']=='Wingdings2-SC700')
 found=len(re.findall(r'(?<!\w)y(?!\w)',c))
 if bullets and bullets==found:
  chunks[n]=re.sub(r'(?<!\w)y(?!\w)','•',c)
  changes.append({'pdf_page':n,'change':f'Исправлено {bullets} маркеров Wingdings2-SC700: y → •.','basis':'Тот же шрифт/символ, сверенный визуально на странице 6; совпадение количества на странице.','review_scope':'symbol mapping only'})
# Fix both recruitment tables and separate the adjacent charts.
c=chunks[69]; a=c.index('<p>Количество нанятых</p>'); b=c.index('<p>М Е Т А Л Л О И Н В Е С Т')
headers=['Категория','Белгородская область','Курская область','Всего']
hired=[['Всего, в том числе:','1 978','990','2 968'],['Женщин','596','276','872'],['До 30 лет','332','127','459'],['30–50 лет','217','138','355'],['Старше 50 лет','47','11','58'],['Мужчин','1 382','714','2 096'],['До 30 лет','812','432','1 244'],['30–50 лет','443','231','674'],['Старше 50 лет','127','51','178']]
fired=[['Всего, в том числе:','2 394','1 138','3 532'],['Женщин','740','268','1 008'],['До 30 лет','294','69','363'],['30–50 лет','301','147','448'],['Старше 50 лет','145','52','197'],['Мужчин','1 654','870','2 524'],['До 30 лет','563','268','831'],['30–50 лет','745','424','1 169'],['Старше 50 лет','346','178','524']]
new='Количество нанятых сотрудников в 2021–2023 годах, человек\n\n'+mdtable(['Год','Человек'],[['2021','3 256'],['2022','2 118'],['2023','2 968']])+'\n\nОбщее количество нанятых сотрудников в 2023 году в разбивке по полу, возрасту и региону, человек\n\n'+mdtable(headers,hired)+'\n\nКоличество уволенных сотрудников в 2021–2023 годах, человек\n\n'+mdtable(['Год','Человек'],[['2021','3 576'],['2022','3 310'],['2023','3 532']])+'\n\nОбщее количество уволенных сотрудников в 2023 году в разбивке по полу, возрасту и региону, человек\n\n'+mdtable(headers,fired)+'\n\n'
c=c[:a]+new+c[b:]
# Reorder the two columns on printed page 137, preserving verbatim paragraphs.
a=c.index('<p>195</p>'); b=c.index('<p>СПЕЦИАЛЬНЫЕ ПРОГРАММЫ')
right='''Компания неуклонно придерживается принципов инклюзивности и на протяжении многих лет успешно реализует программу по включению лиц с инвалидностью в трудовой процесс.

В рамках этой программы в Компании разработан список вакансий, которые могут быть предложены кандидатам с инвалидностью. Корпоративная политика предусматривает, что при наличии полного соответствия квалификационным требованиям претенденты с ограниченными возможностями здоровья (ОВЗ) имеют приоритет в трудоустройстве.

В процессе найма лиц с ОВЗ Компания строго следует нормам законодательства Российской Федерации, обеспечивая выполнение государственных нормативов по квотированию рабочих мест и трудоустройству данной категории граждан. Компания гарантирует предоставление всех положенных льгот и гарантий для людей с ОВЗ, которые закреплены в Трудовом кодексе Российской Федерации.

В будущем Компания намерена продолжать политику обеспечения гарантированных экономических, социальных и правовых мер работникам с ограниченными возможностями здоровья.

195 ЧЕЛОВЕК С ОГРАНИЧЕННЫМИ ВОЗМОЖНОСТЯМИ ЗДОРОВЬЯ РАБОТАЕТ В КОМПАНИИ

Сотрудники с ограниченными возможностями здоровья, работающие в Металлоинвесте по состоянию на конец 2023 года, человек

'''+mdtable(['Предприятие','Человек'],[['ЛГОК','60'],['МГОК','86'],['ОЭМК','49'],['Всего','195']])+'\n\n'
chunks[69]=c[:a]+right+c[b:]
note(69,'По всем ячейкам оригинала заново собраны таблицы найма и увольнения; отделены соседние диаграммы; восстановлены категории, годы, подписи и порядок двух колонок печатной страницы 137.')
# Energy: preserve original introductory body and notes, replace malformed tables/charts.
c=chunks[106]; a=c.index('<p>Общее потребление энергии'); intro=c[c.index('<p>ПОКАЗАТЕЛИ'):a]
intro=re.sub(r'</p>\s*<p>',' ',intro).replace('<p>','').replace('</p>','')
body='## ПОКАЗАТЕЛИ ЭНЕРГОПОТРЕБЛЕНИЯ\n\n'+intro.replace('ПОКАЗАТЕЛИ ЭНЕРГОПОТРЕБЛЕНИЯ ','',1)+'\n\n'
body+='Общее потребление энергии, 2021–2023 годы, ТДж\n\n'+mdtable(['Год','ЛГОК','МГОК','ОЭМК','Всего'],[['2023','66 794','15 825','58 483','141 102'],['2022','66 667','15 809','57 972','140 448'],['2021','66 954','19 059','61 142','147 155']])
body+='\n\nПотребление топлива в разбивке по видам топлива, 2021–2023 годы, ТДж<sup>6</sup>\n\n'+mdtable(['Вид топлива','2021','2022','2023'],[['Уголь','–','–','–'],['Мазут','61','50','270'],['Природный газ','107 964','104 209','105 088'],['Дизельное топливо','3 710','3 225','2 941'],['Итого','111 735','107 484','108 299']])
body+='\n\nПродажа тепловой энергии, полученной в результате сжигания топлива и не потраченной на собственные нужды, 2021–2023 годы, ТДж<sup>7</sup>\n\n'+mdtable(['Год','ТДж'],[['2021','237'],['2022','263'],['2023','267']])
body+='''

<sup>6</sup> В потреблении топлива не учитываются данные по потреблению бензина, пропана, отработанных нефтепродуктов и кокса в связи с выявленной несущественностью их потребления.

<sup>7</sup> Металлоинвест не осуществляет продажу электроэнергии. В 2021 и 2022 годах были изменены значения в связи с актуализацией данных продажи тепловой энергии на ЛГОКе.

Структура потребления топлива в разбивке по предприятиям, 2023 год

'''+mdtable(['Предприятие','Доля'],[['ЛГОК','51%'],['МГОК','7%'],['ОЭМК','42%']])
body+='\n\nСтруктура потребления электроэнергии в разбивке по предприятиям, 2023 год\n\n'+mdtable(['Предприятие','Доля'],[['ЛГОК','34%'],['МГОК','26%'],['ОЭМК','40%']])
body+='\n\nПотребление электроэнергии предприятий в 2023 году\n\n'+mdtable(['Вид','Единица измерения','ЛГОК','МГОК','ОЭМК','Итого'],[['Электроэнергия','мВт*ч','3 144 400','2 353 514','3 688 258','9 186 172'],['Электроэнергия','ТДж','11 319,84','8 472,65','13 277,73','33 070,22'],['Доля потребления в Металлоинвесте','%','34','26','40','100']])
body+='\n\n302-3\n\nЭнергоемкость продукции в разбивке по предприятиям, 2023 год, ГДж/тонн жидкой стали\n\n'+mdtable(['Предприятие','ГДж/тонн жидкой стали'],[['ЛГОК','7,6'],['МГОК','2,5'],['ОЭМК','13,4']])
replacebody(106,body)
note(106,'По всем значениям оригинала восстановлены четыре таблицы и данные четырёх диаграмм, годы, категории, единицы и сноски 6–7. Удалены колонтитулы этой страницы после установления их роли.')
# Source visibly gives a URL but the annotation has no destination. No guessed link.
chunks[145]=chunks[145].replace('<details>','> Служебная пометка: у ссылки «www.fsb-tcfd.org/.» нет назначения в аннотации PDF; сохранён видимый адрес, переход не восстановлен.\n\n<details>',1)
# Photograph details not suitable as reliable body OCR.
for n in [17,33]:
 chunks[n]=chunks[n].replace('<details>','> Служебная пометка: основной заголовок, навигация и значки ЦУР прочитаны. Мелкий и частично закрытый текст внутри фотографии не транскрибирован полностью; см. оригинал ниже.\n\n<details>',1)
# Blank back cover.
replacebody(158,'<!-- Задняя обложка: однотонное изображение, видимого текста нет. -->')
note(158,'По исходному изображению подтверждена задняя обложка без видимого текста.')
# Native paragraph/table order remains unreviewed elsewhere: explicit page-level state.
checked={1,6,7,24,69,83,106,158}
for r in records:
 n=r['pdf_page']; r['conversion_status']='converted'; r['review_status']='checked' if n in checked else 'pending'; r['semantic_source_review_completed']=n in checked
 r['original_issues']=r['issues']; r['issues']=[] if n in checked else ['Полная построчная сверка текста, порядка чтения и связей по оригиналу не выполнена.']
 r['verification_scope']='Визуальное чтение всей основной области и сверка переноса; фотографии сохранены.' if n in checked else 'Механический перенос текстового слоя; исходное изображение сохранено.'
 r['printed_page_labels']=None
 if n in [6,24,69,106,145]: r['printed_page_labels']={6:['10','11'],24:['46','47'],69:['136','137'],106:['210','211'],145:['288','289']}[n]
 if n in [1,7,17,33,83,158]: r['printed_page_labels']=[]
 r['content_type']='native_text_with_graphics' if r['native_nonspace_glyphs'] else 'image_only'
 if n in [17,33]: r['issues'].append('Мелкий/закрытый текст внутри фотографии не полностью прочитан; декоративная фотография сохранена, основной текст извлечён.')
 if n==145:r['issues'].append('Аннотация ссылки www.fsb-tcfd.org/. не содержит назначения; адрес не угадан.')
 r['reviewed_objects']=[x for x in changes if x['pdf_page']==n]
 if n not in checked and r['tables']:
  r['issues'].append('Таблицы требуют сверки строк и столбцов: возможны слитые строки, пустые детекторные колонки и смешение с диаграммами.')
 if n in checked:r['ambiguous_cell_assignments_resolved']=bool(r.get('ambiguous_cell_assignments'))
 # Underlying glyph inventory is historical; do not claim it validates revised serialization.
 r['native_inventory_scope']='Исходный механический кандидат, сохранённый в before/report.md; ручные исправления учтены отдельно.'
# Pending notices in body, separate from author text.
for r in records:
 n=r['pdf_page']
 if r['review_status']=='pending':
  pos=chunks[n].index('\n',chunks[n].index('</a>'))
  chunks[n]=chunks[n][:pos]+'\n\n> Служебная пометка: converted / pending — полная сверка этой страницы по оригиналу не завершена.\n'+chunks[n][pos:]
parts=[f'<!-- pdf_page: {n} -->'+chunks[n].rstrip() for n in range(1,159)]
report='\n\n'.join(parts)+'\n'
# Title is required at the start; page marker remains the first physical-page boundary.
report=report.replace('# ОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ 2023','# ОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ 2023\n\n> Служебная информация: рабочая версия полного переноса 158 физических страниц. Полная сверка всего документа по оригиналу не выполнена; статусы приведены в _проверка/pages.json.',1)
(root/'report.md').write_text(report)
(root/'_проверка/pages.json').write_text(json.dumps({'pages':records},ensure_ascii=False,indent=2)+'\n')
(root/'_проверка/corrections.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
(root/'_проверка/revision_coverage.json').write_text(json.dumps({'source_sha256':hashlib.sha256(Path(json.load(open('source.json'))['source_pdf']).read_bytes()).hexdigest(),'physical_pages':len(doc),'report_sha256':hashlib.sha256(report.encode()).hexdigest(),'checked_pages':sorted(checked),'review_pending_pages':[n for n in range(1,159) if n not in checked],'scope':'Native coverage belongs to initial candidate; revised document includes source-based corrections, not a claim of full fidelity.'},ensure_ascii=False,indent=2)+'\n')
print('Saved',len(report),'characters;',len(changes),'corrections')
