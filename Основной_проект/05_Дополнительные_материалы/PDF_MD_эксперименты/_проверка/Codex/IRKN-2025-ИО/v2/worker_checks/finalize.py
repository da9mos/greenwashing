import sys,json,re,html,collections
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf
from markdown_it import MarkdownIt
out=Path('result');audit=out/'_проверка';meta=json.loads((audit/'pages.json').read_text());src=json.loads(Path('source.json').read_text());d=pymupdf.open(src['source_pdf']);parts=['# Место рождения достижений\n\nГодовой отчет АО «ИНК-Капитал» за 2025 год\n\n> Техническое примечание: рабочая версия конвертации всех 206 физических страниц. Полная визуальная сверка не выполнена. Изображения служат визуальной опорой; реестр обработки и ограничений находится в `_проверка/pages.json`.\n'];candidates=[];fallback=[]
for n in range(1,207):
 f=audit/'pages'/f'{n:04}.md';md=f.read_text();raw=f.with_suffix('.txt').read_text();rec=meta['pages'][n-1]
 def words(x):return set(re.findall(r'\w+',html.unescape(x).lower()))
 missing=words(raw)-words(re.sub('<[^>]+>',' ',md));rec['native_missing_tokens']=sorted(missing)
 if missing:
  md+='\n\n<details><summary>Дополнительный текстовый слой: фрагменты могут повторяться; структура требует сверки</summary>\n<pre>'+html.escape(raw)+'</pre>\n</details>\n';fallback.append(n);rec['issues'].append('Для исключения потерь при выделении таблиц дополнительно сохранён полный текстовый слой страницы; возможны повторы.')
 # Actual short titles from text layer, preserving text exactly.
 for b in d[n-1].get_text('dict')['blocks']:
  spans=[s for l in b.get('lines',[]) for s in l['spans']];bt='\n'.join(''.join(s['text'] for s in l['spans']) for l in b.get('lines',[])).strip()
  if spans and 2<len(bt)<160 and min(s['size'] for s in spans)>=18 and not re.fullmatch(r'[\d\s/.,%–—-]+',bt):
   candidate=html.escape(bt).replace('\n','  \n')
   if candidate in md:md=md.replace(candidate,('## ' if max(s['size'] for s in spans)>=27 else '### ')+candidate.replace('  \n',' '),1)
 ocr=(audit/'pages'/f'{n:04}.ocr.txt').read_text();native=set(re.findall('[а-яёa-z]{3,}',raw.lower()));extra=[]
 for line in ocr.splitlines():
  w=re.findall('[а-яёa-z]{3,}',line.lower());new=[v for v in w if v not in native]
  if len(new)>=3 and len(new)/max(1,len(w))>.5:extra.append(line)
 if extra:candidates.append({'pdf_page':n,'lines':extra});rec['issues'].append('OCR выявил отличающиеся строки; кандидаты сохранены в ocr-candidates.json, точность не подтверждена.')
 if n==1:
  md+='\n25 лет. ИРКУТСКАЯ НЕФТЯНАЯ КОМПАНИЯ.\n';rec['issues'].append('Визуально прочитана эмблема «25 лет» и название компании; полной сверки страницы нет.')
 if n==49:
  md+='\n> Техническое примечание: мелкий текст двух свидетельств на изображениях распознан частично. Читаются «Certificate of ESG Rating», «Joint-Stock Company INK-Capital», «A-»; на российском свидетельстве — «СВИДЕТЕЛЬСТВО», «эксперт ра», «РЕЙТИНГ ESG», «АО "ИНК-Капитал"», «ESG-A–». Остальные мелкие строки требуют отдельной сверки; см. изображение страницы.\n';rec['conversion_status']='pending';rec['issues'].append('Не завершено чтение мелкого текста двух растровых рейтинговых свидетельств.')
 if n==91:
  md+='\n> Техническое примечание — текст внутри фотографии: «GLOBAL MANAGEMENT CHALLENGE»; «−802 тыс. евро», «−190 тыс. евро»; «Прибыль компании в последний период»; «42 сборщика» — «Квалифицированных сотрудников работает в компании»; «10 станков» — «Станков в распоряжении компании». Подпись к первому показателю частично перекрыта человеком.\n';rec['conversion_status']='pending';rec['issues'].append('Прочитан доступный текст экрана внутри фотографии; подпись первого показателя частично перекрыта.')
 rec['visual_review_scope']='partial' if n in [1,7,9,10,11,23,27,49,58,77,91,94,136,167,200] else 'not_reviewed'
 if rec['visual_review_scope']=='partial':rec['issues'].append('Просмотрено изображение для проверки устройства страницы или отдельного объекта; это не полная сверка.')
 # Never infer printed numbering from offset.
 rec['printed_page']=None
 f.write_text(md);parts.append(f'\n<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+md)
report='\n'.join(parts);(out/'report.md').write_text(report);(audit/'pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2));(audit/'ocr-candidates.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2))
render=MarkdownIt('commonmark',{'html':True}).render(report)
(audit/'preview.html').write_text('<!doctype html><meta charset="utf-8"><style>body{font:16px Arial;margin:30px;max-width:1400px}table{border-collapse:collapse;display:block;overflow:auto}td{border:1px solid #aaa;padding:5px;min-width:55px;vertical-align:top}img{max-width:100%}pre{white-space:pre-wrap}</style>'+render.replace('src="assets/','loading="lazy" src="../assets/'))
refs=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',report);assert all((out/p).exists() for p in refs);assert list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',report)))==list(range(1,207))
checks={'pages':206,'page_markers_unique_and_ordered':True,'image_links':len(refs),'missing_local_images':0,'table_text_fallback_pages':fallback,'ocr_pages':sum(p.get('ocr_status')=='completed' for p in meta['pages']),'conversion_status_counts':dict(collections.Counter(p['conversion_status'] for p in meta['pages'])),'review_status_counts':dict(collections.Counter(p['review_status'] for p in meta['pages'])),'full_visual_review_pages':0}
(audit/'validation.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2));print(json.dumps(checks,ensure_ascii=False));print('candidates',json.dumps(candidates,ensure_ascii=False))
