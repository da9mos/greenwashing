from pathlib import Path
import datetime,hashlib,json,re
import pymupdf

ROOT=Path(__file__).resolve().parent.parent
OUT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
ACTOR='Codex /root/corpus_audit'
sha=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
folders=['GAZP-2023-ОУР_57','GAZP-2023-ЭО_76','TRMK-2023-ИО_4']
identity=[]
for folder in folders:
 directory=ROOT/folder;result=json.loads((directory/'result.json').read_text());raw=json.loads((directory/'raw.json').read_text())
 answer=json.loads(raw['choices'][0]['message']['content']);assert answer==result['answer']
 assert raw['choices'][0]['finish_reason']=='stop'
 assert sha(directory/'page.md')==result['report_sha256']
 assert sha(ROOT/'frozen_instruction.md')==result['instruction_sha256']
 source=BASE/'_источники'/(result['report_id']+'.pdf');stat=source.stat();assert stat.st_blocks and not(stat.st_flags&0x40000000)
 assert sha(source)==result['source_sha256']
 with pymupdf.open(source) as document:
  page=document[result['pdf_page']-1];scale=min(2,2600/max(page.rect.width,page.rect.height));pixels=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False);saved=pymupdf.Pixmap(str(directory/'source.png'))
  assert pixels.digest==saved.digest
  identity.append({'page_folder':folder,'report_id':result['report_id'],'pdf_page':result['pdf_page'],'source_pdf':str(source),'source_pdf_sha256':sha(source),'source_png_sha256':sha(directory/'source.png'),'source_pixels_match_original_pdf':True,'source_render_scale':scale,'source_rect':list(page.rect),'saved_markdown_sha256':sha(directory/'page.md'),'raw_sha256':sha(directory/'raw.json'),'result_sha256':sha(directory/'result.json'),'input_sha256':sha(directory/'input.json'),'request_sha256':sha(directory/'request.json'),'frozen_instruction_sha256':sha(ROOT/'frozen_instruction.md'),'raw_answer_matches_result':True,'finish_reason':'stop'})
(OUT/'identity.json').write_text(json.dumps(identity,ensure_ascii=False,indent=2)+'\n')

header='''Б1
НОВЫЕ ВЫЗОВЫ
НОВЫЕ РЕШЕНИЯ

ООО «ЦАТР – аудиторские услуги»
Россия, 115035, Москва
Садовническая наб., 75
Тел.: +7 495 705 9700
+7 495 755 9700
Факс: +7 495 755 9701
ОГРН: 1027739707203
ИНН: 7709383532
ОКПО: 59002827
КПП: 770501001

TSATR – Audit Services LLC
Sadovnicheskaya Nab., 75
Moscow, 115035, Russia
Tel: +7 495 705 9700
+7 495 755 9700
Fax: +7 495 755 9701
www.b1.ru'''
nav_old='''ПОРТРЕТ
КОМПАНИИ1

ПОРТРЕТ
КОМПАНИИ
2

ОТЧЕТ О КОРПОРАТИВНОМ
УПРАВЛЕНИИ
3

ИНФОРМАЦИЯ
ДЛЯ АКЦИОНЕРОВ'''
nav_new='''1. ПОРТРЕТ КОМПАНИИ
2. ОТЧЕТ О КОРПОРАТИВНОМ УПРАВЛЕНИИ
3. ИНФОРМАЦИЯ ДЛЯ АКЦИОНЕРОВ'''
assert nav_old in (ROOT/'TRMK-2023-ИО_4/page.md').read_text()
patches=[
 {'id':'EO76-HEADER','page_folder':'GAZP-2023-ЭО_76','severity':'major','type':'omitted_text_region','source_bbox':[60,175,440,275],'source_crop':'GAZP-2023-ЭО_76/auditor_header.png','source_observation':'Полностью видимый блок автора заключения, русский и английский адреса, контакты и регистрационные идентификаторы отсутствуют в Markdown.','operation':'insert_after_exact','old':'Приложение','new':'Приложение\n\n'+header,'expected_occurrences':1},
 {'id':'EO76-PRINTED-PAGE','page_folder':'GAZP-2023-ЭО_76','severity':'minor','type':'omitted_printed_page_label','source_bbox':[250,800,310,830],'source_crop':'GAZP-2023-ЭО_76/printed_page.png','source_observation':'Печатное обозначение 74 видно внизу. Физическая страница 76.','operation':'insert_before_exact','old':'![Исходная страница](source.png)','new':'74\n\n![Исходная страница](source.png)','expected_occurrences':1},
 {'id':'TRMK4-NAVIGATION','page_folder':'TRMK-2023-ИО_4','severity':'moderate','type':'wrong_label_number_association','source_bbox':[890,20,1580,125],'source_crop':'TRMK-2023-ИО_4/navigation.png','source_observation':'В источнике 1 относится к «ПОРТРЕТ КОМПАНИИ», 2 к «ОТЧЕТ О КОРПОРАТИВНОМ УПРАВЛЕНИИ», 3 к «ИНФОРМАЦИЯ ДЛЯ АКЦИОНЕРОВ». В Markdown портрет продублирован и связан с цифрой2.','operation':'replace_exact','old':nav_old,'new':nav_new,'expected_occurrences':1}]
for patch in patches:
 source_md=ROOT/patch['page_folder']/'page.md';text=source_md.read_text();assert text.count(patch['old'])==patch['expected_occurrences'];patch['original_markdown_sha256']=sha(source_md);patch['old_quote_sha256']=hashlib.sha256(patch['old'].encode()).hexdigest();patch['proposed_new_quote_sha256']=hashlib.sha256(patch['new'].encode()).hexdigest();patch['source_crop_sha256']=sha(OUT/patch['source_crop']);patch['applied']=False
(OUT/'patch_proposals.json').write_text(json.dumps(patches,ensure_ascii=False,indent=2)+'\n')

quotes={
 'GAZP-2023-ОУР_57':[
  '| Коэффициент частоты травматизма¹ | 0,13 | 0,12 | 0,173² |',
  '| Коэффициент тяжести травматизма³ | 68,19 | 67,87 | 76,6² |',
  '| Компании газового бизнеса | 0,99 | 1,18 | 1,963 |',
  '| Компании нефтяного бизнеса | 3,80 | 0¹¹ | 0¹¹ |',
  '| Компании электроэнергетического бизнеса | 0 | 1,23¹² | 0¹² |'],
 'GAZP-2023-ЭО_76':['Приложение','| Транспортировка | 782,02 тыс. т. CH₄ |','| Подземное хранение газа | 0,03 млн т. CO₂-экв |'],
 'TRMK-2023-ИО_4':[nav_old,'**Компания была создана в 2001 году и на конец 2023 года объединяла ряд производственных активов общей мощностью 6,6 млн тонн трубной продукции в год.**']}
def polish(text):
 text=re.sub(r'(?<=[А-Яа-яЁё])(?=\d)', ' ', text)
 text=re.sub(r'(?<=\d)(?=[А-Яа-яЁё])', ' ', text)
 text=re.sub(r'(?<=[А-Яа-яЁё])(?=«)', ' ', text)
 return text.replace('млнт.', 'млн т.').replace('млнтонн', 'млн тонн').replace('тыс.т.', 'тыс. т.').replace('иwww.', 'и www.').replace('тикерTRMK', 'тикер TRMK').replace('вгод', 'в год').replace('тыс. т.CH₄,0,34', 'тыс. т. CH₄, 0,34').replace('млн т.CO₂', 'млн т. CO₂').replace('0¹¹,1,23¹²,0¹²', '0¹¹, 1,23¹², 0¹²').replace('»,2 к', '», 2 к').replace('»,3 к', '», 3 к')

components={
 'GAZP-2023-ОУР_57':{
  'text':('checked','Прочитаны все заголовки, строки, все поясняющие текстовые блоки и тексты сносок1–13. Подтверждённая повторяющаяся боковая навигация исключена согласно разделу3 frozen-инструкции.'),
  'numbers':('checked','Все75 числовых и прочерковых ячеек четырёх таблиц сверены с увеличениями. 1,963 сохранено целиком. 0,173² и76,6² содержат исходные значения и отдельную сноску2. Периоды2021–2023 и пояснения44,2%,12,9%,66,4% сохранены.'),
  'tables':('checked','Сверены четыре таблицы, строки каждой компании, все три года, единица «чел.» второй таблицы, определения LTIFR и FAR в сносках, прочерки и нули.'),
  'footnotes':('checked','Сноски1–13 сопоставлены с надстрочными знаками. ×1 000 для частоты травматизма, ×1 000 000 для LTIFR и ×100 000 000 для FAR переданы. Значения0¹¹ и1,23¹² не склеены со сносками.'),
  'graphics':('checked','Содержательные цветные индикаторы29.1 и29.2 переданы текстом, весь исходный растр сохранён. Самостоятельных диаграмм с данными на странице нет.'),
  'reading_order':('checked','Текст каждой половины разворота читается сверху вниз, абзацы под таблицами восстановлены из колонок. Содержание таблиц не перемешано.'),
  'links':('checked','В PDF четыре аннотации повторяющейся навигации. Содержательных внешних адресов на странице нет. Локальная ссылкаsource.png существует и соответствует исходной странице.'),
  'display':('checked','Проверены отдельные снимки всех четырёх HTML-таблиц, полный рендер и ширины1440/390. Сноски и последние цифры чисел различимы, общего переполнения нет.')},
 'GAZP-2023-ЭО_76':{
  'text':('pending','Тело заключения прочитано полностью, последний абзац сохранён. Верхний текстовый блок аудитора и печатный номер74 отсутствуют.'),
  'numbers':('pending','Все14 значений трёх таблиц, категории, единицы, области Охвата1/2 и ссылки на страницы50/52/51 совпали. Регистрационные номера и контактные числа верхнего блока опущены.'),
  'tables':('checked','Все14 строк трёх таблиц сопоставлены по категориям и единицам млн т.CO₂-экв /тыс.т.CH₄. Числа0,34 /1,9 /0,03 и71,58 /782,02 /7,28 /16,93 /22,62 совпали.'),
  'footnotes':('not_applicable','На этой физической странице нет надстрочных сносок, требующих привязки к значениям.'),
  'graphics':('checked','Полный исходный растр с логотипом и сканом сохранён и доступен через source.png.'),
  'reading_order':('pending','Порядок тела заключения сохранён. Верхний блок автора и нижний печатный номер не вошли в последовательность текста.'),
  'links':('pending','В PDF нет аннотаций. Видимый адресwww.b1.ru отсутствует в Markdown вместе с остальными реквизитами.'),
  'display':('checked','Три таблицы и основной текст отображаются при1440/390. Исходное изображение читается. Пустые неназванные шапки добавлены Markdown-синтаксисом и видны как тонкие пустые строки, исходные категории не заменены.')},
 'TRMK-2023-ИО_4':{
  'text':('pending','Основной абзац, выделенные блоки, тикерTRMK и подпись на фотографии прочитаны по оригиналу и совпали. Навигационный заголовок «ПОРТРЕТ КОМПАНИИ» продублирован, цифры связаны с чужими пунктами.'),
  'numbers':('pending','Год2001, период2023 и6,6 млн тонн трубной продукции в год визуально совпали. Номера разделов1/2/3 в навигации получили неверные связи.'),
  'tables':('not_applicable','Источник содержит текстовые информационные блоки и фотографию, табличных данных на странице нет.'),
  'footnotes':('not_applicable','На этой странице нет содержательных надстрочных сносок. Номера1/2/3 относятся к навигации.'),
  'graphics':('checked','Фотография, пиктограммы и логотип доступны в полном исходном растре. Текст о производственных и сервисных возможностях перенесён из оранжевого блока.'),
  'reading_order':('pending','Порядок основного текста и подписи сохранён. Навигационный блок ошибочен, а объяснение модели о наложении цифр не подтверждается изображением.'),
  'links':('checked','PDF не содержит аннотаций ссылок. Единственная локальная ссылкаsource.png разрешается в правильное изображение.'),
  'display':('checked','Полный Markdown отрендерен, первая область навигации просмотрена. Ошибочное соответствие пунктов видно и в отображении. При1440/390 общего переполнения нет.')}}
verdicts=[]
for meta in identity:
 folder=meta['page_folder'];page_md=ROOT/folder/'page.md';text=page_md.read_text();evidence=[]
 for quote in quotes[folder]:
  assert quote in text
  evidence.append({'quote':quote,'quote_sha256':hashlib.sha256(quote.encode()).hexdigest(),'saved_markdown_sha256':meta['saved_markdown_sha256']})
 (OUT/folder/'exact_quotes.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
 page_issues=[patch['id'] for patch in patches if patch['page_folder']==folder]
 record={'schema_version':1,'reviewer':ACTOR,'reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'report_id':meta['report_id'],'pdf_page':meta['pdf_page'],'source_sha256':meta['source_pdf_sha256'],'output_sha256':meta['saved_markdown_sha256'],'whole_report_checked':False,'page_scope_status':'accepted' if not page_issues else 'needs_rework','checked':not page_issues,'checked_scope':'Вся содержательная область указанной физической страницы, с явным учётом разрешённого исключения повторяющейся навигации. Остальные физические страницы исходного PDF не входят в этот пилот.','open_defects':page_issues,'components':{name:{'status':status,'finding':polish(description)} for name,(status,description) in components[folder].items()},'source_identity':meta,'evidence':{'source_crops_manifest':'../source_crops.json','exact_quotes':'exact_quotes.json','render_check':'render/render_check.json','full_render':'render/full_page_1440.png','source_png':'../../'+folder+'/source.png'}}
 if folder=='GAZP-2023-ОУР_57':
  record['deepseek_issue_resolution']='Пять исходных issues описывают уже прочитанные сноски и номера, самостоятельных нерешённых расхождений не содержат. Независимая проверка подтверждает приведённые значения. Raw сохранён.'
 elif folder=='GAZP-2023-ЭО_76':
  record['deepseek_issue_resolution']='Raw issues пуст, несмотря на пропуск верхнего блока аудитора и печатного номера. Приёмка всей страницы отклонена.'
 else:
  record['deepseek_issue_resolution']='Заявление DeepSeek о совмещении/наложении цифр не подтверждено источником. Основной текст с повреждённым шрифтом восстановлен правильно, навигация требует правки.'
 (OUT/folder/'comparison.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');verdicts.append(record)
summary={'reviewed_pages':3,'accepted_page_scopes':1,'needs_rework_page_scopes':2,'whole_reports_checked':0,'pages':[{'report_id':r['report_id'],'pdf_page':r['pdf_page'],'page_scope_status':r['page_scope_status'],'output_sha256':r['output_sha256'],'open_defects':r['open_defects']} for r in verdicts]}
(OUT/'review_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
report='''# Независимая проверка трёх страниц пилота DeepSeek v4

Проверены сохранённые ответы DeepSeek, исходные PDF и реальные изображения трёх страниц. Для каждой страницы подтверждены SHA PDF, Markdown, raw, frozen-инструкции и пиксельное соответствие source.png исходному PDF. Точные цитаты, увеличения и рендеры сохранены рядом.

| Страница | Итог заявленного объёма | Основной результат |
|---|---|---|
| Газпром2023, социальный отчёт, физическая57 | Принята содержательная область страницы | Все75 числовых и прочерковых ячеек четырёх таблиц и сноски1–13 совпали |
| Газпром2023, экологический отчёт, физическая76 | Требует правки | Тело скана и14 показателей совпали, блок автора заключения и печатный номер74 опущены |
| ТМК2023, физическая4 | Требует правки | Основной текст и6,6 млн тонн восстановлены, навигационные номера связаны неверно |

## Социальный отчёт Газпрома, физическая57

Сверены все строки четырёх таблиц, периоды2021–2023, единица«чел.», определения LTIFR/FAR и13 сносок. Значение1,963 сохранено полностью. Значения0,173² и76,6² сохраняют исходные числа и отдельную сноску2. Нули0¹¹,1,23¹²,0¹² и прочерки со сноской9 также совпали. Перечитаны поясняющие абзацы и все тексты примечаний. Боковая полоса1–6 является повторяющейся навигацией, её исключение допускает frozen-инструкция после определения роли.

Все четыре таблицы просмотрены в рендере. При ширине1440 и390 общего переполнения нет. Заявленный объём одной физической страницы принят. Остальные135 страниц исходного PDF здесь не проверялись. Пять строк raw issues содержат пояснения к корректно прочитанным объектам, их независимая проверка закрыта этим протоколом.

## Экологический отчёт Газпрома, физическая76

Перечитаны заголовок заключения, обращение к совету директоров, вводный и заключительный абзацы. Все14 строк трёх таблиц совпали с оригиналом, в том числе782,02 тыс.т.CH₄,0,34 и0,03 млнт.CO₂-экв. Категории, единицы и ссылки на печатные страницы50/52/51 сохранились.

Верхний блок аудитора отсутствует целиком. На источнике видны ООО«ЦАТР–аудиторские услуги», русская и английская части адреса, телефоны, факс, ОГРН1027739707203, ИНН7709383532, ОКПО59002827, КПП770501001 иwww.b1.ru. Печатное обозначение74 также не перенесено. В исходном ответе issues пуст. Для приёмки всей страницы нужны подтверждённые вставки обоих пропущенных блоков и повторная проверка сохранённого Markdown. [Предложения правок](patch_proposals.json).

## ТМК, физическая4

По исходному изображению перечитан весь текст с повреждённым шрифтом. Основной абзац, год создания2001, период2023, мощность6,6 млнтонн вгод, блоки устойчивого развития и сбытовой сети, тикерTRMK и текст поверх фотографии совпали.

Навигация содержит реальную ошибку. На источнике1 относится к«ПОРТРЕТ КОМПАНИИ»,2 к«ОТЧЕТ О КОРПОРАТИВНОМ УПРАВЛЕНИИ»,3 к«ИНФОРМАЦИЯ ДЛЯ АКЦИОНЕРОВ». В Markdown первый пункт продублирован, цифры2 и3 оказались рядом с предыдущими названиями. В рендере это видно как«ПОРТРЕТ КОМПАНИИ2» и«ОТЧЕТ О КОРПОРАТИВНОМ УПРАВЛЕНИИ3». Описание DeepSeek о наложении цифр опровергается увеличением оригинала. После адресной замены навигационного блока требуется повторная проверка.

## Доказательства

[Идентичность файлов](identity.json) · [Увеличения исходника с координатами и SHA](source_crops.json) · [Точные предложения правок](patch_proposals.json) · [Сводные вердикты](review_summary.json)

Результаты сравнения и точные цитаты находятся в comparison.json и exact_quotes.json каждой из трёх папок. Полные рендеры и снимки отдельных таблиц сохранены в render/. Правки в page.md, raw, исходные PDF и frozen-инструкцию не вносились.
'''
# Spaces around numeric tokens are retained in the actual comparison JSON. Polish
# this human summary without touching quoted source text or source artifacts.
for old,new in [('Газпром2023','Газпром 2023'),('ТМК2023','ТМК 2023'),('физическая57','физическая 57'),('физическая76','физическая 76'),('физическая4','физическая 4'),('все75','все 75'),('Все75','Все 75'),('и14','и 14'),('Все14','Все 14'),('периоды2021','периоды 2021'),('все13','все 13'),('и13','и 13'),('135','135'),('остальные135','остальные 135'),('ширине1440','ширине 1440'),('и390','и 390')]:report=report.replace(old,new)
(OUT/'Отчёт_3_страницы.md').write_text(polish(report))
print(json.dumps(summary,ensure_ascii=False))
