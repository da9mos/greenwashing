from pathlib import Path
import json,re,subprocess,hashlib,html,collections
O=Path('result');A=O/'_проверка';P=A/'pages';s=json.load(open('source.json'));reg=json.load(open(A/'pages.json'))
f=P/'0002.md';t=f.read_text();v=subprocess.check_output(['pdftotext','-f','2','-l','2','-layout','-x','0','-y','65','-W','595','-H','755',s['source_pdf'],'-']).decode().replace('\f','').rstrip()
t=re.sub(r'```text\n.*?\n```','# ценен вклад каждого\n\n```text\n'+v+'\n```',t,count=1,flags=re.S);f.write_text(t)
f=P/'0047.md';f.write_text(f.read_text().replace('# системная работа с персоналом','# системная работа c персоналом'))
f=P/'0132.md';t=f.read_text();t=t.replace('\nИндикаторы оценки достижений в области содействия социально-экономическому развитию регионов Российской Федерации\n','');f.write_text(t)
for r in reg['pages']:
 n=r['pdf_page'];t=(P/f'{n:04}.md').read_text()
 r['conversion_status']='converted';r['review_status']='pending'
 r['text_output']=f'pages/{n:04}.md';r['source_image']=f'assets/page_{n:04}.png'
 r['html_tables']=t.count('<table>');r['fixed_width_blocks']=len(re.findall(r'^```text$',t,re.M))
 if r['html_tables'] or r['fixed_width_blocks']:r.pop('detected_tables',None)
 if n in [144,145,146,147]:r['raster_body_transcribed']=True
 if n in [85,86]:r['content_type']=['photographic_spread','header_text'];r['issues']=['Фотографический разворот просмотрен в обзорном изображении; полная проверка страницы не заявляется.']
 if n==2:
  r.setdefault('reviewed_objects',[]).append('По оригиналу обнаружены и восстановлены две строки тела ниже обычной нижней границы разворота (до y=809).')
  r['issues'].append('Сложная страница с содержанием: порядок колонок и внутренние переходы требуют полной сверки.')
 # Ensure every unresolved technical issue is visible in the document itself.
 if r.get('unmatched_native_blocks'):r['issues'].append('Повернутые заголовки главы представлены дополнительными фрагментами; требуется восстановление их порядка.')
(O/'report.md').write_text('# Отчет о социальной деятельности Группы Газпром\n\n2024\n\n> **Техническая пометка к конвертации:** рабочая версия всего документа, физические страницы 1–150. Полная сверка по оригиналу не завершена; все страницы имеют статусы `converted/pending`. Текст сканированных заключений распознан локально и адресно исправлен по изображениям. Для сложных таблиц и диаграмм сохранены текстовые раскладки с колонками и оригиналы страниц; часть таблиц восстановлена в HTML и Markdown. Связи цветовых рядов, отдельные переносы, сноски и ячейки требуют дальнейшей сверки. Раздельные статусы, замечания и объекты частичной сверки перечислены в `_проверка/pages.json`.\n\n'+'\n\n'.join((P/f'{n:04}.md').read_text() for n in range(1,151)))
reg['summary']={'converted_pages':150,'fully_reviewed_pages':0,'review_status':'pending','partial_visual_review':'Обложка, обзор растровых разворотов, декоративные заголовки, отдельные числовые диаграммы и сканированные заключения. Это не полная сверка всего документа.'}
(A/'pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2))
# Validate the saved artifact, not just the in-memory fragments.
t=(O/'report.md').read_text();markers=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',t)));assert markers==list(range(1,151))
assets=re.findall(r'!\[[^\]]*\]\((assets/[^)]+)\)',t);missing=[x for x in assets if not (O/x).is_file()];assert not missing
anchors=set(re.findall(r'id="([^"]+)"',t));targets=re.findall(r'\]\(<#([^>]+)>\)',t);assert set(targets)<=anchors
assert not re.search(r'[\ue000-\uf8ff]',t)
index=json.load(open(s['index']));hash_mismatch=[]
for p in index['pages']:
 f=O/'assets'/f'page_{p["pdf_page"]:04}.png'
 if hashlib.sha256(f.read_bytes()).hexdigest()!=p['image_sha256']:hash_mismatch.append(p['pdf_page'])
assert not hash_mismatch
checks={'physical_markers':len(markers),'page_records':len(reg['pages']),'source_images':len(assets),'broken_local_images':missing,'internal_targets':len(targets),'missing_internal_targets':list(set(targets)-anchors),'image_hash_mismatches':hash_mismatch,'pua_remaining':False,'report_bytes':len(t.encode()),'report_sha256':hashlib.sha256(t.encode()).hexdigest()}
(A/'integrity.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2));print(json.dumps(checks,ensure_ascii=False,indent=2))
