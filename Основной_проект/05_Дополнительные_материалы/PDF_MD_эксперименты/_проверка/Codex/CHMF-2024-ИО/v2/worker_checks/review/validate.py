import sys,pathlib,json,re,hashlib,collections,unicodedata
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
import pymupdf
root=pathlib.Path('result');checks=root/'_проверка';s=(root/'report.md').read_text(); pdf=pymupdf.open(json.load(open('source.json'))['source_pdf'])
rendered=MarkdownIt('commonmark',{'html':True}).render(s)
soup=BeautifulSoup(rendered,'html.parser');badlinks=[];anchors={t.get('id') for t in soup.find_all(id=True)}
for t in soup.find_all(['img','a']):
 v=t.get('src') if t.name=='img' else t.get('href','')
 if t.name=='a' and not t.has_attr('href'):continue
 if not v:badlinks.append(str(t)[:100]);continue
 if v.startswith('#'):
  if v[1:] not in anchors:badlinks.append(v)
 elif not re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:',v) and not (root/v).exists():badlinks.append(v)
markers=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',s)))
base=json.load(open(checks/'pages.native.json'));covers=[1,4,7,13,16,35,43,53,83,122];unicode_pages=[];diagnostics=[]
log=json.load(open(checks/'corrections.json'));by_page=collections.defaultdict(list)
for item in log:by_page[item['pdf_page']].append(item)
for r in base['pages']:
 n=r['pdf_page'];original_issues=r['issues'][:];r['native_diagnostic_issues']=original_issues
 r['conversion_status']='converted';r['review_status']='checked' if n in covers else 'pending';r['semantic_source_review_completed']=n in covers
 r['verification_scope']='Полная визуальная сверка обложки/разделителя' if n in covers else 'Механическая конвертация; визуальная проверка отдельных объектов, если перечислены; полная сверка не выполнена'
 r['issues']=[] if n in covers else ['Полная сверка текста, порядка чтения, таблиц, сносок и ссылок по оригиналу не завершена.']
 r['content_type']='cover' if n==1 else 'section_divider' if n in covers else 'mixed_raster_and_native' if 141<=n<=146 else 'native_text_tables_graphics' if r['tables'] else 'native_text_and_graphics'
 r['source_image']=f'assets/page_{n:04d}.png'
 r['corrections']=by_page[n]
 words=pdf[n-1].get_text('words');r['printed_designation']=[{'text':w[4],'bbox':list(w[:4]),'status':'extracted_from_footer_not_visually_verified' if n not in covers else 'visually_checked'} for w in words if w[1]>pdf[n-1].rect.height-52 and (w[0]<45 or w[0]>pdf[n-1].rect.width-45) and re.fullmatch(r'\d{1,3}',w[4])]
 if r.get('unresolved_unicode'):
  unicode_pages.append(n);r['unicode_normalization']={'status':'class_verified_with_page_samples','remaining_unresolved_unicode':0,'scope':'Не проверены все вхождения; классы шрифтов проверены по исходным фрагментам на каждой затронутой странице.'}
 if n==9:r['issues'].append('Восстановленные таблицы и легенда сверены по изображению; полная проверка отображения и всех связей страницы отдельно от этой правки не означает checked всей страницы.')
 if 141<=n<=146:r['ocr_engine']='local Tesseract rus+eng, 3x, separate spread sides, no confidence filtering';r['ocr_verified']=False;r['issues'].append('Текст сканированного тела извлечён OCR; пословная сверка, знаки, реквизиты и структура требуют проверки.');r['ocr_review_files']=[str(p.relative_to(root)) for p in sorted((checks/'review').glob(f'ocr_{n}_*.txt'))]
 if r.get('unresolved_source_links'):r['issues'].append('Некорректные/неоднозначные назначения PDF-ссылок сохранены в диагностике; назначение по номеру страницы не угадывалось.')
 if r.get('tables') and n not in covers:r['issues'].append('Не все ячейки и объединения таблиц сверены по оригиналу; полнота глифов не подтверждает структуру.')
 for issue in original_issues:
  diagnostics.append({'pdf_page':n,'diagnostic':issue,'examined':True,'disposition':'class_normalized_partial_visual_review' if 'font mapping' in issue else 'reconstructed_table_partial_page_review' if 'ambiguous table' in issue else 'divider_visually_checked' if n in covers else 'ocr_reprocessed_pending_word_review' if 141<=n<=146 else 'source_link_pending' if 'link destinations' in issue else 'native_body_retained_ocr_noise_removed_pending_full_review','evidence':[x['basis'] for x in by_page[n]]})
base['summary']={'physical_pages':167,'converted':167,'checked':len(covers),'review_pending':167-len(covers),'checked_pages':covers,'all_pages_accounted_once_in_order':markers==list(range(1,168)),'full_document_source_review_completed':False,'report_sha256':hashlib.sha256(s.encode()).hexdigest()}
(checks/'pages.json').write_text(json.dumps(base,ensure_ascii=False,indent=2)+'\n')
(checks/'diagnostic_review.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2)+'\n')
validation={'source_sha256':hashlib.sha256(pathlib.Path(json.load(open('source.json'))['source_pdf']).read_bytes()).hexdigest(),'physical_pages':len(pdf),'markers_correct':markers==list(range(1,168)),'local_links_and_anchors_missing':badlinks,'rendered_tables':len(soup.find_all('table')),'images':len(soup.find_all('img')),'remaining_bad_unicode':dict(collections.Counter(c for c in s if c=='�' or unicodedata.category(c) in ['Co','Cs'] or (unicodedata.category(c)=='Cc' and not c.isspace()))),'baseline_report_sha256':hashlib.sha256((checks/'report.native.md').read_bytes()).hexdigest(),'final_report_sha256':hashlib.sha256(s.encode()).hexdigest(),'scope':'Структурная проверка; не подтверждает точность содержания.'}
(checks/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
style='<style>body{font:16px/1.5 Arial;max-width:1200px;margin:30px auto;padding:20px}table{border-collapse:collapse;display:block;overflow-x:auto;max-width:100%;margin:20px 0}td,th{border:1px solid #aaa;padding:8px;min-width:55px}img{max-width:100%;height:auto}details{border:1px solid #ccc;padding:10px}blockquote{background:#f5f5f5;padding:10px}</style>'
html='<!doctype html><html lang="ru"><meta charset="utf-8">'+style+'<body>'+rendered.replace('src="assets/','loading="lazy" src="../assets/')+'</body></html>'
(checks/'report.preview.html').write_text(html)
# Compact addressed sample for actual visual rendering of changed objects.
p9=re.search(r'<!-- pdf_page: 9 -->.*?(?=<!-- pdf_page: 10 -->)',s,re.S).group();p9=p9[:p9.index('> Служебная информация: ссылки')]
(checks/'review/page9.preview.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8">'+style+'<body>'+MarkdownIt('commonmark',{'html':True}).render(p9).replace('src="assets/','src="../../assets/')+'</body></html>')
print(json.dumps(validation,ensure_ascii=False));print(base['summary'])
