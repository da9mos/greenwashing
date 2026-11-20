import sys,re,json,hashlib,collections
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
import fitz
r=Path(__file__).resolve().parents[1];src=json.load(open(r.parent/'source.json'));d=fitz.open(src['source_pdf'])
report=(r/'report.md').read_text();parts=re.split(r'<!-- pdf_page: \d+ -->',report)[1:]
base=json.load(open(r/'_проверка/baseline/pages.json'))['pages'];td=json.load(open(r/'_проверка/table_diagnostics.json'));changes=json.load(open(r/'_проверка/corrections.json'))
checked={1,11,26};full_body={1,4,11,13,19,21,26,27,43,58,62};ocr={1,4,19,21,26,27,43,58}
# Fix scope notes on pages whose body was inspected but annotations remain pending.
for n in [4,13,19,21,27,43,58]:
 t=parts[n-1]
 if '> Техническая пометка: converted / pending' not in t:
  note='> Техническая пометка: converted / pending — тело страницы сверено по изображению; полная проверка аннотаций и отображения страницы не завершена.\n\n'
  t=t.replace(f'<a id="pdf-page-{n}"></a>\n\n',f'<a id="pdf-page-{n}"></a>\n\n'+note)
  parts[n-1]=t
# Surface table diagnostics beside the actual tables rather than hide them in a log.
for n in sorted({x['pdf_page'] for x in td}):
 t=parts[n-1];count=sum(x['pdf_page']==n for x in td)
 note=f'> Техническая пометка о таблицах: {count} объект(а) с пустыми ячейками/дорожками сетки либо несколькими годами в одной ячейке. Эти структуры требуют сверки строк и столбцов по изображению ниже; семантическая точность не подтверждена.\n\n'
 t=t.replace('> Служебная информация: ссылки исходного PDF',note+'> Служебная информация: ссылки исходного PDF')
 parts[n-1]=t
report=report.split('<!-- pdf_page: 1 -->')[0]+''.join(f'<!-- pdf_page: {n} -->'+t for n,t in enumerate(parts,1));(r/'report.md').write_text(report)
registry=[];diagnostics=[]
for n,(old,t,pdfp) in enumerate(zip(base,parts,d),1):
 header=[]
 for b in pdfp.get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   if l['bbox'][1]<45:
    txt=''.join(s['text'] for s in l['spans']).strip()
    if re.fullmatch(r'\d{1,3}',txt):header.append((l['bbox'][0],txt))
 printed=[x[1] for x in sorted(header)]
 issues=[]
 if n not in checked:issues.append('Полная построчная сверка страницы, всех связей и отображения не завершена; review_status=pending.')
 flags=[x for x in td if x['pdf_page']==n]
 if flags:issues.append('Табличная структура требует сверки: '+', '.join(str(x['table']) for x in flags)+'. Пустые ячейки не являются автоматически ошибками; возможны лишние дорожки и объединенные периоды.')
 if '#pdf-page-1"' in t:issues.append('PDF содержит назначения nameddest=p0 на обложку при иных видимых подписях; оригинальные назначения сохранены, смысл не подтвержден.')
 if n==62:issues.append('В оригинале итоги отпуска за 2022/2021 отображаются как 2 / 713. Сохранены видимые подписи; расчетное восстановление не выполнялось.')
 if n not in full_body:scope='Просмотр общего устройства страницы в контактном листе; полная сверка текста/данных не выполнена.'
 else:scope='Визуально прочитано тело страницы по полному исходному изображению; исправленные объекты сопоставлены с текстом.'
 if old.get('unresolved_unicode'):scope+=' Все поврежденные управляющие символы просмотрены в исходных PDF-кропах.'
 registry.append({'pdf_page':n,'printed_designations':printed,'content_type':'native_text_with_graphics'+('_spread' if pdfp.rect.width>pdfp.rect.height else ''),'conversion_status':'converted','review_status':'checked' if n in checked else 'pending','semantic_source_review_completed':n in checked,'review_scope':scope,'issues':issues,'corrected_objects':[x['correction'] for x in changes if x['pdf_page']==n],'native_candidate_metrics':{k:v for k,v in old.items() if k not in ['pdf_page','conversion_status','review_status','semantic_source_review_completed','issues','verification_scope']}})
 if old['issues'] or flags:
  diagnostics.append({'pdf_page':n,'initial_issues':old['issues'],'unicode_region_review':'inspected and repaired' if old.get('unresolved_unicode') else 'not flagged','ocr_region_review':'inspected; native body retained; noise removed or cover text added' if n in ocr else 'not flagged','ambiguous_cell_assignments_review':'none recorded in native candidate' if not old.get('ambiguous_cell_assignments') else 'pending','table_structure_review':'pending' if flags else ('corrected selected objects' if n in [4,11,13,26,35,62] else 'not a full table review'),'whole_page_status':'checked' if n in checked else 'pending'})
(r/'_проверка/pages.json').write_text(json.dumps({'pages':registry},ensure_ascii=False,indent=2))
(r/'_проверка/diagnostic_review.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2))
# Integrity checks of the final saved file.
nums=[int(x) for x in re.findall(r'<!-- pdf_page: (\d+) -->',report)];assert nums==list(range(1,71))
assets=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',report);missing=[x for x in assets if not (r/x).is_file()];assert not missing
soup=BeautifulSoup(report,'html.parser');ids={x.get('id') for x in soup.find_all(id=True)}
bad=[a['href'] for a in soup.find_all('a',href=True) if a['href'].startswith('#') and a['href'][1:] not in ids];assert not bad
assert not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',report)
source_hash=hashlib.sha256(Path(src['source_pdf']).read_bytes()).hexdigest();native=json.load(open(r/'_проверка/native_coverage.json'));assert source_hash==native['source_sha256']
verification={'source_sha256':source_hash,'physical_pages':len(d),'page_markers_ordered_once':True,'all_70_pages_have_text':all(len(BeautifulSoup(x.split('<details>')[0],'html.parser').get_text(strip=True))>20 for x in parts),'local_image_references':len(assets),'missing_assets':missing,'broken_internal_anchors':bad,'report_sha256':hashlib.sha256(report.encode()).hexdigest(),'review_checked_pages':sorted(checked),'review_pending_pages':[n for n in nums if n not in checked],'full_body_image_read_pages':sorted(full_body),'partial_graph_review_pages':[35],'table_diagnostic_objects_pending':len(td),'rendering':'Selected corrected bodies rendered with PyMuPDF Story; browser headless launch failed with exit 134. Full Markdown HTML preview saved; full-document display not checked.','native_coverage_scope':'native_coverage.json describes baseline only; corrections remove duplicate/noise glyphs, so original report hash is not current.'}
(r/'_проверка/validation.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in verification.items() if not k.startswith('review_pending')},ensure_ascii=False,indent=2))
