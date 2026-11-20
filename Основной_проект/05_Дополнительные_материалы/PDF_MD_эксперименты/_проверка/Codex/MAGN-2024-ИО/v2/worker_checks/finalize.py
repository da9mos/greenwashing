import re,json,html,hashlib
from pathlib import Path
r=Path('result');s=(r/'report.md').read_text();parts=re.split(r'<!-- pdf_page: \d+ -->',s);registry=json.load(open(r/'_проверка/pages.json'))
for n in range(279,283):
 text='\n> Служебная пометка: тело заключения находится в растровых изображениях низкого разрешения (434 × 615 пикселей на лист). Ниже — локальное OCR, не прошедшее полную сверку. Ошибки распознавания, пропуски и нарушения связей чисел в таблицах остаются нерешёнными; точные значения следует читать по исходному изображению.\n\n'
 count=0
 for j in range(2):
  suffix='_rows' if n>=281 else ''
  o=(r/f'_проверка/scan_{n}_{j}{suffix}.txt').read_text();count+=len(o)
  text+=f'\n<h3>Лист изображения {j+1}</h3>\n<pre>'+html.escape(o)+'</pre>\n'
 pos=parts[n].index('<details>');parts[n]=parts[n][:pos]+text+'\n'+parts[n][pos:]
 p=registry['pages'][n-1];p['conversion_status']='pending';p['review_status']='pending';p['ocr_chars']=count;p['ocr_engine']='local Tesseract rus+eng; psm3 text, psm6 tables';p['issues']=['Low-resolution raster body processed by OCR; recognition and table-cell associations remain unreliable and require source transcription.'];p['review_notes']=['Source images viewed; OCR output examined. No full-page fidelity claim.']
s=parts[0]+''.join(f'<!-- pdf_page: {n} -->'+parts[n] for n in range(1,330));(r/'report.md').write_text(s);(r/'_проверка/pages.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2))
markers=[int(x) for x in re.findall(r'<!-- pdf_page: (\d+) -->',s)];anchors=set(re.findall(r'id="([^"]+)"',s));missing=[]
for m in re.finditer(r'(?:href|src)="([^"]+)"|!\[[^\]]*\]\(([^)]+)\)',s):
 t=m.group(1) or m.group(2)
 if t.startswith('#'):
  if t[1:] not in anchors:missing.append(t)
 elif not re.match(r'[a-z]+:',t) and not (r/t).exists():missing.append(t)
check={'pages':len(markers),'page_sequence_valid':markers==list(range(1,330)),'missing_links':missing,'report_sha256':hashlib.sha256(s.encode()).hexdigest(),'source_sha256':json.load(open(r/'_проверка/native_coverage.json'))['source_sha256'],'checked_pages':[],'conversion_pending_pages':list(range(279,283)),'render_status':'failed: Chrome launch SIGABRT / TargetClosedError; HTML generated, no viewport screenshots','review_status':'selective only; all full-page reviews pending'}
(r/'_проверка/final_validation.json').write_text(json.dumps(check,ensure_ascii=False,indent=2))
(r/'_проверка/review.md').write_text('''# Проверка рабочей конвертации

Учтены все 329 физических страниц, последовательность маркеров и локальные ссылки проверены. Исходный механический report сохранён в versions/report.native.md. В report.md сохранён весь доступный текстовый слой; все 329 полных исходных изображений доступны в assets.

Просмотрены обзорные изображения всех 26 диагностических страниц (1, 34, 60, 229, 236, 263, 269, 303–320, 328). Увеличенные участки: таблица 34; Unicode-контекст 60, 236, 303, 328. Полная сверка всех таблиц и страниц НЕ выполнена. Контрольные листы не подтверждают чтение мелких символов. Исправления перечислены в corrections.json.

Дополнительно просмотрены обзорные изображения страниц с малым количеством текста и заметной растровой площадью: 5, 6, 7, 12, 14, 21, 50, 53, 56, 75, 77, 85, 112, 127, 131, 163, 182, 188, 193, 279–282. В 279–282 выявлено растровое тело документа, отсутствующее в механической транскрипции. Все восемь листов обработаны локальным Tesseract rus+eng; исходное OCR сохранено рядом и добавлено в report.md. Качество исходного растра низкое: распознавание чисел и структуры таблиц не завершено, conversion_status=pending. Ни одна страница не получила checked.

Рендер указанной пользователем командой: HTML создан, Chrome завершился при запуске (SIGABRT, TargetClosedError, kill EPERM). Снимки 1440/390 не получены и не просмотрены. Отображение итогового файла не подтверждено. HTML промежуточной версии оставлен в render; после добавления OCR он не соответствует финальной версии.

Ограничения: порядок чтения многоколоночного текста, связи диаграмм, сносок и всех 200 механически обнаруженных таблиц требуют полной сверки. Числовой учёт исходных глифов не подтверждает семантическую точность. Реестр каждой страницы содержит отдельные conversion_status, review_status и issues.
''')
(r/'_проверка/error_rules.md').write_text('''# Правила контроля подтверждённых классов ошибок

1. Геометрический детектор может принять края страницы за объединённую ячейку и вынести тело таблицы в перемешанный текст. Признаки: ячейка занимает почти всю страницу, пустые соседние строки, заголовки вместе с колонтитулами. По изображению установить реальные границы; повторно извлечь глифы в отдельные ячейки. Приёмка: все заголовки, строки, столбцы и примечания соответствуют оригиналу. Сценарий: ложное объединение отклоняется; подтверждённая сетка принимается; неразличимая граница остаётся pending.

2. Управляющие коды шрифтов не являются автоматически видимыми символами. Проверять их координаты и изображение. Заменять только после установления функции: пробел, отступ или отсутствие видимого знака. Сценарий: необоснованное удаление видимого знака отклоняется; подтверждённый пробел принимается; неизвестный глиф помечается.

3. Наличие нативного заголовка может скрывать полностью растровое тело. Проверять страницы с небольшим текстовым слоем и крупными растровыми объектами. OCR обязателен для тела; изображения и учёт нативных глифов не подтверждают транскрипцию. Сценарий: заголовок плюс непрочитанный скан отклоняется как завершённый; сверенный OCR принимается; неразборчивые таблицы остаются pending.
''')
print(json.dumps(check,ensure_ascii=False))
