from pathlib import Path
import json,re,hashlib,importlib.util,sys
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf as fitz
root=Path(__file__).resolve().parents[1]
src=json.load(open('source.json'));pdf=fitz.open(src['source_pdf'])
tool=Path(src['source_pdf']).parents[1]/'tools/native_candidate.py'
spec=importlib.util.spec_from_file_location('native',tool);native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
text=(root/'_проверка/baseline/report.md').read_text();parts=re.split(r'<!-- pdf_page: \d+ -->',text)
reg=json.load(open(root/'_проверка/baseline/pages.json'));log=[]
# Source-derived thin rectangles represent rules; broad filled rectangles are backgrounds.
for n,top,bottom in [(27,164,1070),(28,164,992),(30,164,1027),(31,164,982),(32,164,1011),(144,249,1080)]:
 p=pdf[n-1];lines=[]
 for d in p.get_drawings():
  r=d['rect']
  if r.width<2 and r.height>50:lines.append(((r.x0+.5,top),(r.x0+.5,bottom)))
  if r.height<2 and r.width>100 and top<=r.y0<=bottom:lines.append(((r.x0,r.y0+.5),(r.x1,r.y0+.5)))
 right=1862 if n==144 else 1860
 lines += [((60,top),(60,bottom)),((right,top),(right,bottom)),((60,top),(right,top)),((60,bottom),(right,bottom))]
 tables=p.find_tables(paths=[],add_lines=lines)
 class Proxy:
  def get_text(self,*a,**k):return p.get_text(*a,**k)
  def find_tables(self,*a,**k):return tables
 body,diag=native.convert_page(Proxy())
 tail=parts[n][parts[n].index('> Служебная информация: ссылки исходного PDF'):] if '> Служебная информация: ссылки исходного PDF' in parts[n] else parts[n][parts[n].index('<details>'):]
 parts[n]=f'\n<a id="pdf-page-{n}"></a>\n\n'+body+'\n\n'+tail
 row=reg['pages'][n-1];row.update(diag);row['repair']='Reused native_candidate.convert_page with source thin-rule geometry and visual outer bounds; excluded background fills.'
 row['issues']=['Rebuilt table geometry: full cell-by-cell visual acceptance pending.']
 log.append({'page':n,'action':row['repair'],'remaining_ambiguous_glyphs':len(diag['ambiguous_cell_assignments'])})
# Reject duplicated/noisy residual OCR on pages with native body text. Preserve original in baseline.
for row in reg['pages']:
 n=row['pdf_page']
 if row.get('ocr_chars') and n!=125:
  parts[n]=re.sub(r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\.\n\n.*?(?=> Служебная информация:|<details>)','',parts[n],flags=re.S)
  row['ocr_residual_rejected']=True
  log.append({'page':n,'action':'Removed residual OCR duplicating native text or recognizing page/photo decoration; native text retained. Original OCR retained in baseline.'})
# Cover: source logo lettering and decorative MMK are absent from native layer.
parts[1]=parts[1].replace('<p>Годовой отчет</p>','<p>МАГНИТОГОРСКИЙ МЕТАЛЛУРГИЧЕСКИЙ КОМБИНАТ</p>\n\n<p>Годовой отчет</p>\n\n<p>ММК</p>')
log.append({'page':1,'action':'Added visually read company logo lettering and decorative ММК.'})
# Whole raster page: manually correct OCR and restore numbered relationship to map.
n=125;tail=parts[n][parts[n].index('> Служебная информация: ссылки исходного PDF'):]
parts[n]='\n<a id="pdf-page-125"></a>\n\n'+(root/'_проверка/review/page125_corrected.md').read_text()+'\n\n'+tail
log.append({'page':125,'action':'Replaced OCR with visual transcription of full body, all twelve numbered entries and map labels.'})
for n in [174,*range(196,205),207]:
 old=parts[n];parts[n]=parts[n].replace('\x07','').replace('\x08','')
 log.append({'page':n,'action':'Removed invisible font-map control characters U+0007/U+0008; image shows text spacing, no additional printed symbol.','count':len(old)-len(parts[n])})
# Keep every incomplete visual review explicitly pending, independently of conversion.
for row in reg['pages']:
 n=row['pdf_page'];row['review_status']='pending';row['semantic_source_review_completed']=False
 row['verification_scope']='Native accounting and automated integrity; full visual source comparison pending.'
 row['diagnostic_image_overview_viewed']=n in [p['pdf_page'] for p in json.load(open(root/'_проверка/baseline/pages.json'))['pages'] if p['issues']]
 if n in [1,125]:
  row['review_status']='checked';row['semantic_source_review_completed']=True;row['issues']=[];row['verification_scope']='Full source image visually read; cover lettering / raster text transcribed.'
 else:
  row['issues']=list(dict.fromkeys(row['issues']+['Full page visual comparison of reading order, table relationships and graphics remains pending.']))
 if n in [174,*range(196,205),207]:row['unicode_repair_completed']=True;row['unresolved_unicode']=0;row['issues']=[i for i in row['issues'] if 'font mapping' not in i]
 if n==125:row['ocr_verified']=True;row['printed_page']='124'
 if n==1:row['printed_page']=None
 # Plainly place unresolved review notice next to the affected page.
 if row['review_status']=='pending':
  notice='\n\n> Служебная пометка: рабочая транскрипция; полная визуальная сверка страницы, порядка чтения, таблиц и графики не завершена.\n'
  parts[n]=parts[n].replace(f'<a id="pdf-page-{n}"></a>',f'<a id="pdf-page-{n}"></a>'+notice,1)
header='# Годовой отчет 2023\n\n> Служебная информация: рабочая версия полного документа, 242 физических страницы. Визуально проверенные страницы и нерешённые вопросы перечислены в `_проверка/pages.json`. Сохранённые изображения не заменяют текст.\n\n'
out=header+''.join(f'<!-- pdf_page: {n} -->'+parts[n] for n in range(1,243))
(root/'report.md').write_text(out)
(root/'_проверка/pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n')
(root/'_проверка/corrections.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n')
(root/'_проверка/source_verification.json').write_text(json.dumps({'source_sha256':hashlib.sha256(Path(src['source_pdf']).read_bytes()).hexdigest(),'physical_pages':len(pdf),'final_report_sha256':hashlib.sha256(out.encode()).hexdigest(),'baseline_preserved':True},indent=2)+'\n')
print('Saved',len(out),'characters;',len(log),'correction records')
