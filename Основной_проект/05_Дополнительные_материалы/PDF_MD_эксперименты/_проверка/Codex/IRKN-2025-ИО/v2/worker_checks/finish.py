import json,re
from pathlib import Path
out=Path('result');a=out/'_проверка';p=a/'pages/0049.md';md=p.read_text();extra='''

Текст английского свидетельства (прочитан по исходному растровому объекту):

Certificate of ESG Rating  
Joint-Stock Company INK-Capital

China Chengxin Green Finance Technology (Beijing) Ltd. ("CCXGF") has conducted a comprehensive analysis of your latest performance in Environmental (E), Social (S), and Governance (G) areas. Upon the final approval by the Review Committee from CCXGF, your ESG rating is:

A-

Issue Date: December 24, 2025  
Valid Until: December 23, 2026

China Chengxin Green Finance Technology (Beijing) Ltd.  
December 24, 2025

> Техническое примечание: мелкий регистрационный идентификатор вверху свидетельства и мелкий текст российского свидетельства не прочитаны уверенно. Графические подписи и печати сохранены на изображении страницы.
''';md+=extra;p.write_text(md)
r=out/'report.md';report=r.read_text();needle='<!-- pdf_page: 50 -->';report=report.replace(needle,extra+'\n'+needle);r.write_text(report)
meta=json.loads((a/'pages.json').read_text());meta['pages'][48]['issues'].append('После просмотра исходного растрового объекта добавлен читаемый английский текст свидетельства; идентификатор и мелкий текст русского свидетельства остаются pending.')
meta['rendering_status']='HTML построен локальным Markdown-рендерером. Визуальная проверка отображения в Chromium недоступна: запуск браузера завершился SIGABRT в ограниченной среде.'
(a/'pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
(a/'limitations.md').write_text('''# Состояние конвертации

Учтены физические страницы 1–206, по порядку, по одному маркеру на страницу. Контрольная сумма источника совпадает с входным реестром. Текстовый слой извлечён на всех страницах; локальный Tesseract rus+eng обработал все 206 изображений. Исходные изображения скопированы как визуальная опора, не вместо текстовой транскрипции.

204 страницы имеют conversion_status converted, страницы 49 и 91 — pending из-за частично непрочитанного мелкого или перекрытого текста в растровых объектах. Review_status всех 206 страниц — pending. Полностью сверенных по PDF страниц нет. Изображения 1, 7, 9, 10, 11, 23, 27, 49, 58, 77, 91, 94, 136, 167, 200 просматривались для проверки устройства страницы или отдельного объекта. Это выборочный просмотр, не посимвольная сверка.

В исходном порядке текстовых блоков сохранены переносы строк и дефисы. Колонтитулы сохранены, поскольку систематическая проверка возможности их удаления не выполнена. Таблицы представлены HTML с текстом, извлечённым по областям ячеек. Объединения и разбиение строк ещё требуют визуальной сверки. У страницы 180 дополнительно сохранён полный текстовый слой из-за обнаруженного различия охвата; возможны повторы. Печатная нумерация не выводилась по смещению и оставлена null. Переходы извлечены из аннотаций PDF, адреса не проверялись во внешней сети.

HTML построен локально; запуск Chromium для визуальной проверки не удался (SIGABRT в ограниченной среде). Поэтому внешний вид не подтверждён. Необходима полная постраничная сверка, прежде всего таблиц и графиков; candidates OCR сохранены отдельно и не считаются установленными исправлениями.
''')
(a/'error-rules.md').write_text('''# Правила контроля извлечения

## Порядок блоков в многоколоночной верстке
Причина: геометрическое объединение строк смешивает колонки и карточки. Признак: подпись одного показателя склеена с другим числом или предложение перескакивает между колонками. Действие: сравнить исходные блоки и изображение; восстановить порядок только по оригиналу. Приёмка: весь затронутый объект читается в правильном порядке.
Сценарий: перемешанный кандидат отклоняется; кандидат, сверенный по всему объекту, принимается; неоднозначный получает pending.

## Порядок символов в табличных ячейках
Причина: извлечение таблицы переупорядочивает фрагменты шрифта и десятичные знаки. Признак: потеря пробелов и запятая на отдельной строке после цифр. Действие: извлекать текст из исходной области ячейки и сверять её по изображению. Приёмка: сохранены слова, десятичные разделители и соответствие заголовку.
Сценарий: склеенные слова и переставленные знаки отклоняются; посимвольно сверенная ячейка принимается; неясная структура остаётся pending. Автоматическая замена способа извлечения сама по себе не является сверкой.
''')
# Re-render exact final saved version.
import sys
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
render=MarkdownIt('commonmark',{'html':True}).render(report)
(a/'preview.html').write_text('<!doctype html><meta charset="utf-8"><style>body{font:16px Arial;margin:30px;max-width:1400px}table{border-collapse:collapse;display:block;overflow:auto}td{border:1px solid #aaa;padding:5px;min-width:55px;vertical-align:top}img{max-width:100%}pre{white-space:pre-wrap}</style>'+render.replace('src="assets/','loading="lazy" src="../assets/'))
assert list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',report)))==list(range(1,207))
for t in re.findall(r'\]\((assets/[^)]+)\)',report):assert (out/t).is_file()
anchors=set(re.findall(r'id="([^"]+)"',report));assert all(x in anchors for x in re.findall(r'\]\(#([^)]+)\)',report))
print('Final validation passed:',len(report),'characters;',len(anchors),'anchors')
