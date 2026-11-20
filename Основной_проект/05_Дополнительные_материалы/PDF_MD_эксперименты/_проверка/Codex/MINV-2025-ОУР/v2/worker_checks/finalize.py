from pathlib import Path
import json,re,sys,hashlib,html
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import fitz
from bs4 import BeautifulSoup
r=Path('result');s=(r/'report.md').read_text();parts=re.split(r'<!-- pdf_page: (\d+) -->',s);pages={int(parts[i]):parts[i+1] for i in range(1,len(parts),2)}
pages[75]=pages[75].replace('<p>ВЗАИМО</p>\n\n<p>ДЕЙСТВИЕ</p>','<p>ВЗАИМОДЕЙСТВИЕ</p>')
for n,label in [(75,'заголовке раздела'),(187,'адресе электронной почты')]:
 pages[n]=pages[n].replace('<details>',f'> Служебная пометка: ссылка в {label} исходного PDF ведёт на недоступный локальный файл верстки InDesign. Видимый текст сохранён; назначение не восстановлено.\n\n<details>',1)
# All abbreviation rows individually compared against source page 187.
t=BeautifulSoup(pages[187],'html.parser').find('table');rows=[]
for tr in t.find_all('tr'):
 cells=[td.get_text(' ',strip=True) for td in tr.find_all('td')];rows.append(cells)
entries=[];pre=''
for key,val in rows:
 if key:
  entries.append([key, ((pre+' ') if pre else '')+val]);pre=''
 elif entries:entries[-1][1]+=' '+val
 else:pre=val
# First empty cell is English HR name; NPS English precedes its keyed row.
for i,e in enumerate(entries):
 if e[0]=='MSHA':
  e[1]=e[1].removesuffix(' Net Promoter Score')
 if e[0]=='NPS':e[1]='Net Promoter Score '+e[1]
new='| Сокращение | Расшифровка |\n| --- | --- |\n'+'\n'.join('| '+k+' | '+v+' |' for k,v in entries)
pages[187]=re.sub(r'<table>.*?</table>',new,pages[187],flags=re.S)
changes=json.load(open(r/'_проверка/corrections.json'));changes.extend([{'pdf_page':75,'change':'Собран заголовок из двух раздельно извлечённых частей; отмечена ссылка в отсутствующий файл верстки.','basis':'Изображение и аннотации PDF'},{'pdf_page':187,'change':'Объединены строки расшифровок с их сокращениями по изображению; отмечено отсутствующее назначение ссылки.','basis':'Все 14 строк таблицы сверены по исходному изображению'}]);(r/'_проверка/corrections.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
source=json.load(open('source.json'));pdf=fitz.open(source['source_pdf']);reg=json.load(open(r/'_проверка/pages.json'))
checked=[1,188]; diagnostic=[1,6,21,22,30,31,44,45,50,66,75,84,97,102,116,131,145,183,187,188]
for p in reg['pages']:
 n=p['pdf_page'];p['baseline_issues']=p['issues'];p['review_status']='checked' if n in checked else 'pending';p['conversion_status']='converted';p['semantic_source_review_completed']=n in checked
 p['verification_scope']='Вся страница визуально сверена' if n in checked else ('Просмотр диагностических областей и выборочная сверка; вся страница не проверена' if n in diagnostic else 'Механический перенос; визуальная сверка не выполнена')
 p['issues']=[] if n in checked else ['Полная сверка текста, порядка чтения, таблиц и связей с оригиналом не завершена.']
 if n in [75,187]:p['issues'].append('Аннотация исходного PDF ведёт в отсутствующий файл верстки; назначение ссылки не восстановлено.')
 if n==183:p['issues'].append('Мелкие реквизиты растрового заключения требуют повторного контрольного чтения; основной текст прочитан и исправлен.')
 p['source_image_viewed']=n in diagnostic;p['diagnostic_records_inspected']=n in diagnostic;p['corrections']=[x['change'] for x in changes if x['pdf_page']==n]
 p['printed_labels']=[]
 for b in pdf[n-1].get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   txt=''.join(v['text'] for v in l['spans']).strip()
   if l['bbox'][1]>800 and re.fullmatch(r'\d{1,3}',txt):p['printed_labels'].append(txt)
 p['content_type']='mixed_raster_text' if p.get('ocr_chars') else ('text_tables_graphics' if p.get('tables') else 'text_graphics')
 p['ocr_verified']= n==188 if p.get('ocr_chars') else None
 if n not in checked:
  anchor=f'<a id="pdf-page-{n}"></a>'
  msg='> Служебная пометка: converted / pending — полная сверка этой страницы по оригиналу не завершена.'
  pages[n]=pages[n].replace(anchor,anchor+'\n\n'+msg,1)
reg['source_sha256']=hashlib.sha256(Path(source['source_pdf']).read_bytes()).hexdigest();reg['total_pages']=len(pdf);reg['review_summary']={'checked_pages':checked,'diagnostic_pages_viewed':diagnostic,'unreviewed_pages':'Все остальные страницы: converted / pending','scope':'Просмотр диагностических участков не равен полной сверке страницы.'}
(r/'_проверка/pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n')
s=parts[0]+''.join(f'<!-- pdf_page: {n} -->'+pages[n] for n in range(1,189));(r/'report.md').write_text(s)
# Keep native coverage as historical evidence, with explicit final-version status.
c=json.load(open(r/'_проверка/native_coverage.json'));c['applies_to']='baseline/report.md; механический кандидат до адресных правок';c['final_report_sha256']=hashlib.sha256(s.encode()).hexdigest();c['final_report_has_manual_repairs']=True;c['semantic_source_review_completed']=False;(r/'_проверка/native_coverage.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n')
# Bundle integrity only, not accuracy.
ids=re.findall(r'<a id="([^"]+)"',s);internal=re.findall(r'href="#([^"]+)"',s);images=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',s)
missing=[p for p in images if not (r/p).is_file()];bad=[p for p in internal if p not in ids]
assert re.findall(r'<!-- pdf_page: (\d+) -->',s)==list(map(str,range(1,189)))
assert not missing and not bad
check={'pages':188,'source_sha256':reg['source_sha256'],'report_sha256':hashlib.sha256(s.encode()).hexdigest(),'image_links':len(images),'missing_assets':missing,'broken_internal_anchors':bad,'replacement_characters':s.count('�'),'scope':'Структурная целостность, не точность транскрипции'}
(r/'_проверка/integrity.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n');print(check)
