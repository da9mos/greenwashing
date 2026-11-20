from pathlib import Path
import sys,json,re,hashlib,collections
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1];source=json.loads((root.parent/'source.json').read_text());doc=pymupdf.open(source['source_pdf']);s=(root/'report.md').read_text()
checked={1,2,60,104,188,190};graphs={8,9,10,11,16,17,18,77,89,107,108,109,111,112,113,115,116,117,118,128,129,131}
raw=json.loads((root/'_проверка/session_input/pages.native.json').read_text());changes=json.loads((root/'_проверка/corrections.json').read_text())
by_page=collections.defaultdict(list)
for i,c in enumerate(changes):by_page[c['pdf_page']].append(i)
for n in range(1,191):
 if n not in checked:
  note='> Служебная пометка: converted/pending — полная сверка содержания и связей по оригиналу не завершена.'
  if n in graphs:note+=' Принадлежность значений диаграмм и элементов схем категориям требует отдельной проверки по изображению.'
  anchor=f'<a id="pdf-page-{n}"></a>';s=s.replace(anchor,anchor+'\n\n'+note,1)
(root/'report.md').write_text(s)
for item in raw['pages']:
 n=item['pdf_page'];page=doc[n-1]
 item['original_diagnostics']={k:item.get(k) for k in ['issues','unresolved_unicode','ambiguous_cell_assignments','ocr_chars','ocr_verified']}
 item['conversion_status']='converted';item['review_status']='checked' if n in checked else 'pending'
 item['semantic_source_review_completed']=n in checked
 item['verification_scope']='Полное визуальное чтение страницы и сверка перенесённого текста/таблиц' if n in checked else 'Обзор макета исходной страницы; диагностические записи рассмотрены; полная пословная/поячеечная сверка не выполнена'
 item['source_image_review']='full_content' if n in checked else 'layout_overview'
 item['image_path']=f'assets/page_{n:04}.png'
 item['content_type']='image_cover_with_visual_transcription' if n==1 else 'native_text_with_graphics' if page.get_images() else 'native_text_and_vector_layout'
 nums=[]
 for b in page.get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   t=''.join(sp['text'] for sp in l['spans']).strip()
   if l['bbox'][1]>550 and t.isdigit() and len(t)<4:nums.append(t)
 item['printed_page_labels']=list(dict.fromkeys(nums))
 item['printed_page_label_basis']='Прямое извлечение из нижнего колонтитула; при отсутствии не вычислялось по смещению.'
 item['issues']=[] if n in checked else ['Полная сверка текста, порядка чтения, таблиц, сносок и связей графики по оригиналу не завершена.']
 if n in graphs:item['issues'].append('Связи извлечённых значений диаграмм/схем с категориями и рядами требуют проверки; изображение сохранено.')
 item['unresolved_unicode']=0
 item['ambiguous_cell_assignments']=[]
 if item.get('ocr_chars') is not None:
  item['ocr_main_text_disposition']='Заменён визуальной транскрипцией' if n in [1,190] else 'Дополнительный OCR исключён как дубли/артефакты; исходный текстовый слой сохранён. Сырой OCR в session_input/report.native.md.'
  item['ocr_verified']=n in [1,190]
 item['correction_indices']=by_page[n]
 item['baseline_inventory_scope']='Поля native_glyphs/all_native_glyphs_assigned_once/rendered_native_character_inventory_matches/objects описывают исходного механического кандидата; не являются подтверждением итогового порядка или полной сверки.'
(root/'_проверка/pages.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2))
# Integrity audit of the actual saved report.
md=MarkdownIt('commonmark',{'html':True}).enable('table');soup=BeautifulSoup(md.render(s),'html.parser')
markers=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',s)));assert markers==list(range(1,191))
anchors={a['id'] for a in soup.find_all(id=True)};missing=[];local=[]
for tag,attr in [('a','href'),('img','src')]:
 for el in soup.find_all(tag):
  target=el.get(attr,'')
  if target.startswith('#'):
   if target[1:] not in anchors:missing.append(target)
  elif target and not re.match(r'^[a-z]+:',target):
   local.append(target)
   if not (root/target).is_file():missing.append(target)
assert not missing,missing
assert '\x07' not in s and '\ufffd' not in s
index=json.loads(Path(source['index']).read_text());asset_mismatch=[]
for x in index['pages']:
 path=root/f"assets/page_{x['pdf_page']:04}.png"
 if hashlib.sha256(path.read_bytes()).hexdigest()!=x['image_sha256']:asset_mismatch.append(x['pdf_page'])
assert not asset_mismatch
sha=hashlib.sha256(Path(source['source_pdf']).read_bytes()).hexdigest();assert sha==index['source_sha256']
audit={'source_pdf':source['source_pdf'],'source_sha256':sha,'physical_pages':len(doc),'report_sha256':hashlib.sha256(s.encode()).hexdigest(),'page_markers_in_source_order':markers==list(range(1,191)),'local_assets_referenced':len(local),'missing_local_targets':missing,'source_images_hash_verified':190,'tables_rendered':len(soup.find_all('table')),'fully_reviewed_pages':sorted(checked),'layout_overview_pages':190,'pending_full_review_pages':[n for n in range(1,191) if n not in checked],'all_native_body_scanned_pages_with_no_text':[1],'whole_document_semantic_review_completed':False,'rendering':'HTML получен локально; контрольные фрагменты 1,2,3,60,104,188 отрендерены PyMuPDF Story. Браузер Chrome завершился SIGABRT; браузерное отображение и отображение всего документа не проверены.'}
(root/'_проверка/final_integrity.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
cov=json.loads((root/'_проверка/session_input/native_coverage.json').read_text());cov['scope']='Только исходный механический кандидат до адресных исправлений; не финальная визуальная проверка';cov['native_candidate_report_sha256']=cov.pop('report_sha256');cov['native_candidate_report']='session_input/report.native.md';cov['final_report_sha256']=audit['report_sha256'];cov['final_integrity']='final_integrity.json';cov['review_status']='pending';cov['pending_pages']=audit['pending_full_review_pages'];cov['fully_reviewed_pages']=sorted(checked);(root/'_проверка/native_coverage.json').write_text(json.dumps(cov,ensure_ascii=False,indent=2))
print(json.dumps({k:audit[k] for k in ['physical_pages','tables_rendered','source_images_hash_verified','fully_reviewed_pages','missing_local_targets']},ensure_ascii=False))
