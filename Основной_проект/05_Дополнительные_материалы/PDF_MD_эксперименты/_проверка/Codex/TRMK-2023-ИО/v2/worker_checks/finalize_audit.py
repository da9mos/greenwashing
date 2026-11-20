import json,hashlib,re,sys,shutil
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs');import pymupdf as f
sys.path.insert(0,'/private/tmp/sber-diff-libs');from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
root=Path('result');checks=root/'_проверка';s=json.load(open('source.json'));doc=f.open(s['source_pdf']);report=(root/'report.md').read_text();sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
if not (checks/'initial_pages.json').exists():shutil.copy2(checks/'pages.json',checks/'initial_pages.json')
if not (checks/'initial_native_coverage.json').exists():shutil.copy2(checks/'native_coverage.json',checks/'initial_native_coverage.json')
initial=json.load(open(checks/'initial_pages.json'))['pages'];derived=json.load(open(checks/'repaired_candidate/_проверка/pages.json'))['pages']
checked={1,10,11,18,20,22,25,32,38,39,40,42,43}
reviewed_details={1,10,11,18,20,22,25,27,32,38,39,40,42,43}
manual={1,3,5,6,8,9,10,11,13,15,18,20,22,25,32,34,37,38}
tables={19:[5,2],23:[6,3],27:[6,4],39:[[8,4],[6,2],[10,2]],40:[7,5]}
records=[]
for n in range(1,44):
 vals=[]
 for b in doc[n-1].get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   for sp in l['spans']:
    if sp['bbox'][0]>1800 and sp['bbox'][1]<120 and sp['text'].strip().isdigit():vals.append(sp['text'].strip())
 pn=list(dict.fromkeys(vals));visible=n not in {1,3,15,37,43}
 fixes=[]
 if initial[n-1].get('unresolved_unicode'):fixes.append('Восстановлены Unicode-соответствия встроенных CID-шрифтов по атласам глифов исходного PDF; отдельные карты для различных подмножеств шрифтов.')
 if n not in {1,2,3,15,37,43}:fixes.append('Удалены подтвержденные повторные верхние колонтитулы и навигация; декоративные рамки не представлены таблицами.')
 if n in manual:fixes.append('Адресно восстановлены декоративный текст, подписи показателей или связи схемы по исходному изображению.')
 if n in tables:fixes.append('Восстановлена целая таблица с учетом чередующихся заливок строк; текст и числа ячеек перенесены общей программой из глифов по выбранным границам.')
 if n in {1,3,5,7,15,37,38}:fixes.append('Проверен диагностический OCR: конфликты оказались дублями нативного текста/декора; ошибочные OCR-добавления исключены. На обложке вручную прочитан текст логотипа.')
 if n in {13,24}:fixes.append('Диагностика неоднозначных ячеек относится к декоративной рамке/схеме; ложная таблица исключена, текст перенесен отдельно.')
 issues=[]
 if n not in checked:issues.append('Полная построчная сверка всей страницы по оригиналу не завершена; просмотр контактного листа и адресные исправления не равны полной сверке.')
 if n==27:issues.append('Два URL разорваны в оригинале на строках с дефисом. Видимые символы сохранены; в PDF нет аннотаций ссылок, адрес назначения не подтвержден.')
 if n==40:issues.append('Звездочка после названия основного акционера сохранена; поясняющая сноска на данной странице источника отсутствует.')
 records.append({'pdf_page':n,'printed_label_from_source_text':pn,'printed_label_visually_confirmed':visible,'content_type':'native_text_with_graphics','conversion_status':'converted','review_status':'checked' if n in checked else 'pending','semantic_source_review_completed':n in checked,'review_scope':'Полное визуальное чтение содержания страницы и сопоставление с сохраненным текстом; браузерная проверка недоступна.' if n in checked else 'Просмотр исходной страницы на контактном листе; адресная проверка диагностик, шрифта и структуры. Полная построчная сверка pending.','source_image_viewed':True,'source_image_view':'individual_or_full_readable_view' if n in reviewed_details else 'contact_sheet','issues':issues,'corrections':fixes,'initial_diagnostics':initial[n-1]['issues'],'derived_diagnostics':derived[n-1]['issues'],'table_shape_after_repair':tables.get(n),'source_image':f'assets/page_{n:04d}.png'})
(checks/'pages.json').write_text(json.dumps({'source_pdf':s['source_pdf'],'source_sha256':sha(s['source_pdf']),'physical_pages':len(doc),'final_report_sha256':sha(root/'report.md'),'overall_status':'converted; partial source review; browser render pending','pages':records},ensure_ascii=False,indent=2)+'\n')
# Link and structure verification of final saved report
md=MarkdownIt('commonmark',{'html':True}).enable('table');soup=BeautifulSoup(md.render(report),'html.parser')
markers=[int(x) for x in re.findall(r'<!-- pdf_page: (\d+) -->',report)];missing=[]
for im in soup.find_all('img'):
 if not (root/im['src']).is_file():missing.append(im['src'])
anchors=[e['id'] for e in soup.select('[id]')];badlinks=[]
for a in soup.find_all('a',href=True):
 if a['href'].startswith('#') and a['href'][1:] not in anchors:badlinks.append(a['href'])
validation={'report_sha256':sha(root/'report.md'),'source_sha256':sha(s['source_pdf']),'physical_page_count':len(doc),'page_markers':markers,'markers_complete_ordered_once':markers==list(range(1,44)),'missing_images':missing,'broken_internal_anchors':badlinks,'table_count':len(soup.find_all('table')),'image_count':len(soup.find_all('img')),'unresolved_controls':[hex(ord(c)) for c in set(report) if ord(c)<32 and c not in '\n\r\t'],'checked_pages':sorted(checked),'pending_pages':[n for n in range(1,44) if n not in checked],'browser_render':'failed: Chrome headless SIGABRT; report.html generated; no browser screenshots','fallback_render':'PyMuPDF Story snapshots: cover widths 1440/390, tables pages 18/19/23/27/39/40; inspected. Not equivalent to browser rendering.'}
(checks/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
coverage=json.load(open(checks/'initial_native_coverage.json'));coverage['scope']='Original mechanical candidate glyph accounting only; not a proof of final report fidelity. See initial_native_coverage.json, region_accounting.json, pages.json and validation.json.';coverage['original_candidate_report_sha256']=coverage.pop('report_sha256');coverage['final_report_sha256']=sha(root/'report.md');coverage['review_status']='converted';coverage['semantic_source_review_completed']=False;coverage['pending_pages']=validation['pending_pages']
(checks/'native_coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n')
assert validation['markers_complete_ordered_once'] and not missing and not badlinks and not validation['unresolved_controls']
print(json.dumps(validation,ensure_ascii=False))
