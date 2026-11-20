from pathlib import Path
import json,re,collections,hashlib
import pymupdf
out=Path('result');c=out/'_проверка';meta=json.load(open(c/'pages.json'));s=json.load(open('source.json'));d=pymupdf.open(s['source_pdf']);fixes=[]
# Keep source line-ending hyphens rather than guessing which are lexical.
for n in range(1,153):
 p=c/'pages'/f'{n:04}.md';md=p.read_text();raw=d[n-1].get_text()
 for a,b in set(re.findall(r'([А-Яа-яЁёA-Za-z]+)-\n([А-Яа-яЁёA-Za-z]+)',raw)):
  pattern=r'(?<![А-Яа-яЁёA-Za-z])'+re.escape(a+b)+r'(?![А-Яа-яЁёA-Za-z])'
  md,k=re.subn(pattern,a+'-\n'+b,md)
  if k:fixes.append({'pdf_page':n,'kind':'preserve_source_hyphen','source_fragments':[a+'-',b],'count':k})
 if n==35:
  md=md.replace('~~','');fixes.append({'pdf_page':35,'kind':'remove_false_strikethrough','reason':'Связующие линии организационной схемы ошибочно распознаны как зачёркивание текста; проверено по изображению.'})
 p.write_text(md)
# Readable certificate text restored against the source image, including display lettering OCR missed.
p=c/'pages/0149.md';md=p.read_text();tail=md[md.index('<details>'):]
left=(c/'pages/0149_1_ocr.txt').read_text().replace('\nря\n','\n[Графическая подпись — см. оригинал страницы.]\n').replace('‘аудиторов','аудиторов').replace(' - Аудит',' – Аудит')
right='''## Заверение РСПП

Российский союз промышленников и предпринимателей

### СВИДЕТЕЛЬСТВО

об общественном заверении корпоративного нефинансового отчета

**Отчет о социальной деятельности Группы Газпром за 2025 год**

прошел процедуру общественного заверения в Совете РСПП по нефинансовой отчетности, индексам и рейтингам устойчивого развития:

Отчет о социальной деятельности Группы Газпром за 2025 год содержит значимую информацию по всем ключевым направлениям ответственной деловой практики в соответствии с принципами Социальной хартии российского бизнеса и с достаточной полнотой раскрывает сведения о деятельности Компании в этих направлениях.

Развернутое заключение Совета РСПП об общественном заверении Отчета о социальной деятельности Группы Газпром за 2025 год направлено в Компанию, которая может публиковать его без каких-либо изменений и использовать как для внутрикорпоративных целей, так и в целях коммуникаций с заинтересованными сторонами.

Регистрационный номер 333.01.05.01.25

Президент РСПП — А. Шохин

Москва 2026 г.

> Техническая пометка: графические подпись и печать сохранены на изображении оригинала. Текст внутри печати отдельно не расшифрован.
'''
p.write_text('> Техническая пометка: левая половина распознана OCR, полная сверка не завершена. Текст свидетельства справа исправлен визуальным чтением; подпись и печать сохранены изображением.\n\n'+left+'\n\n'+right+'\n\n'+tail)
meta['pages'][148]['issues'].append('На правой половине визуально восстановлены декоративное слово «СВИДЕТЕЛЬСТВО», А. Шохин, Москва 2026 г., исправлены подмены OCR. Мелкий текст печати отдельно не транскрибирован. Левая половина полностью не сверена.')
# Include fixed-column glossary to retain the relationship of multi-line abbreviations and expansions.
for n in [151,152]:
 p=c/'pages'/f'{n:04}.md';md=p.read_text();raw=d[n-1].get_text();
 if n==152:
  md=md.replace('ESG (англ.\nEnvironmental,\nSocial, Governance)\n\n\n**300**\n\n\nОхрана окружающей среды. Социальная ответственность. Корпоративное управление','| Сокращение | Расшифровка |\n|---|---|\n| ESG (англ. Environmental, Social, Governance) | Охрана окружающей среды. Социальная ответственность. Корпоративное управление |\n\n**300**')
 p.write_text(md)
head='# Отчет о социальной деятельности Группы Газпром\n\n2025\n\n> Техническое примечание: рабочая полная конвертация 152 физических страниц. Текстовый слой извлечён; тело сканов на физических страницах 146–149 распознано локальным OCR. Полная визуальная сверка не выполнена. Статусы и ограничения каждой страницы — в `_проверка/pages.json`. Дополнительные моноширинные представления сохраняют расположение табличных колонок; изображения оригиналов служат визуальной опорой. Исходные дефисы на границах строк сохранены там, где автоматическое извлечение их удаляло.\n\n'
report=head+'\n\n'.join(f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+(c/'pages'/f'{n:04}.md').read_text() for n in range(1,153));(out/'report.md').write_text(report)
for rec in meta['pages']:
 rec['markdown_chars']=len((c/'pages'/f"{rec['pdf_page']:04}.md").read_text());rec['conversion_status']='converted';rec['review_status']='pending'
meta['method']='Локальное извлечение PyMuPDF4LLM legacy с отключённым layout-модулем; проверенные границы разворотов; запрет исключения текста под векторной графикой; pdftotext -layout для альтернативной табличной вёрстки; Tesseract rus+eng для тела сканов 146–149.'
meta['review_scope']={'full_pages_checked':[],'layout_contact_sheets_inspected':'1–152; только классификация вёрстки, не сверка содержания','selected_source_images_inspected':[1,2,3,4,33,100,146,147,148,149],'selected_source_content_reviewed':['Порядок колонок физической страницы 4','Выявление сканов 146–149','Правое свидетельство на физической странице 149','Структура и связь ESG с расшифровкой на физической странице 152'],'note':'Ни одна страница не обозначена checked по выборочному просмотру.'}
(c/'pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2));(c/'fixes.json').write_text(json.dumps(fixes,ensure_ascii=False,indent=2));print('saved',len(report),'chars',len(fixes),'fixes')
