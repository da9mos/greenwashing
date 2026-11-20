import sys,json,re,hashlib,pathlib,collections,zipfile
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
import pymupdf
root=pathlib.Path('result');a=root/'_проверка';s=(root/'report.md').read_text();meta=json.load(open('source.json'));d=pymupdf.open(meta['source_pdf']);reg=json.load(open(a/'pages.json'));index=json.load(open(meta['index']));diag=[p['pdf_page'] for p in reg['pages'] if p['issues']]
checked={1,2,18,47,52,54,57,62,89,99,118,165,170,174,183}
changes=json.load(open(a/'corrections.json'));changed={x['pdf_page'] for x in changes if x['object']=='body'}
parts=re.split(r'<!-- pdf_page: (\d+) -->',s);P={int(parts[i]):parts[i+1] for i in range(1,len(parts),2)}
for p in reg['pages']:
 n=p['pdf_page'];p['original_diagnostics']=p['issues'];p['conversion_status']='converted';p['review_status']='checked' if n in checked else 'pending';p['semantic_source_review_completed']=n in checked
 p['verification_scope']='Source body, tables/charts and reading order reviewed; navigation artwork retained in source image.' if n in checked else ('Diagnostic image inspected for structure/OCR residuals; full text/cell-by-cell review not completed.' if n in diag else 'Mechanical native-glyph coverage only; source-content and reading-order review pending.')
 p['source_image_inspection']='full_body' if n in checked else ('structural_overview' if n in diag else 'not_reviewed')
 p['issues']=[] if n in checked else ['Полная сверка текста, порядка чтения, примечаний и связей по оригиналу не завершена.']
 if p.get('tables') and n not in checked:p['issues'].append('Геометрия таблиц требует сверки: возможны слияния самостоятельных таблиц, строк или колонок; полный учёт символов этого не исключает.')
 p['content_type']='native_text_with_graphics_and_tables' if p.get('tables') else 'native_text_with_graphics';p['source_image']=f'assets/page_{n:04}.png'
 nums=[w[4] for w in d[n-1].get_text('words') if w[0]>1590 and w[1]<80 and re.fullmatch(r'\d+',w[4])];p['printed_labels']=nums;p['printed_label_basis']='Text-layer tokens in upper-right page-number area; no offset inferred.'
 p['corrections']=[i for i,x in enumerate(changes) if x['pdf_page']==n]
 if n in changed:p['native_accounting_after_repair']='Native coverage in original candidate is historical; addressed source regions copied by review_repairs.py. Changed layout does not retain original glyph IDs.'
 if n==2:p['original_unresolved_unicode']=p['unresolved_unicode'];p['unresolved_unicode']=0
 if p.get('ocr_chars') is not None:p['ocr_residual_disposition']='Removed supplemental OCR residual after structural inspection; source text layer retained. Original OCR is in corrections.json and native_before_review.zip.';p['ocr_verified']=False
 if n not in checked:
  note='> Служебная пометка: converted / pending — полная сверка этой страницы по оригиналу не завершена.'
  if p.get('tables'):note+=' Структура таблиц требует проверки; возможны слияния строк и колонок.'
  P[n]=P[n].replace(f'<a id="pdf-page-{n}"></a>',f'<a id="pdf-page-{n}"></a>\n\n{note}',1)
reg['review_summary']={'physical_pages':204,'conversion_status':'converted','checked_pages':sorted(checked),'pending_pages':sorted(set(range(1,205))-checked),'diagnostic_pages_structurally_inspected':diag,'full_document_semantic_review_completed':False,'external_models_or_api_used':False,'basis':'Supplied local mechanical candidate plus original PDF glyphs and source images. No old/model transcriptions consulted.'}
(a/'pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n')
s=parts[0]+''.join(f'<!-- pdf_page: {n} -->'+P[n] for n in range(1,205));(root/'report.md').write_text(s)
md=MarkdownIt('commonmark',{'html':True});rendered=md.render(s);soup=BeautifulSoup(rendered,'html.parser')
markers=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',s)));assert markers==list(range(1,205))
ids={t.get('id') for t in soup.find_all(id=True)};badanchors=[];badfiles=[]
for el in soup.find_all(['a','img']):
 target=el.get('href') if el.name=='a' else el.get('src')
 if not target:continue
 if target.startswith('#'):
  if target[1:] not in ids:badanchors.append(target)
 elif not re.match(r'^[a-zA-Z]+:',target) and not (root/target).is_file():badfiles.append(target)
assert not badanchors and not badfiles,(badanchors,badfiles)
asset_checks=[]
for p in index['pages']:
 n=p['pdf_page'];asset=root/f'assets/page_{n:04}.png';h=hashlib.sha256(asset.read_bytes()).hexdigest();assert h==p['image_sha256'];asset_checks.append({'pdf_page':n,'sha256':h,'matches_source_index':True})
control=[(ord(c),i) for i,c in enumerate(s) if ord(c)<32 and c not in '\n\r\t'];assert not control
assert '\ufffd' not in s
# Copy-pasted native numbers in repaired tables must remain equal to the source glyph inventory.
with zipfile.ZipFile(a/'native_before_review.zip') as z:oldcov=json.loads(z.read('_проверка/native_coverage.json'))
cov=dict(oldcov);cov['original_candidate_report_sha256']=cov.pop('report_sha256');cov['report_sha256']=hashlib.sha256(s.encode()).hexdigest();cov['semantic_source_review_completed']=False;cov['review_status']='pending';cov['checked_pages']=sorted(checked);cov['pending_pages']=sorted(set(range(1,205))-checked);cov['scope']='Original candidate: all native glyphs assigned once. Current result: addressed source repairs; only listed pages semantically reviewed. This is not a full-fidelity certificate.';cov['native_glyph_accounting_applies_to']='native_before_review.zip/report.md'
(a/'native_coverage.json').write_text(json.dumps(cov,ensure_ascii=False,indent=2)+'\n')
checks={'physical_pages':204,'page_markers_unique_and_ordered':True,'local_links_valid':True,'broken_local_links':badfiles,'broken_internal_targets':badanchors,'assets_match_all_204_source_hashes':True,'replacement_characters':s.count('\ufffd'),'unexpected_control_characters':len(control),'report_sha256':cov['report_sha256'],'source_pdf_sha256':hashlib.sha256(pathlib.Path(meta['source_pdf']).read_bytes()).hexdigest(),'source_page_count':len(d),'rendering':'HTML generated; visual rendering check recorded separately.','full_semantic_review':False}
(a/'assembly_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
(a/'asset_checks.json').write_text(json.dumps(asset_checks,ensure_ascii=False,indent=2)+'\n')
css='body{font:16px/1.5 Arial,sans-serif;max-width:1280px;margin:32px auto;padding:20px;color:#222}table{border-collapse:collapse;max-width:100%;margin:20px 0}td,th{border:1px solid #aaa;padding:7px;vertical-align:top}img{max-width:100%}blockquote{background:#f5f5f5;padding:12px} .table-wrap{overflow-x:auto}'
for t in soup.find_all('table'):
 wrapper=soup.new_tag('div',attrs={'class':'table-wrap'});t.wrap(wrapper)
(a/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>Проверка Markdown</title><style>'+css+'</style>'+str(soup).replace('src="assets/','src="../assets/'))
# Separate page views use exactly the saved report segments.
for n in sorted(checked):
 (a/f'preview_{n:04}.html').write_text('<!doctype html><meta charset="utf-8"><style>'+css+'</style>'+md.render(P[n].split('> Служебная информация: ссылки')[0].split('<details>')[0]))
print(json.dumps(checks,ensure_ascii=False));print('checked',len(checked),'pending',204-len(checked))
