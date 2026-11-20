import sys,json,re,hashlib,pathlib,collections,urllib.parse
sys.path.insert(0,'/private/tmp/sber-pdf-libs');sys.path.insert(0,'/private/tmp/sber-diff-libs')
import pymupdf as f
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
root=pathlib.Path(__file__).resolve().parents[3];res=root/'result';audit=res/'_проверка';source=json.loads((root/'source.json').read_text());pdf=f.open(source['source_pdf'])
hashpdf=hashlib.sha256(pathlib.Path(source['source_pdf']).read_bytes()).hexdigest();baseline=json.loads((audit/'native_coverage.json').read_text());assert hashpdf==baseline['source_sha256'];assert len(pdf)==139
s=(res/'report.md').read_text();pages=json.loads((audit/'pages.before-review.json').read_text())['pages'];checked={1,2,3,16,46,85,108};partial={29,51,83,84,115,116,118,119,125};structure={22,111,112,114,117,123,128,136};overview={30,52,56,58,73,80,95,100,105,107,139}
# Explicitly expose remaining uncertainty next to the affected source representation.
for n in sorted(structure):
 msg=('Диаграммы: текстовый слой сохранен, но соответствие всех значений рядам, категориям и периодам еще не подтверждено; ложная табличная сетка механического переноса не считается проверенной.' if n==22 else 'Структура таблиц/схемы требует дальнейшей сверки: механическая сетка может содержать лишние столбцы или разбиение одной ячейки на несколько строк. Текстовый слой сохранен; исходная страница доступна ниже.')
 pattern=r'(<!-- pdf_page: '+str(n)+r' -->\n<a id="pdf-page-'+str(n)+r'"></a>\n)';s=re.sub(pattern,lambda m:m[1]+'\n> Служебная пометка, pending: '+msg+'\n',s)
(res/'report.md').write_text(s)
for a in pages:
 n=a['pdf_page'];a['initial_diagnostics']=a['issues'];a['conversion_status']='converted';a['review_status']='checked' if n in checked else 'pending';a['semantic_source_review_completed']=n in checked;a['render_status']='pending';a['issues']=[] if n in checked else ['Полная построчная сверка содержания, порядка чтения и связей по оригиналу не выполнена.']
 a['source_image']=f'assets/page_{n:04}.png';a['source_image_inspected']=n in checked|partial|structure|overview
 a['verification_scope']=('Визуально сверены все основные надписи; декоративный фон сохранен изображением, колонтитулы исключены как навигация.' if n in checked else 'Механический перенос исходных глифов. Полная визуальная сверка страницы pending.')
 if n in partial:a['verification_scope']+=' Просмотрено исходное изображение диагностического участка; подробности в review_log.md. Это не проверка всей страницы.'
 if n in structure:a['issues'].append('Просмотрена структура; требуется исправление/подтверждение лишних столбцов, строк и связей значений. Пометка включена в report.md.')
 if n in overview:a['verification_scope']+=' Просмотрен обзор страницы в контактном листе; детали не сверены.'
 if n in {29,51,83,84}:a['resolved_diagnostics']=['Удален дублирующий OCR-фрагмент и шум рисунка; исходный текстовый слой сохранен.'];a['ocr_disposition']='removed duplicate/noise after visual inspection'
 if n in {115,116,118,119,125}:a['resolved_diagnostics']=['Исправлены строки и объединения по исходным линейкам PDF; состав исходных непробельных глифов сохранен, кроме U+0007 на странице 125.'];a['issues'].append('Связи внутренних ссылок и все значения страницы целиком не сверены; таблицы исправлены адресно.')
 if n in checked:a['resolved_diagnostics']=['Восстановлены основные надписи по изображению; удалена ложная сетка декоративного фона.']
 if n==125:a['resolved_diagnostics'].append('Удален U+0007 в заголовке раздела VI: на изображении соответствующий знак отсутствует.')
 # Printed numbering comes from explicit page text; never calculated by offset.
 text=pdf[n-1].get_text();labels=re.findall(r'(?m)^\s*(\d{1,3})\s*\|\s*(\d{1,3})\s*$',text);a['printed_designations']=[' | '.join(t) for t in labels];a['printed_designation_status']='read_from_native_footer' if labels else 'not_established'
 a['content_type']=['native_text','graphics']+(['table'] if a['tables'] else []);a['content_type_basis']='native diagnostics; raster/text-body completeness not fully visually verified'
(audit/'pages.json').write_text(json.dumps({'source_sha256':hashpdf,'page_count':139,'status_definitions':{'conversion_status':'Извлечение содержания','review_status':'Сверка всей страницы по оригиналу','render_status':'Отображение выдаваемой страницы в браузере'},'pages':pages},ensure_ascii=False,indent=2)+'\n')
# Validate the issued version, including actual Markdown-rendered image and anchor targets.
html=MarkdownIt('commonmark',{'html':True}).enable('table').render(s);soup=BeautifulSoup(html,'html.parser');marks=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',s)));assert marks==list(range(1,140));ids=[x['id'] for x in soup.find_all(id=True)];assert len(ids)==len(set(ids))
missing=[];bad=[]
for im in soup.find_all('img'):
 target=res/urllib.parse.unquote(im['src']);
 if not target.is_file():missing.append(im['src'])
for a in soup.find_all('a',href=True):
 h=a['href']
 if h.startswith('#') and h[1:] not in ids:bad.append(h)
assert not missing and not bad,(missing,bad)
report_hash=hashlib.sha256((res/'report.md').read_bytes()).hexdigest()
result={'source_sha256':hashpdf,'report_sha256':report_hash,'physical_pages':139,'page_markers_in_order':True,'unique_page_anchors':len([v for v in ids if v.startswith('pdf-page-')]),'image_references':len(soup.find_all('img')),'missing_assets':missing,'broken_internal_targets':bad,'source_checked_pages':sorted(checked),'source_partially_reviewed_pages':sorted(partial),'structure_inspected_pending':sorted(structure),'browser_render_status':'pending: Chrome launch failed (SIGABRT/EPERM)','alternative_render':'MuPDF Story, selected tables 115/119/125; selected first-page snapshots inspected. Not a whole-document browser check.','native_coverage_scope':'native_coverage.json and report.before-review.md describe initial mechanical candidate, not the edited issued report.'}
(audit/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
(audit/'render/render_check.json').write_text(json.dumps({'report_sha256':report_hash,'status':'pending','error':'Chrome launch TargetClosedError; SIGABRT, kill EPERM','screenshots_1440_390_created':False,'scope':'HTML generated; browser rendering not completed'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
