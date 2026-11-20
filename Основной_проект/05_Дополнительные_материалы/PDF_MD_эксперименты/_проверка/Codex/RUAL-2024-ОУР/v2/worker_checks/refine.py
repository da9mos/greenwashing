import re, json, hashlib, sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
baseline = (root / '_проверка/baseline/report.md').read_text()
parts = re.split(r'<!-- pdf_page: (\d+) -->', baseline)
pages = {int(parts[i]): parts[i+1] for i in range(1, len(parts), 2)}
changes = []

def log(n, message):
    changes.append({'pdf_page': n, 'change': message, 'basis': 'Исходное изображение PDF; локальный визуальный просмотр.'})

# Remove the supplemental OCR only where source text is already present and
# the image shows that the supplemental recognition is duplicate/logo noise.
for n in [1,5,6,10,19,32,33,41,56,67,68,80,109]:
    pages[n] = re.sub(r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\.\n\n.*?(?=\n> Служебная информация:|\n<details>)', '', pages[n], flags=re.S)
    log(n, 'Удалён ошибочный дополнительный OCR: дубли текстового слоя и распознавание графики; на стр. 68 также технический TSV, ошибочно попавший в текст.')

pages[1] = '''
<a id="pdf-page-1"></a>

## ОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ 2024

РУСАЛ

ТРАНСФОРМИРОВАТЬСЯ, НЕ ТЕРЯЯ СУТИ

<details>
<summary>Источник: PDF-страница 1</summary>

![Полная исходная страница 1](assets/page_0001.png)

</details>

'''
log(1, 'По изображению восстановлено декоративное слово «ТРАНСФОРМИРОВАТЬСЯ,» и название РУСАЛ; удалён бессмысленный OCR.')

for n in [2,9]:
    pages[n] = pages[n].replace('\x08','').replace('\x07','')
    log(n, 'Удалены управляющие коды U+0008 / U+0007, не представляющие видимые буквы: в оглавлении у конца заголовков, в перечне активов перед названиями. Остальная страница не прошла полную сверку.')

# Pair section-menu titles with their printed page labels rather than leaving
# two disconnected lists. PDF annotation links remain intact below the text.
for n, labels, values in [
    (5,['Основные сведения','Продукция РУСАЛа','География активов'],['8','10','14']),
    (10,['Стратегия и\u00a0цели устойчивого развития РУСАЛа до\u00a02035\u00a0года','Существенные факторы устойчивого развития бизнеса','Оценка существенности','Партнёрство и\u00a0членство в\u00a0ассоциациях и\u00a0международных инициативах','ЦУР и\u00a0приоритеты бизнеса в\u00a0области устойчивого развития'],['18','24','26','28','31']),
    (19,['Подход к\u00a0управлению вопросами окружающей среды','Водные ресурсы','Управление отходами','Выбросы в\u00a0атмосферу','Земельные ресурсы','Биоразнообразие'],['38','41','46','52','55','56']),
    (32,['Управление','Стратегия','Управление рисками','Цели и\u00a0метрики'],['64','66','72','73']),
]:
    pattern = '\n\n'.join('<p>'+re.escape(x)+'</p>' for x in labels+values)
    replacement = '<table>\n'+''.join(f'<tr><td>{a}</td><td>{b}</td></tr>\n' for a,b in zip(labels, values))+'</table>'
    pages[n], count = re.subn(pattern, lambda _: replacement, pages[n])
    assert count == 1, (n, count)
    log(n,'Пункты меню связаны с печатными номерами в двухколоночной таблице по изображению.')

pages[56] = pages[56].replace('> Служебная информация: ссылки исходного PDF', '<p>Код безопасности РУСАЛ</p>\n\n> Служебная информация: ссылки исходного PDF')
pages[68] = pages[68].replace('> Служебная информация: ссылки исходного PDF', '''<p>Национальные проекты России: Здравоохранение; Образование; Жилье и городская среда; Демография.</p>

<p>3 — Хорошее здоровье и благополучие; 8 — Достойная работа и экономический рост; 11 — Устойчивые города и населенные пункты.</p>

> Служебная информация: ссылки исходного PDF''')
log(68,'Текст и номера четырёх национальных проектов и трёх ЦУР переписаны с увеличенного фрагмента значков; основной текст сохранён из PDF.')

# Four columns of the scanned assurance statement, read left to right across
# each embedded sheet, then signature and organization details.
columns = [(root / f'_проверка/assurance_{i}.txt').read_text() for i in range(4)]
columns[0] = columns[0].replace('«Отчет»},','«Отчет»).')
columns[1] = columns[1].replace('{пересмотрен-', '(пересмотрен-').replace('вудиторских','аудиторских').replace('‘аудиторов','аудиторов')
columns[2] = columns[2].replace('> _ ', '> ').replace('> — ', '> ').replace('» посещение','> посещение').replace('стем,','с тем,')
columns[2] = columns[2].split('‚ gee')[0]
columns[3] = columns[3].replace('> _ ', '> ')
# Preserve source line hyphens: no conjectural dictionary-based joining.
body = '\n\n'.join('<p>'+x.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').strip().replace('\n','<br/>')+'</p>' for x in columns)
header = '''<p>Б1. НОВЫЕ ВЫЗОВЫ. НОВЫЕ РЕШЕНИЯ</p>

<p>ООО «ЦАТР – аудиторские услуги»<br/>
Россия, 115035, Москва<br/>Садовническая наб., 75<br/>
Тел.: +7 495 705 9700; +7 495 755 9700<br/>Факс: +7 495 755 9701<br/>
ОГРН: 1027739707203<br/>ИНН: 7709383532<br/>ОКПО: 59002827<br/>КПП: 770501001</p>

<p>TSATR – Audit Services LLC<br/>Sadovnicheskaya Nab., 75<br/>Moscow, 115035, Russia<br/>
Tel: +7 495 705 9700; +7 495 755 9700<br/>Fax: +7 495 755 9701<br/>www.b1.ru</p>
'''
footer = '''
<p>Хачатурян Михаил Сергеевич<br/>Партнер<br/>
Общество с ограниченной ответственностью<br/>
«Центр аудиторских технологий и решений – аудиторские услуги»</p>

<p>28 апреля 2025 г.</p>

<h3>Сведения о практикующем специалисте</h3>
<p>Наименование: Общество с ограниченной ответственностью «Центр аудиторских технологий и решений – аудиторские услуги»<br/>
Запись внесена в Единый государственный реестр юридических лиц 5 декабря 2002 г. и присвоен государственный регистрационный номер 1027739707203.<br/>
Местонахождение: 115035, Россия, г. Москва, Садовническая наб., д. 75.<br/>
Общество с ограниченной ответственностью «Центр аудиторских технологий и решений – аудиторские услуги» является членом Саморегулируемой организации аудиторов Ассоциация «Содружество» (СРО ААС). Общество с ограниченной ответственностью «Центр аудиторских технологий и решений – аудиторские услуги» включено в контрольный экземпляр реестра аудиторов и аудиторских организаций за основным регистрационным номером записи 12006020327.</p>

<h3>Сведения об организации</h3>
<p>Наименование: МКПАО «ОК РУСАЛ»<br/>
Запись внесена в Единый государственный реестр юридических лиц 25 сентября 2020 г. и присвоен государственный регистрационный номер 1203900011974.<br/>
Местонахождение: 236006, Россия, г. Калининград, ул. Октябрьская, д. 8, оф. 410.</p>
'''
old = pages[148]
start = old.index('> Служебная пометка: распознанный текст изображения')
end = old.index('> Служебная информация: ссылки исходного PDF', start)
pages[148] = old[:start] + header + '\n\n' + body + '\n\n' + footer + '\n\n' + old[end:]
log(148,'Заменён повреждённый OCR с TSV-вставками. Повторный Tesseract rus+eng на PDF 4x и на четырёх колонках; колонки визуально прочитаны, исправлены показанные ошибки OCR. Реквизиты, подпись-дата и нижние примечания переписаны с увеличенных фрагментов. Подпись остаётся на изображении.')

report = '# ОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ 2024\n\n'
report += '> Техническая информация о переносе: извлечены все 149 физических страниц. Полная постраничная сверка не завершена. Непроверенные текст, таблицы и порядок чтения имеют статус converted/pending в `_проверка/pages.json`. Изображения страниц сохранены как визуальная опора.\n\n'
for n in range(1,150):
    page = pages[n]
    if n != 1:
        page = re.sub(r'(<a id="pdf-page-\d+"></a>)', r'\1\n\n> Техническая пометка: полная сверка страницы по оригиналу — pending; отдельные исправления перечислены в реестре проверки.', page, count=1)
    report += f'<!-- pdf_page: {n} -->'+page
(root / 'report.md').write_text(report)

registry = json.loads((root / '_проверка/baseline/pages.json').read_text())
diagnostic_pages = [x['pdf_page'] for x in registry['pages'] if x['issues']]
viewed = [1,2,5,6,9,10,19,32,33,40,41,56,67,68,80,109,115,119,122,125,131,134,135,136,148]
for x in registry['pages']:
    n=x['pdf_page']
    x['conversion_status']='converted'
    x['review_status']='checked' if n==1 else 'pending'
    x['semantic_source_review_completed']=n==1
    x['verification_scope']='Полная визуальная сверка обложки' if n==1 else 'Механический перенос; полная сверка страницы не выполнена'
    x['source_image_viewed']=n in viewed
    x['original_diagnostics']=x['issues']
    x['issues']=[] if n==1 else ['Полная сверка текста, порядка чтения, таблиц и графики страницы по оригиналу не завершена.']
    x['corrections']=[c['change'] for c in changes if c['pdf_page']==n]
    if n in [2,9]:
        x['unresolved_unicode_after_correction']=0
        x['issues'].append('Просмотрены проблемные управляющие символы; остальная структура не подтверждена.')
    if x.get('ambiguous_cell_assignments'):
        x['ambiguous_cell_review']='Просмотрены увеличенные фрагменты. Все отмеченные глифы — пробелы/NBSP на границе ячеек; числовых или буквенных глифов в диагностике нет. Полная таблица не сверена.'
    if n==148:
        x['ocr_engine']='local Tesseract rus+eng, 4x render, four cropped columns'
        x['ocr_verified']=False
        x['issues'].append('Тело скана прочитано по четырём увеличенным колонкам и исправлено; окончательная сверка отображения и каждого знака всей страницы не завершена.')
registry['summary']={'total_pages':149,'converted':149,'checked_pages':[1],'pending_pages':list(range(2,150)), 'diagnostic_pages_inspected':diagnostic_pages,'full_document_review_completed':False}
(root / '_проверка/pages.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2))
(root / '_проверка/corrections.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))

source=json.loads(Path('source.json').read_text())
actual=hashlib.sha256(Path(source['source_pdf']).read_bytes()).hexdigest()
assert actual==json.loads((root/'_проверка/native_coverage.json').read_text())['source_sha256']
markers=[int(x) for x in re.findall(r'<!-- pdf_page: (\d+) -->',report)]
assert markers==list(range(1,150))
missing=[]
for link in re.findall(r'\]\((assets/[^)]+)\)',report):
    if not (root/link).is_file():missing.append(link)
assert not missing,missing
ids=set(re.findall(r'id="([^"]+)"',report))
broken=[x for x in re.findall(r'href="#([^"]+)"',report) if x not in ids]
assert not broken,broken
assert not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',report)
checks={'source_sha256':actual,'report_sha256':hashlib.sha256(report.encode()).hexdigest(),'physical_pages':len(markers),'page_order_ok':True,'missing_local_links':missing,'broken_internal_anchors':broken,'control_characters':0,'rendering_review_completed':False,'full_source_review_completed':False,'baseline_glyph_accounting_applies_to':'baseline/report.md; after source-based corrections exact glyph inventory is not asserted'}
(root/'_проверка/validation.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
print(json.dumps(checks,ensure_ascii=False,indent=2))
