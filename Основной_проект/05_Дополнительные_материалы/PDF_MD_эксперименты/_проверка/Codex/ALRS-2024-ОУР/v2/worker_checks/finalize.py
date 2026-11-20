from pathlib import Path
import re,json,hashlib,html
root=Path(__file__).resolve().parents[1]
s=(root/'report.md').read_text()
parts={int(m.group(1)):m.group(0) for m in re.finditer(r'<!-- pdf_page: (\d+) -->.*?(?=<!-- pdf_page:|\Z)',s,re.S)}
changes=[]
def replace_body(n,body):
 old=parts[n]; tail=old[old.index('> Служебная информация: ссылки исходного PDF'):] if '> Служебная информация: ссылки исходного PDF' in old else old[old.index('<details>'):]
 parts[n]=f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+body.strip()+'\n\n'+tail
replace_body(1,'АЛРОСА\n\n# ОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ\n\n2024')
replace_body(4,'''АЛРОСА — ОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ 2024

## О КОМПАНИИ

| Страница | Раздел |
| --- | --- |
| 5 | Кратко об АЛРОСА |
| | География деятельности |
| 7 | Бизнес-модель |
| 9 | Ключевые события 2024 года |
| 10 | Ключевые рейтинги, рэнкинги, индексы и награды в области устойчивого развития |
| 11 | Участие в организациях и ассоциациях |''')
# Preserve source links, navigation, page images. Replace only damaged infographic body.
a=parts[100].index('<p>Подтверждена');b=parts[100].index('> Служебная информация: ссылки')
parts[100]=parts[100][:a]+'''## Подтверждена углеродная нейтральность алмазно-бриллиантового комплекса АЛРОСА за 2023 и 2024 годы

### КАРБОНИЗАЦИЯ

**КИМБЕРЛИТ** — Горная порода, содержащая алмазное сырье.

Поглощенный углерод «запирается» в стабильной форме, предотвращающей его попадание обратно в атмосферу.

Руда в одном 130-тонном самосвале поглощает 6000 кг углекислого газа<sup>1</sup> Примерно столько производит автомобиль на бензине, проехав 26 тыс. километров — ⅔ земного шара по экватору.

**34 млн тонн** АЛМАЗНОЙ РУДЫ АЛРОСА ДОБЫВАЕТ В ГОД

**400 тыс. га леса** — ПРИ ПРОИЗВОДСТВЕ АЛМАЗОВ АЛРОСА ПОГЛОЩАЕТСЯ БОЛЕЕ 1 МЛН ТОНН СО₂ В ГОД — ПОЧТИ СТОЛЬКО ЖЕ ПАРНИКОВЫХ ГАЗОВ ПОГЛОЩАЮТ 400 ТЫС. ГА ЛЕСА

**№1** АЛРОСА СТАЛА ПЕРВОЙ В МИРЕ УГЛЕРОДНО-НЕЙТРАЛЬНОЙ КОМПАНИЕЙ В ГОРНОЙ ДОБЫЧЕ

доказано в результате 3-летних научных исследований

МГУ

CO₂ NEUTRAL

TÜV AUSTRIA — VERIFIED — STANDARDS & COMPLIANCE

подтверждено международным сертификатом

<sup>1</sup> Средний объем поглощения — 46 кг CO₂– экв. / тонна руды.

'''+parts[100][b:]
for n in [152,153]:
 t=parts[n]; pos=t.index('> Служебная информация: ссылки')
 parts[n]=t[:pos]+(root/f'_проверка/transcription_{n}.md').read_text()+'\n\n'+t[pos:]
# Remove page number interrupting the last body column, confirmed against source image.
parts[2]=parts[2].replace('<p>2</p>\n\n','')
# Reconstruct page 154's entire table, preserving source wording from native glyphs.
t=parts[154]; table=re.search(r'<table>.*?</table>',t,re.S).group()
rows=[]
rows.append(['1. Информация об организации и практиках подготовки отчетности','GRI 2: Общие элементы отчетности 2021','2-1. Подробная информация об организации','Кратко об АЛРОСА, стр. 5<br/>Бизнес-модель, стр. 7<br/>Контакты, стр. 189','Существенный регион деятельности — Российская Федерация. Для некоторых показателей дополнительно представлена разбивка по регионам, где расположены ключевые активы (Республика Саха (Якутия), Архангельская область, Смоленская область, Санкт-Петербург).<br/>Форма собственности — смешанная российская собственность с долями федеральной собственности и собственности субъектов Российской Федерации.<br/>Основными акционерами Компании выступают Российская Федерация (33 % акций) и Республика Саха (Якутия) (25 % акций).<br/>Отличительной чертой управления АЛРОСА является участие коренных народов в принятии стратегических решений Компании: на администрации районов (улусов) Республики Саха (Якутия) приходится 8 % акционерного капитала Компании.<br/>Подробнее см. Раскрываемую годовую бухгалтерскую (финансовую) отчетность и Аудиторское заключение независимого аудитора по состоянию на 31 декабря 2024 года'])
rows.append(['','','2-2. Юридические лица, включенные в отчетность организации в области устойчивого развития','–','В документах, подлежащих обязательному раскрытию, доступ к сведениям о юридических лицах, входящих в периметр отчетности, ограничен в соответствии с Постановлением Правительства Российской Федерации от 4 июля 2023 года № 1102 «Об особенностях раскрытия и (или) предоставления информации, подлежащей раскрытию и (или) предоставлению в соответствии с требованиями Федерального закона «Об акционерных обществах» и Федерального закона «О рынке ценных бумаг». При раскрытии информации в настоящем отчете применяется аналогичный подход'])
rows.append(['','','2-3. Отчетный период, частота предоставления отчетности и контактная информация','Об Отчете и существенности, стр. 149<br/>Контакты, стр. 189',''])
rows.append(['','','2-4. Изменения в информации','Об Отчете и существенности, стр. 149',''])
rows.append(['','','2-5. Независимое заверение отчетности','Об Отчете и существенности, стр. 149','Комитет по стратегии и устойчивому развитию рассматривает Отчет об устойчивом развитии в соответствии с положениями Политики в области устойчивого развития. Генеральный директор — Председатель Правления ежегодно утверждает приказ о подготовке Отчета об устойчивом развитии, в котором среди прочего прописаны положения о внешнем заверении Отчета'])
rows.append(['2. Деятельность и сотрудники','GRI 2: Общие элементы отчетности 2021','2-6. Сведения о деятельности, цепочке создания добавленной стоимости и об иных деловых связях организации','Бизнес-модель, стр. 7',''])
new='<table>\n<tr><th></th><th></th><th>ПОКАЗАТЕЛЬ</th><th>РАЗДЕЛ</th><th>КОММЕНТАРИИ</th></tr>\n'
for i,row in enumerate(rows):
 new+='<tr>'
 for j,val in enumerate(row):
  if j<2 and 0<i<5:continue
  span=' rowspan="5"' if i==0 and j<2 else ''
  new+=f'<td{span}>{val}</td>'
 new+='</tr>\n'
new+='</table>'
parts[154]=t.replace(table,new)
# Explicitly flag review debt on each page; converted is distinct from checked.
checked={1,4,100,152,153,154}
p=json.loads((root/'_проверка/pages.json').read_text())
for x in p['pages']:
 n=x['pdf_page']; x['conversion_status']='converted'; x['review_status']='checked' if n in checked else 'pending';x['semantic_source_review_completed']=n in checked
 x['original_diagnostics']=x['issues']; x['issues']=[]
 if n not in checked:
  x['issues'].append('Полная постраничная сверка по оригиналу не выполнена; порядок чтения и связи блоков требуют проверки.')
  if x['tables']:x['issues'].append('Таблица механического кандидата: проверить границы многострочных ячеек, строки, колонки и объединения; обнаружен этот класс дефекта на странице 154.')
  mark='> Служебная пометка: рабочая транскрипция; полная сверка этой страницы по оригиналу не выполнена.'
  if x['tables']:mark+=' Структура таблиц требует проверки: возможны разбиение многострочной ячейки и смещение связи с соседней строкой.'
  pos=parts[n].index('\n\n')+2;parts[n]=parts[n][:pos]+mark+'\n\n'+parts[n][pos:]
 x['verification_scope']='Full page visual source review and targeted corrections' if n in checked else ('Partial column-order review; no full-page acceptance' if n==2 else 'Mechanical conversion; visual semantic review pending')
 if n in [1,4]: x['ocr_verified']=True
 if n==100:x['resolved_unicode']=4;x['unresolved_unicode']=0
 if n in [152,153]:x['raster_body_transcribed']=True;x['raster_review_method']='Local Tesseract rus+eng, followed by visual reading and correction of all source panels'
 x['printed_page_label']=None
 x['printed_page_label_status']='not independently recorded' if n not in {1,4,100,152,153,154} else 'visually confirmed'
 if n in {100,152,153,154}:x['printed_page_label']=str(n)
 x['content_type']='mixed/raster_body' if n in {152,153} else ('cover' if n==1 else ('text_and_tables' if x['tables'] else 'text_and_graphics'))
(root/'_проверка/pages.json').write_text(json.dumps(p,ensure_ascii=False,indent=2))
header='# ОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ 2024\n\n> Служебная информация: рабочая конвертация всех 189 физических страниц. Полностью сверены страницы 1, 4, 100, 152–154. Прочие страницы: converted / pending; таблицы требуют проверки структуры. Изображения оригинала приложены к каждой странице.\n\n'
report=header+''.join(parts[n] for n in range(1,190))
(root/'report.md').write_text(report)
c=json.loads((root/'_проверка/native_coverage.json').read_text());c['baseline_report_sha256']=c.pop('report_sha256');c['report_sha256']=hashlib.sha256(report.encode()).hexdigest();c['review_status']='partial';c['pending_pages']=[n for n in range(1,190) if n not in checked];c['checked_pages']=sorted(checked);c['scope']='Native glyph coverage applies to preserved baseline only; revised report includes visual corrections and raster body transcription. Does not certify unreviewed table structure.'
(root/'_проверка/native_coverage.json').write_text(json.dumps(c,ensure_ascii=False,indent=2))
