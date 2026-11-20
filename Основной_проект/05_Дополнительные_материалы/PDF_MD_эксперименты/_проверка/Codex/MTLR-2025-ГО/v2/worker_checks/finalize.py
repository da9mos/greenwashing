from pathlib import Path
import re,json,hashlib,fitz
R=Path('result');p=R/'report.md';s=p.read_text();src=json.load(open('source.json'));D=fitz.open(src['source_pdf'])
checked={1,2,7,23,50,67}
viewed={1,2,4,5,7,10,12,18,19,20,21,22,23,50,53,56,57,58,59,61,62,64,66,67}
parts=re.split(r'<!-- pdf_page: (\d+) -->',s)
header_strings=['ГОДОВОЙ ОТЧЕТ 2025','СТРАТЕГИЧЕСКИЙ ОТЧЁТ','КОРПОРАТИВНОЕ УПРАВЛЕНИЕ','ПРИЛОЖЕНИЯ','ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ','www.mechel.ru']
for i in range(1,len(parts),2):
 n=int(parts[i]);t=parts[i+1]
 # Remove repetitive navigation only if corresponding source text is in header/footer band.
 if n not in [1,2,4,23,50,67]:
  native=[(''.join(z['text'] for z in l['spans']).strip(),l['bbox'][1]) for b in D[n-1].get_text('dict')['blocks'] for l in b.get('lines',[])]
  for text in header_strings:
   count=sum(a==text and (y<40 or y>635) for a,y in native)
   for _ in range(count):t=t.replace('<p>'+text+'</p>\n\n','',1)
  # page footer is separate from body; never remove in-table page-like numbers
  footer=[a for a,y in native if y>635 and a.isdigit()]
  for num in footer:
   pat='<p>'+num+'</p>'; pos=t.rfind(pat)
   if pos>=0:t=t[:pos]+t[pos+len(pat):]
 if n not in checked:
  note='> Служебная пометка: содержание страницы конвертировано; полная сверка текста, порядка чтения и связей по оригиналу остаётся pending.\n\n'
  t=t.replace('<details>',note+'<details>',1)
 # Actual annotation destinations retained, including source inconsistencies.
 t=re.sub(r'> Служебная информация: ссылки исходного PDF\n\n(.*?)(?=<details>|> Служебная пометка: содержание)',r'<details>\n<summary>Служебная информация: ссылки исходного PDF</summary>\n\n\1</details>\n\n',t,flags=re.S)
 parts[i+1]=t
p.write_text(parts[0]+''.join('<!-- pdf_page: '+parts[i]+' -->'+parts[i+1] for i in range(1,len(parts),2)))
reg=json.load(open(R/'_проверка/pages.json'));allp=[]
for x in reg['pages']:
 n=x['pdf_page'];x['original_diagnostics']=x['issues'];x['issues']=[]
 x['conversion_status']='converted';x['review_status']='checked' if n in checked else 'pending'
 x['semantic_source_review_completed']=n in checked
 x['verification_scope']='Полная сверка содержательной обложки/разделителя/оглавления/карты с исходным изображением' if n in checked else 'Механический перенос; полная семантическая сверка страницы не завершена'
 x['source_image_layout_viewed']=n in viewed or 53<=n<=66
 x['printed_page_labels']=[ ''.join(z['text'] for z in l['spans']).strip() for b in D[n-1].get_text('dict')['blocks'] for l in b.get('lines',[]) if l['bbox'][1]>635 and ''.join(z['text'] for z in l['spans']).strip().isdigit() ]
 x['content_type']='native_text_with_graphics'
 if n in [1,4,23,50,67]:x['content_type']='illustrated_cover_or_divider_with_native_title'
 if 53<=n<=66:
  x['content_type']='two_independent_five_column_tables';x['checkbox_review_status']='checked';x['issues'].append('Структура строк и столбцов исправлена; все 78 состояний отметок приложения проверены по вырезкам оригинала. Полная вычитка текста всех ячеек остаётся pending.')
 if n not in checked:x['issues'].append('Полная сверка содержимого и порядка чтения страницы по оригиналу не завершена.')
 x['issues'].append('Отображение итогового Markdown в Chrome не проверено: процесс браузера аварийно завершился при запуске; HTML сформирован, снимки не получены.')
 if n==7:x['ocr_verified']=True;x['content_type']='native_text_and_raster_map';x['verification_scope']='Текст вступления, все подписи карты и легенда прочитаны по исходному изображению; карта сохранена'
 if n in [64,66]:x['ambiguous_cell_resolution']='Исходная неоднозначность относится к пробелу в строке объединённой шапки. Таблицы перестроены по исходным строкам и независимым половинам.'
 allp.append(x)
reg['pages']=allp;reg['source_sha256']=hashlib.sha256(Path(src['source_pdf']).read_bytes()).hexdigest();reg['document_review_status']='pending';reg['render_status']='blocked_browser_launch';reg['checked_pages']=sorted(checked)
(R/'_проверка/pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2))
# Integrity of final saved output and all local references.
s=p.read_text();marks=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',s)));assert marks==list(range(1,70))
refs=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',s);missing=[r for r in refs if not (R/r).is_file()];assert not missing
anchors=set(re.findall(r'id="([^"]+)"',s));targets=re.findall(r'href="#([^"]+)"',s);assert not(set(targets)-anchors)
report={'pages':len(marks),'page_order_valid':True,'images':len(refs),'missing_assets':missing,'broken_internal_anchors':list(set(targets)-anchors),'report_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_sha256':reg['source_sha256'],'native_accounting_scope':'native_coverage.json applies only to report.native.md; corrected report has deliberate deletion of hidden navigation and OCR artifacts, restored map labels, checkbox state and table links','render':'HTML generated, Chrome SIGABRT/EPERM at launch; screenshots unavailable','checked_pages':sorted(checked),'all_other_pages':'converted/pending'}
(R/'_проверка/final_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
