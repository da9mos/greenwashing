"""Rebuild the adjudicated extraction reference from the blind Markdown and source PDFs."""
import csv
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import fitz

HERE = Path(__file__).resolve().parent
REPORTS = None
FIELDS = (
    'id report_id pdf_page source_kind locator source_evidence subject block block2 '
    'claim_type topic metric period comparison_period value unit status related_ids note'
).split()


def plain(text):
    return ' '.join(text.split())


def pdf_key(text):
    return re.sub(r'[\s\u00ad]', '', text)


def read_originals():
    texts = {}
    manifest = json.loads((HERE / 'Реестр_страниц.json').read_text(encoding='utf-8'))
    for item in manifest:
        report = item['report_id']
        source = REPORTS / (report + '.pdf')
        assert hashlib.sha256(source.read_bytes()).hexdigest() == item['pdf_sha256']
        with fitz.open(source) as pdf:
            texts[report] = pdf[item['physical_pdf_page'] - 1].get_text()
    return texts


def read_blind():
    rows = {}
    for line in (HERE / 'Разметка_GPT-6.1-Sol.md').read_text(encoding='utf-8').splitlines():
        if not re.match(r'^\| (?:KMAZ|ALRS|PLZL)-\d\d \|', line):
            continue
        parts = [part.strip() for part in line.strip('|').split('|')]
        assert len(parts) == 13
        rows[parts[0]] = parts
    assert Counter(rid.split('-')[0] for rid in rows) == {'KMAZ': 18, 'ALRS': 24, 'PLZL': 25}
    return rows


def from_blind(blind, key, evidence=None, **updates):
    _, report, page, locator, quote, subject, block, secondary, kind, metric, _, _, _ = blind[key]
    row = dict.fromkeys(FIELDS, '')
    row.update(id=key, report_id=report, pdf_page=page, source_kind='text', locator=locator,
               source_evidence=json.dumps(evidence if evidence is not None else [quote], ensure_ascii=False),
               subject=subject, block=block, block2=secondary, claim_type=kind.lower(),
               metric=metric, status='scored')
    row.update(updates)
    return row


def kamaz(blind):
    rows = []
    for n in range(1, 19):
        key = f'KMAZ-{n:02}'
        quote = blind[key][4]
        evidence = [quote]
        update = {'topic': 'управление рисками'}
        if n <= 4:
            update.update(period='2024', value=('13', '305', '22', '299')[n-1],
                          unit=('проверка', 'мероприятие', 'проверка', 'мероприятие')[n-1])
        if n == 2:
            evidence.append('В 2024 году Служба внутреннего аудита провела 13 аудиторских проверок.')
        if n in (3, 4):
            evidence.append('В 2024 году')
            update['note'] = 'Год следует из контекста левой врезки.'
        if n == 6:
            evidence = ['Ключевые документы, регламентирующие внутренний аудит ПАО «КАМАЗ»:',
                        'законодательство Российской Федерации;', 'Устав ПАО «КАМАЗ»;',
                        'Политика ПАО «КАМАЗ» в области внутреннего аудита;', 'иные внутренние документы;',
                        'международные основы профессиональной практики внутреннего аудита Международного института внутренних аудиторов (IIA).']
            update['note'] = 'Перечень закрепляет, какими документами регулируется конкретная функция ПАО «КАМАЗ».'
        if 9 <= n <= 18:
            evidence.append('Ключевые задачи:' if n <= 13 else 'Основные функции:')
            update['note'] = 'Раскрытый мандат текущей службы.'
        if n == 13:
            update['topic'] = 'этика и антикоррупция'
        if n in (9, 14):
            update['related_ids'] = 'KMAZ-14' if n == 9 else 'KMAZ-09'
            update['note'] += ' Связанные формулировки задачи и функции.'
        rows.append(from_blind(blind, key, evidence=evidence, **update))
    return rows


# Values in source order 2021, 2022, 2023, 2024, checked by row and column in the PDF.
ALROSA = [
    ('Списочная численность на конец года', '31988 33756 35106 35511'),
    ('Женщины', '10454 10623 10827 10860'), ('Мужчины', '21534 23133 24279 24651'),
    ('Численность работников, в том числе:', '31988 33756 35106 35511'),
    ('работающих в России', '31860 33292 35028 35417'),
    ('работающих в зарубежных странах', '128 464 78 94'),
    ('Доля работников из России', '100% 99% 100% 100%'),
    ('Доля работников из зарубежных стран', '0% 1% 0% 0%'),
    ('Работники по бессрочному трудовому договору', '29701 30749 32080 32417'),
    ('Женщины', '9910 10044 10232 10288'), ('Мужчины', '19791 20705 21848 22129'),
    ('Доля работников по бессрочному трудовому договору', '93% 91% 91% 91%'),
    ('Работники по срочному трудовому договору', '2287 3007 3026 3075'),
    ('Женщины', '544 579 595 553'), ('Мужчины', '1743 2428 2431 2522'),
    ('Доля работников по срочному трудовому договору', '7% 9% 9% 9%'),
    ('Работники, работающие полный рабочий день', '28559 33716 35039 35374'),
    ('Женщины', '9129 10596 10776 10772'), ('Мужчины', '19430 23120 24263 24602'),
    ('Доля работников, работающих полный рабочий день', '89% 100% 100% 100%'),
    ('Работники, работающие неполный рабочий день', '3429 40 67 137'),
    ('Женщины', '1325 27 51 88'), ('Мужчины', '2104 13 16 49'),
    ('Доля работников, работающих неполный рабочий день', '11% 0% 0% 0%'),
]


def printed(value):
    return value if value.endswith('%') else format(int(value), ',').replace(',', ' ')


def alrosa(blind, source):
    # Check full text-layer rows in order, not a page-wide search for individual numbers.
    ordered = [*ALROSA[8:], *ALROSA[:8]]
    cursor = 0
    source = pdf_key(source)
    for label, values in ordered:
        row = pdf_key(label + values)
        index = source.find(row, cursor)
        assert index >= 0, (label, values)
        cursor = index + len(row)
    groups = {10: 9, 11: 9, 14: 13, 15: 13, 18: 17, 19: 17, 22: 21, 23: 21}
    rows = []
    for n, (label, values) in enumerate(ALROSA, 1):
        key = f'ALRS-{n:02}'
        heading = blind[key][3].split('»,', 1)[0].lstrip('«')
        parent = ALROSA[groups[n] - 1][0] if n in groups else ''
        metric = f'{parent} / {label.lower()}' if parent else label
        expected = re.findall(r'20\d\d = ([\d %]+)', blind[key][10])
        assert [v.replace(' ', '') for v in expected] == values.split()
        for year, value in zip(range(2021, 2025), values.split(), strict=True):
            related = f'ALRS-{4 if n == 1 else 1:02}-{year}' if n in (1, 4) else ''
            evidence = [part for part in (heading, parent, label, str(year), printed(value)) if part]
            rows.append(from_blind(
                blind, key, evidence=evidence, id=f'{key}-{year}', source_kind='table',
                locator=f'{heading} / {metric} / {year}', topic='персонал и оплата', metric=metric,
                period=str(year), value=value.removesuffix('%'), unit='%' if value.endswith('%') else 'человек',
                related_ids=related, note='Совпадающий ряд общей численности в другой таблице.' if related else '',
            ))
    return rows


def polyus(blind):
    rows = []

    def add(n, evidence=None, **kwargs):
        key = f'PLZL-{n:02}'
        fields = {'topic': 'энергия' if n >= 8 else 'климат'}
        fields.update(kwargs)
        rows.append(from_blind(blind, key, evidence=evidence, **fields))

    add(1, metric='Заявленное снижение выбросов ПГ', related_ids='PLZL-24',
        note='Ненумерованное утверждение о снижении. База и период не названы. Вклад в ЦУР без отдельной цели сохранён в цитате.')
    add(2, id='PLZL-02-level', period='2025', value='1,5', unit='млн т CO2-экв.',
        related_ids='PLZL-05-2025', note='Совпадающее число с графиком. Тождество периметров прямо не оговорено.')
    add(2, id='PLZL-02-change', metric='Изменение прямых выбросов ПГ', period='2025',
        comparison_period='2024', value='+14', unit='%')
    add(2, evidence=['в связи с увеличением объемов извлеченной горной массы'],
        id='PLZL-02-cause', metric='Названная причина роста прямых выбросов ПГ', period='2025',
        related_ids='PLZL-02-change', note='Причина в формулировке отчёта.')
    add(3, metric='Относительная позиция по углеродному следу',
        note='Сравнение без указанного места в рейтинге и без перечня сопоставимых компаний.')
    add(3, evidence=['закупке электроэнергии полностью из возобновляемых источников'],
        id='PLZL-03-power', topic='энергия', metric='Закупка электроэнергии из возобновляемых источников',
        related_ids='PLZL-08-power,PLZL-18', note='Повтор близкого раскрытия в другом месте страницы.')
    add(4, id='PLZL-04-ounce', period='2025', value='0,56', unit='т СО2‑экв./унц. золота в лигатурном золоте')
    add(4, id='PLZL-04-tonne', period='2025', value='17972', unit='т СО2‑экв./т золота в лигатурном золоте')

    for n, first, series, values, unit in [
        (5, 2021, 'Прямые, область охвата 1', '1,33 1,51 1,34 1,31 1,50', 'млн т CO2-экв.'),
        (6, 2021, 'Косвенные энергетические, область охвата 2 (рыночный метод)', '0,009 0,007 0,007 0,007 0,007', 'млн т CO2-экв.'),
        (7, 2021, 'Удельные выбросы, кг CO2-экв. / т переработанной руды', '20 23 22 26 29', 'кг CO2-экв. / т переработанной руды'),
        (15, 2023, 'Общее потребление энергии, ТДж', '9717 9562 9742', 'ТДж'),
        (16, 2023, 'Тепловая энергия', '1822 1757 1753', 'ТДж'),
        (17, 2023, 'Электрическая энергия', '7895 7805 7989', 'ТДж'),
    ]:
        for year, value in enumerate(values.split(), first):
            displayed = printed(value) if n >= 15 else value
            heading = ('Общие прямые и косвенные энергетические выбросы парниковых газов в абсолютном и удельном выражении'
                       if n <= 7 else 'Общее потребление энергии, ТДж')
            evidence = [heading, *([series] if series != heading else []), str(year), displayed]
            note = ('Сноска 1. Периметр группы в целом.' if n <= 7
                    else 'Периметр графика не раскрыт. Текстовый итог за 2025 год вынесен отдельно.'
                    if n == 15 else '')
            related = {5: 'PLZL-02-level', 15: 'PLZL-12-level', 16: 'PLZL-14-level', 17: 'PLZL-17-level'}.get(n, '') if year == 2025 else ''
            add(n, evidence, id=f'PLZL-{n:02}-{year}', source_kind='chart',
                locator=f'{heading} / {series} / {year}', period=str(year), value=value,
                unit=unit, note=note, related_ids=related)

    add(8, evidence=['«Полюс» повышает энергоэффективность своей деятельности'],
        metric='Повышение энергоэффективности')
    add(8, evidence=['получая электроэнергию полностью из возобновляемых источников'],
        id='PLZL-08-power', metric='Электроэнергия из возобновляемых источников',
        related_ids='PLZL-03-power,PLZL-18')
    add(9, block='G', block2='E', topic='управление рисками', period='2025',
        metric='Аудит соответствия ISO 50001:2018',
        note='Выполненная проверка системы энергоменеджмента. Организация аудитора не названа.')
    add(10, period='2025', metric='Завершение проектирования АСУ ТЭР')
    add(11, evidence=['Участие в III конференции Ассоциации развития возобновляемой энергетики (АРВЭ)'],
        id='PLZL-11-arve', period='2025', metric='Участие в конференции АРВЭ')
    add(11, evidence=['в международном форуме «Острова устойчивого развития: климатический аспект»'],
        id='PLZL-11-climate', period='2025', topic='климат', metric='Участие в форуме с климатической тематикой')
    add(11, evidence=['в VI Северном форуме по устойчивому развитию'], id='PLZL-11-north',
        period='2025', status='pending', block='', topic='', metric='Участие в Северном форуме',
        note='Факт участия указан. Конкретный предмет E/S/G из страницы не следует.')
    add(12, id='PLZL-12-level', period='2025', value='24748', unit='ТДж', related_ids='PLZL-15-2025',
        note='Текстовый итог. Периметр и сопоставимость с графиком не установлены.')
    add(12, id='PLZL-12-change', metric='Изменение совокупного потребления энергии', period='2025',
        comparison_period='2024', value='+11', unit='%')
    add(13, evidence=['Это связано с увеличением объемов добычи и транспортировки руды.',
                      'В 2025 году совокупное потребление энергии составило 24 748 ТДж'],
        period='2025', related_ids='PLZL-12-change')
    readings = [
        (14, 'Потребление тепловой энергии', '1753', '-0,2', 'PLZL-16-2025'),
        (17, 'Потребление электрической энергии', '7989', '+2', 'PLZL-17-2025'),
    ]
    energy_quote = blind['PLZL-14'][4].replace('(-0,2%', '(–0,2%').replace('электрической –', 'электрической —')
    for n, metric, level, change, related in readings:
        add(n, [energy_quote], id=f'PLZL-{n:02}-level', locator='Правая колонка, верхний абзац',
            metric=metric, period='2025', value=level, unit='ТДж', related_ids=related)
        add(n, [energy_quote], id=f'PLZL-{n:02}-change', locator='Правая колонка, верхний абзац',
            metric='Изменение: ' + metric.lower(), period='2025', comparison_period='2024', value=change, unit='%')
    add(18, ['100%', 'приобретенной электроэнергии для собственного потребления произведено на основе возобновляемых источников2 на производственных активах с 2021 года',
             'С учетом приобретения сертификатов происхождения электрической энергии.'],
        period='с 2021 года', value='100', unit='%', related_ids='PLZL-03-power,PLZL-08-power',
        note='Сноска 2. Отдельные годовые значения не заявлены.')
    add(19, metric='Анализ внедрения генерации из возобновляемой энергии')
    add(20, period='2025')
    add(21, [blind['PLZL-21'][4].replace('ветропарка –', 'ветропарка —')], period='2026',
        note='Продолжение подбора и обоснования. Строительство как обязательство не заявлено.')
    add(22, period='следующий отчётный период')
    add(23, period='2026', related_ids='PLZL-25')
    add(24, metric='Заявленное снижение выбросов ПГ', topic='климат', related_ids='PLZL-01')
    add(25, period='2026', related_ids='PLZL-23')
    return rows


def main():
    global REPORTS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reports-dir', type=Path, required=True,
                        help='Папка с тремя исходными PDF, имена REPORT_ID.pdf')
    REPORTS = parser.parse_args().reports_dir
    originals = read_originals()
    blind = read_blind()
    rows = kamaz(blind) + alrosa(blind, originals['ALRS-2024-ОУР']) + polyus(blind)
    ids = {row['id'] for row in rows}
    assert len(ids) == len(rows)
    source = {key: pdf_key(text) for key, text in originals.items()}
    for row in rows:
        if row['id'] in ('PLZL-02-level', 'PLZL-02-change'):
            row['source_evidence'] = row['source_evidence'].replace('CO₂', 'CO2')
        if row['id'].startswith('PLZL-04-'):
            row['source_evidence'] = row['source_evidence'].replace('CO₂-экв.', 'СО2‑экв.')
        assert set(filter(None, row['related_ids'].split(','))) <= ids
        for quote in json.loads(row['source_evidence']):
            assert pdf_key(quote) in source[row['report_id']], (row['id'], quote)
    assert all(row['block'] in ('E', 'S', 'G') for row in rows if row['status'] == 'scored')
    result = HERE / 'Эталон_ESG.csv'
    with result.open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS, delimiter=';')
        writer.writeheader()
        writer.writerows(rows)
    with result.open(encoding='utf-8-sig', newline='') as file:
        assert list(csv.DictReader(file, delimiter=';')) == rows
    print(Counter((row['report_id'], row['status']) for row in rows))
    print(Counter(row['source_kind'] for row in rows if row['status'] == 'scored'))


if __name__ == '__main__':
    main()
