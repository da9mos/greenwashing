import sys,json,re,collections
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs');import pymupdf
root=Path('result');s=json.load(open('source.json'));d=pymupdf.open(s['source_pdf']);registry=json.load(open(root/'_проверка/pages.json'))
texts={n:(root/f'_проверка/pages/{n:04}.md').read_text() for n in range(1,136)}
texts[1]='# УСТОЙЧИВОЕ ЛИДЕРСТВО\n\nДОЛГОСРОЧНЫЙ РЕЗУЛЬТАТ\n\nРОСНЕФТЬ\n\n2024\n\nОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ\n'
texts[135]='РОСНЕФТЬ\n\nwww.rosneft.ru\n'
titles={4:'1. УСТОЙЧИВОЕ РАЗВИТИЕ И КОРПОРАТИВНОЕ УПРАВЛЕНИЕ',21:'2. ВЫСОКИЕ СТАНДАРТЫ ДЕЛОВОЙ ПРАКТИКИ',29:'3. НАУЧНО-ИННОВАЦИОННОЕ РАЗВИТИЕ И ВКЛАД В ТЕХНОЛОГИЧЕСКИЙ СУВЕРЕНИТЕТ РОССИИ',41:'4. ОХРАНА ОКРУЖАЮЩЕЙ СРЕДЫ НА БЛАГО БУДУЩИХ ПОКОЛЕНИЙ',58:'5. УГЛЕРОДНЫЙ МЕНЕДЖМЕНТ',67:'6. ОБЕСПЕЧЕНИЕ ПРОМЫШЛЕННОЙ БЕЗОПАСНОСТИ И ОХРАНЫ ТРУДА',79:'7. УПРАВЛЕНИЕ РИСКАМИ ВОЗНИКНОВЕНИЯ ЧРЕЗВЫЧАЙНЫХ СИТУАЦИЙ',83:'8. УПРАВЛЕНИЕ ПЕРСОНАЛОМ',102:'9. СОДЕЙСТВИЕ СОЦИАЛЬНО-ЭКОНОМИЧЕСКОМУ РАЗВИТИЮ',112:'10. ПРИЛОЖЕНИЯ'}
for n,title in titles.items():texts[n]='# '+title+'\n'
# Подписи вертикальных элементов схемы, выпавшие при извлечении.
texts[31]=texts[31].replace('Концептуальная схема Единой цифровой платформы**','Концептуальная схема Единой цифровой платформы**\n\nУнифицированность. Эластичность.')
# Названия рядов в пиктограммах, прочитанные по изображению.
for needle,label in [('Компании в 2024 году составили','Компании в 2024 году составили')]:pass
p=texts[8]
p=p.replace('- «Зеленые» инвестиции','### 3. Хорошее здоровье и благополучие\n\n- «Зеленые» инвестиции',1)
p=p.replace('- «Роснефть» является одним','### 7. Недорогостоящая и чистая энергия\n\n- «Роснефть» является одним',1)
p=p.replace('- «Роснефть» является\n','### 8. Достойная работа и экономический рост\n\n- «Роснефть» является\n',1)
# OCR двух логических страниц независимого заключения.
a=(root/'_проверка/scan113-0.txt').read_text();b=(root/'_проверка/scan113-1.txt').read_text()
a=a.replace('ЗАКЛЮЧЕНИЕ НЕЗАВИСИМОГО\nПРАКТИКУЮЩЕГО СПЕЦИАЛИСТА\n','')
a=a.replace('Россия, 15035','Россия, 115035').replace('Рах:','Fax:').replace('www.blru','www.b1.ru').replace('« » (далее','«✓» (далее').replace('‘удельные','удельные').replace('безопасности Ha','безопасности на')
b=b.replace('HbIx C проверкой','ных с проверкой').replace('‘достаточно','достаточно').replace('‘Сведения','Сведения').replace('‘организации','организации').replace('‘аудиторские','аудиторские')
sig='Старыгина Наталия Геннадьевна\nПартнер\nОбщество с ограниченной ответственностью\n\nСтр. 2\n\n'
b=b.replace(sig,'').replace('«Центр аудиторских технологий и решений - аудиторские услуги»','Старыгина Наталия Геннадьевна\nПартнер\nОбщество с ограниченной ответственностью\n«Центр аудиторских технологий и решений - аудиторские услуги»',1)
a=re.sub(r'(?m)^[>»]\s*','- ',a); b=re.sub(r'(?m)^[>a]\s*','- ',b)
texts[113]='# ЗАКЛЮЧЕНИЕ НЕЗАВИСИМОГО ПРАКТИКУЮЩЕГО СПЕЦИАЛИСТА\n\n'+a+'\n\n'+b
texts[8]=p
checked={1,135} # Полностью прочитаны обложки; обзор разделителей не повышает статус.
parts=[]
for rec in registry['pages']:
 n=rec['pdf_page'];page=d[n-1];raw=page.get_text(); nums=[]
 for block in page.get_text('blocks'):
  if block[1]>800:
   nums.extend(re.findall(r'(?m)^\s*(\d{1,3})\s*$',block[4]))
 rec['printed_page']=nums or None
 rec['content_type']='mixed_scan_text' if n==113 else ('raster_cover' if n in [1,135] else ('section_cover' if n in titles else 'spread_text_tables_graphics'))
 rec['conversion_status']='converted';rec['review_status']='checked' if n in checked else 'pending'
 rec['issues']=[] if n in checked else ['Полная постраничная сверка текста, чисел, сносок, порядка колонок и таблиц по оригиналу не завершена. Возможны ошибки переноса дефисов и порядка блоков.']
 if n==113:rec['issues'].append('Тело скана распознано локальным Tesseract rus+eng; исправлены отдельные ошибки по изображению. Полная сверка OCR не завершена.')
 if n==114:rec['issues'].append('При извлечении обнаружено нарушение порядка колонок и связей этапов сложной таблицы; использовать изображение для проверки структуры.')
 if n==31:rec['issues'].append('Восстановлены выпавшие вертикальные подписи схемы по изображению; прочие элементы страницы полностью не сверены.')
 if n==8:rec['issues'].append('Пиктограммы ЦУР содержат названия категорий; связи всех категорий с пунктами требуют дальнейшей проверки.')
 rec['visual_review_scope']='Полный текст и графика обложки' if n in checked else ('Обзор изображения разделителя; не полная сверка' if n in titles else ('Отдельные области по изображению' if n in [3,8,31,113,114] else 'Не просмотрена визуально'))
 text=texts[n].strip();(root/f'_проверка/pages/{n:04}.md').write_text(text+'\n')
 pagepart=f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+text
 if n==1:pagepart+='\n\n> Техническая пометка: рабочая версия конвертации. Учтены все 135 физических страниц. Полная сверка не выполнена; статусы и ограничения приведены в `_проверка/pages.json`. Изображения служат визуальной опорой и не заменяют текст.'
 if rec['issues']:pagepart+='\n\n> Техническая пометка: '+(' '.join(rec['issues'][1:]) if len(rec['issues'])>1 else 'Текст извлечён; полная сверка страницы по оригиналу ожидается.')
 links=[]
 for l in rec.get('links',[]):
  label=re.sub(r'\s+',' ',l['text']).strip() or 'Ссылка из PDF'
  label=label.replace('[','\\[').replace(']','\\]')
  if 'uri' in l:links.append(f'[{label}](<{l["uri"]}>)')
  elif 1<=l.get('target_pdf_page',0)<=135:links.append(f'[{label}](#pdf-page-{l["target_pdf_page"]})')
 if links:pagepart+='\n\n<details><summary>Ссылки из аннотаций PDF</summary>\n\n'+'\n\n'.join(dict.fromkeys(links))+'\n\n</details>'
 pagepart+=f'\n\n![Оригинал физической страницы {n}](assets/page_{n:04}.png)\n'
 parts.append(pagepart)
(root/'report.md').write_text('\n\n'.join(parts))
registry['status']='working_version';registry['review_summary']={'checked_pages':[1,135],'pending_pages':[n for n in range(1,136) if n not in checked],'render_review':'HTML построен и структурно разобран; визуальный просмотр итоговой HTML-версии не выполнен.'};(root/'_проверка/pages.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2))
print('assembled',len(parts),'pages',len((root/'report.md').read_text()),'characters')
