from pathlib import Path
import re,json,html,hashlib,sys
import fitz
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
src=json.load(open(ROOT.parent/'source.json'))
doc=fitz.open(src['source_pdf'])
original=(ROOT/'_проверка/versions/report.native.md').read_text()
parts=re.split(r'(?=<!-- pdf_page: \d+ -->)',original)
log=[]
def note(n,what):log.append({'pdf_page':n,'correction':what,'basis':f'Visual reading of source page image assets/page_{n:04}.png; native PDF geometry/text where applicable'})
def suffix(n):
 p=parts[n]
 i=p.find('> Служебная информация: ссылки исходного PDF')
 if i<0:i=p.find('<details>')
 return p[i:]
def replacebody(n,body):parts[n]=f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+body+'\n\n'+suffix(n)
def ocr(n,value):
 pat=r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\.\s*.*?(?=> Служебная информация: ссылки исходного PDF|<details>)'
 parts[n],count=re.subn(pat, value+'\n\n' if value else '',parts[n],flags=re.S)
 assert count==1,n
 note(n,'Replaced unverified OCR supplement after source-image inspection; removed duplicates, decoration noise and TSV metadata; retained image-only labels as text.')
def esc(s):return html.escape(s)
def table(headers,rows):return '<table>\n<tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr>\n'+''.join('<tr>'+''.join('<td>'+c+'</td>' for c in r)+'</tr>\n' for r in rows)+'</table>'
def txt(n,box):
 p=doc[n-1]; out=[]
 for b in p.get_text('dict')['blocks']:
  if 'lines' not in b:continue
  for l in b['lines']:
   if not(box[0]<=l['bbox'][0] and l['bbox'][2]<=box[2] and box[1]<=l['bbox'][1] and l['bbox'][3]<=box[3]):continue
   spans=[]
   for s in l['spans']:
    t=esc(s['text']);spans.append('<sup>'+t+'</sup>' if s['flags']&1 else t)
   out.append((l['bbox'][1],l['bbox'][0],''.join(spans).strip()))
 return '<br/>'.join(x[2] for x in sorted(out))
# Cover: all displayed text, without OCR hallucinations.
replacebody(1,'# ОПОРА УСТОЙЧИВОГО БУДУЩЕГО\n\nРУСАЛ\n\nОтчет об устойчивом развитии\n\n2023')
note(1,'Reconstructed cover title, report type, year and logo lettering; removed OCR artifacts «Г» and «8g».')
# Four-column contents: reuse complete source blocks, each entry with its own printed page.
rows=[]
for lo,hi in [(80,500),(532,950),(984,1400),(1436,1850)]:
 pending=[]
 for b in sorted(doc[1].get_text('blocks'),key=lambda b:b[1]):
  if b[0]<lo or b[2]>hi or b[1]<180 or b[1]>1000:continue
  lines=[x.strip() for x in b[4].splitlines() if x.strip()]
  if lines and re.fullmatch(r'\d+',lines[-1]):
   number=lines.pop(); label=' '.join(pending+lines);pending=[];rows.append((esc(label),number))
  else:pending+=lines
 assert not pending
replacebody(2,'## Содержание\n\n'+table(['Раздел','Страница (печатная)'],rows)+'\n\n1')
note(2,'Rebuilt four independent contents columns as consecutive entry/page pairs; resolved ambiguous whitespace glyph and removed fictitious empty columns.')
# Section dividers: inspect native lines by font size to isolate titles from entries.
covers={5:'О компании',11:'Стратегия устойчивого развития',24:'Охрана окружающей среды',43:'Изменение климата и энергоэффективность',53:'Сотрудники',66:'Охрана труда и промышленная безопасность',82:'Развитие местных сообществ',101:'Корпоративное управление и устойчивое развитие',134:'Приложения'}
icons={24:'12 Ответственное потребление и производство; 15 Сохранение экосистем суши.',43:'13 Борьба с изменением климата; 17 Партнерство в интересах устойчивого развития.',53:'8 Достойная работа и экономический рост.',66:'3 Хорошее здоровье и благополучие; 8 Достойная работа и экономический рост.',82:'3 Хорошее здоровье и благополучие; 8 Достойная работа и экономический рост; 11 Устойчивые города и населенные пункты.',101:'17 Партнерство в интересах устойчивого развития.'}
for n,title in covers.items():
 entries=[]
 for b in doc[n-1].get_text('dict')['blocks']:
  lines=[]
  for l in b.get('lines',[]):
   if l['bbox'][0]>610 or l['bbox'][1]<240 or l['bbox'][1]>950:continue
   if max(s['size'] for s in l['spans'])>30:continue
   lines.append(''.join(s['text'] for s in l['spans']).strip())
  if lines:
   assert lines[-1].isdigit(),(n,lines)
   entries.append((min(l['bbox'][1] for l in b['lines'] if l['bbox'][0]<=610 and 240<=l['bbox'][1]<=950 and max(s['size'] for s in l['spans'])<=30),esc(' '.join(lines[:-1])),lines[-1]))
 entries.sort()
 body='## '+title+'\n\n'
 if n==11:body+='«Будучи лидером отрасли, РУСАЛ на собственном примере демонстрирует процесс трансформации алюминиевого сектора в соответствии с принципами устойчивого развития»\n\n'
 body+=table(['Раздел','Страница (печатная)'],[(a,b) for _,a,b in entries])
 if n in icons:body+='\n\n'+icons[n]
 footer=doc[n-1].get_textbox(fitz.Rect(1850,1030,1910,1070)).strip()
 body+='\n\n'+footer
 replacebody(n,body);note(n,'Rebuilt section divider title and entry/page relationships; transcribed SDG icon lettering where present; removed spurious OCR.')
# Remove OCR that duplicated already complete native layer; transcribe actual image lettering.
supplements={6:'',8:'',25:'Экология. Национальные проекты России.',42:'',44:'Экология. Национальные проекты России.',51:'',52:'',54:'Образование. Национальные проекты России.',65:'',72:'',75:'',83:'Здравоохранение. Образование. Жильё и городская среда. Национальные проекты России.',89:'<p>Надпись на фотографии:</p><p>РУСАЛ</p><p>Благоустройство Парка Победы выполнено при поддержке компании РУСАЛ</p><p>Enhancements to the Victory Park were made possible thanks to the support of the company RUSAL</p>',90:'ШЕЛЕХОВ ПАРК',102:'Международная кооперация и экспорт. Национальные проекты России.',109:'8 Достойная работа и экономический рост; 16 Мир, правосудие и эффективные институты.',115:'8 Достойная работа и экономический рост; 12 Ответственное потребление и производство.\n\nМеждународная кооперация и экспорт. Национальные проекты России.',122:'',127:'',128:'8 Достойная работа и экономический рост; 12 Ответственное потребление и производство.\n\nНаука и университеты. Цифровая экономика. Производительность труда. Национальные проекты России.',206:''}
for n,value in supplements.items():ocr(n,value)
# Actual native text errors confirmed against printed source.
for n,a,b in [(83,'Основые показатели','Основные показатели'),(102,'заседания Советов директоров,','заседания Совета директоров,')]:
 assert a in parts[n];parts[n]=parts[n].replace(a,b);note(n,f'Source-image-confirmed native-text correction: {a} → {b}.')
# Source contains one visible client-experience box; PDF text layer contains two overlapping copies.
p=parts[122];start=p.index('<p>РУСАЛ стремится');end=p.index('<p>Функционал',start)
segment=p[start:end]
paragraphs=re.findall(r'<p>(.*?)</p>',segment,re.S)
# Retain one complete occurrence using native strings, excluding its overlapping second copy.
marker=next(i for i,v in enumerate(paragraphs[1:],1) if v.startswith('РУСАЛ стремится'))
parts[122]=p[:start]+'<p>'+' '.join(paragraphs[:marker])+'</p>\n\n'+p[end:]
note(122,'Removed duplicated overlapping PDF text for one visible client-experience box; retained one complete occurrence after comparison to source image.')
# Climate risks: explicit time columns and genuine merged cells, extracted within inspected geometry.
headers=[txt(137,(x,85,x+288,130)) for x in [976,1264,1552]]
left='<h2>Приложение 2. Дополнительная информация</h2>\n<h3>Экологический аспект</h3>\n<p>Климатические риски и возможности</p>\n'
left+='<table><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr><tr><th colspan="3">ФИЗИЧЕСКИЕ РИСКИ</th></tr><tr><td colspan="3">'+txt(137,(80,480,944,740))+'</td></tr><tr><th colspan="3">Связанные возможности:</th></tr><tr><td colspan="3">'+txt(137,(80,800,944,850))+'</td></tr></table>'
right=table(headers,[[txt(137,(x,175,x+288,750)) for x in [976,1264,1552]]])
right=right.replace('ТУР1','ТУР<sup>1</sup>')
right='<h3>ПЕРЕХОДНЫЕ РИСКИ</h3>\n'+right+'\n<table><tr><th colspan="3">Связанные возможности:</th></tr><tr><td>'+txt(137,(976,800,1264,945))+'</td><td colspan="2">'+txt(137,(1264,800,1840,945))+'</td></tr></table>'
replacebody(137,left+'\n\n'+right+'\n\n1 Трансграничное углеродное регулирование.\n\n136')
note(137,'Rebuilt physical and transition risk tables by three inspected time horizons; restored middle-column risks, genuine spans, blank space and footnote 1. All cell text reused from source PDF.')
# Scanned assurance: retain complete OCR body, correct against source, recover scan page labels.
for n in [202,203,204,205]:
 s=parts[n].split('точность OCR не подтверждена.')[1].split('> Служебная информация:')[0].strip()
 if n==202:
  s=s[s.index('Заключение независимого'):]
  header='''<p>Б1<br/>НОВЫЕ ВЫЗОВЫ<br/>НОВЫЕ РЕШЕНИЯ</p>
<table><tr><td>ООО «ЦАТР – аудиторские услуги»<br/>Россия, 115035, Москва<br/>Садовническая наб., 77, стр. 1<br/>Тел.: +7 495 705 9700<br/>+7 495 755 9700<br/>Факс: +7 495 755 9701<br/>ОГРН: 1027739707203<br/>ИНН: 7709383532<br/>ОКПО: 59002827<br/>КПП: 770501001</td><td>TSATR – Audit Services LLC<br/>Sadovnicheskaya Nab., 77, bld. 1<br/>Moscow, 115035, Russia<br/>Tel: +7 495 705 9700<br/>+7 495 755 9700<br/>Fax: +7 495 755 9701<br/>www.b1.ru</td></tr></table>'''
  s=header+'\n\n'+s.replace('06 устойчивом','об устойчивом')
 else:s=s.replace('10.<br/>','',1).replace('НОВЫЕ ВЫЗОВЫ','Б1<br/>НОВЫЕ ВЫЗОВЫ',1)
 if n==203:s=s.replace('управления качеством 4','управления качеством 1')
 if n==204:
  s=s.replace('Описание выполненных процедур,','Описание выполненных процедур').replace('проверки AO','проверки АО')
 if n==205:
  s=s.replace('ограничен ной','ограниченной').replace('Критериями,','Критериями.').replace('‘Ассоциация','Ассоциация')
  s=s.replace('<br/>внесена в Единый','<br/>Запись внесена в Единый')
 s=s.replace(' &gt;<br/>','<br/>').replace('&gt;» ','• ').replace('&gt; ','• ').replace('<br/>» ','<br/>• ')
 if n==204:s=s.replace('<br/>опросы руководителей','<br/>• опросы руководителей')
 s=s.replace('далее -','далее –').replace('решений - аудиторские','решений – аудиторские')
 if n>202:s+=f'<br/>{n-201}'
 ocr(n,s)
 footer=str(n-1)
 parts[n]=parts[n].replace('<p>'+footer+'</p>\n\n','',1)
 cut=parts[n].find('> Служебная информация: ссылки исходного PDF')
 parts[n]=parts[n][:cut]+'<p>'+footer+'</p>\n\n'+parts[n][cut:]
 note(n,'Read scanned assurance body against full source image; corrected OCR and recovered logo/page labels. Scan 203: quality-management standard 4 → 1; scan 205: recovered missing «Запись» and signature retained in full-page image.')
# Contact line reading order: reconstruct only affected paragraph from visible original and existing annotation destinations.
p=parts[206]
a=p.index('<p>Дополнительную информацию');b=p.index('<p>205</p>',a)
para='<p>Дополнительную информацию о РУСАЛе, корпоративном управлении, операционных и финансовых результатах Вы можете найти в <a href="https://rusal.ru/investors/financial-stat/presentations/">обзорах результатов</a>, <a href="https://rusal.ru/investors/financial-stat/annual-reports/">годовых отчетах</a> и <a href="https://rusal.ru/investors/financial-stat/msfo/">отчетности по МСФО</a>, доступных на сайте Компании в разделе «Инвесторам».</p>\n\n'
parts[206]=p[:a]+para+p[b:]
note(206,'Restored contact-paragraph reading order across hyperlink fragments; preserved source annotation destinations.')
# Expose headings already represented as exact native lines, without changing their text.
for n in range(3,207):
 if n in covers or n in [137]:continue
 for block in doc[n-1].get_text('dict')['blocks']:
  for line in block.get('lines',[]):
   st=''.join(s['text'] for s in line['spans']).strip()
   if max(s['size'] for s in line['spans'])>=30 and sum(c.isalpha() for c in st)>len(st)*.6 and len(st)>5:
    old='<p>'+esc(st)+'</p>'
    parts[n]=parts[n].replace(old,'<h2>'+esc(st)+'</h2>')
# Reassociate the inspected chart values with periods, series and units.
a=parts[51].index('<p>Энергомикс для алюминиевых заводов, %</p>')
b=parts[51].index('<p>В отчетном периоде Компания использовала',a)
v='<h3>Энергомикс для алюминиевых заводов, %</h3><p>2023</p>'+table(['Источник','Доля, %'],[['Ядерная энергия (АЭС)','0,05'],['Ископаемое топливо','0,40'],['Ветряная энергия','0,55'],['Гидроэнергия','98,99']])
v+='<h3>Общее энергопотребление и энергоемкость на продукцию алюминия<sup>1</sup>, млн ГДж</h3>'+table(['Год','Общее энергопотребление, млн ГДж','Энергоемкость, ГДж/т алюминия'],[['2021','478,7','127,2'],['2022','466,4','119,0'],['2023','451,9','117,4']])
v+='<h3>Доля потребления возобновляемой энергии, %</h3>'+table(['Год','Доля, %'],[['2021','51,3'],['2022','53,1'],['2023','55']])
parts[51]=parts[51][:a]+v+'\n\n'+parts[51][b:]
# Preserve the source footnote reference at its exact phrase, rather than as a detached numeral.
parts[51]=parts[51].replace('источников , что на 6%</p>\n\n<p>2</p>','источников<sup>2</sup>, что на 6%</p>')
a=parts[51].index('<p>Структура потребления топлива в разбивке по типу</p>');b=parts[51].index('<p>1 Показатель энергоемкости',a)
v='<h3>Структура потребления топлива в разбивке по типу</h3>'+table(['Год','Уголь, млн т','Газ, млн т','Мазут, млрд м<sup>3</sup>'],[['2021','3,6','3,6','0,7'],['2022','3,6','3,2','0,6'],['2023','3,4','3,0','0,6']])
parts[51]=parts[51][:a]+v+'\n\n'+parts[51][b:]
parts[51]=parts[51].replace('<p>2022</p>\n\n<p>2023</p>\n\n<p>50</p>','<p>50</p>')
note(51,'Replaced detached native chart labels with source-verified tables for energy mix, consumption/intensity, renewable energy and fuel; preserved printed values including graph 117,4 versus prose 177,4, without reconciling source inconsistency; attached footnotes to source objects.')
a=parts[72].index('<p>Динамика коэффициента');b=parts[72].index('<p>71</p>',a)
world=['0,34','0,24','0,26','0.26','0,38','0,32','0,26','0,20','0,25','0,24','']
rusal=['0,22','0,19','0,17','0,18','0,15','0,16','0,22','0,18','0,15','0,15','0,15']
v='<h3>Динамика коэффициента LTIFR на 200 000 человеко-часов</h3>'+table(['Год','Мир (данные международного института алюминия)','LTIFR (РУСАЛ)'],[[str(2013+i),w,r] for i,(w,r) in enumerate(zip(world,rusal))])
parts[72]=parts[72][:a]+v+'\n\n'+parts[72][b:]
note(72,'Rebuilt both LTIFR series by year from source chart. Preserved the source’s unusual decimal dot «0.26» for 2016 world series, verified in enlarged source crop; left 2023 world cell empty because no point/value is printed.')
a=parts[75].index('<p>Среднее количество часов');b=parts[75].index('<p>В 2023 году для обеспечения',a)
v='<h3>Среднее количество часов обучения на одного сотрудника (постоянные сотрудники), часов</h3>'+table(['Подразделение','Часов'],[['Алюминиевый дивизион','81,8'],['Глиноземный дивизион','47,1'],['Дивизион Даунстрим','21,4'],['Дирекция по новым проектам','5,1']])
parts[75]=parts[75][:a]+v+'\n\n'+parts[75][b:]
note(75,'Reassociated all four training-chart bars with division labels and hours after source-image comparison.')

# Clear local review notice on every not fully verified page (never imply full verification from character inventory).
checked={1,2,5,11,24,42,43,53,66,82,101,134,137,202,203,204,205,206}
viewed=set(covers)|set(supplements)|{1,2,137,202,203,204,205}
for n in range(1,207):
 if n not in checked:
  marker=f'<a id="pdf-page-{n}"></a>'
  notice='> Служебная пометка: converted / pending — полная сверка текста, порядка чтения, таблиц и графики этой страницы по оригиналу не завершена.'
  parts[n]=parts[n].replace(marker,marker+'\n\n'+notice,1)
parts[0]=''
# Begin with source title; place overall working-version notice after cover.
notice='\n\n> Служебная информация: рабочая версия полного переноса 206 физических страниц. Полная сверка выполнена только для страниц, отмеченных checked в `_проверка/pages.json`. Остальные имеют converted / pending. Изображения служат визуальной опорой, а не заменой тексту.\n\n'
parts[1]=parts[1].replace('РУСАЛ\n',notice+'РУСАЛ\n',1)
report=''.join(parts)
(ROOT/'report.md').write_text(report)
reg=json.load(open(ROOT/'_проверка/versions/pages.native.json'))
for page in reg['pages']:
 n=page['pdf_page'];page['conversion_status']='converted';page['review_status']='checked' if n in checked else 'pending';page['semantic_source_review_completed']=n in checked
 page['original_diagnostics']=page['issues'];page['diagnostic_review_status']='reviewed' if n in viewed else 'not_flagged'
 page['visual_source_inspected']=n in viewed
 page['verification_scope']='Full page content and source-image comparison' if n in checked else ('Diagnostic regions visually inspected; full page comparison pending' if n in viewed else 'Mechanical native glyph coverage only; full visual comparison pending')
 page['issues']=[] if n in checked else ['Полная сверка содержания, порядка чтения, таблиц, сносок и графики по оригиналу не завершена.']
 page['corrections']=[v['correction'] for v in log if v['pdf_page']==n]
 if False:page['issues'].append('Числа диаграмм сохранены из текстового слоя, но все связи ряд/категория/единица ещё не сверены; см. полное изображение страницы.')
 page['printed_labels']=[]
 footer=doc[n-1].get_textbox(fitz.Rect(1840,1030,1910,1070)).strip()
 if footer:page['printed_labels'].append(footer)
 if n in [203,204,205]:page['printed_labels'].append(str(n-201))
 page['content_type']='mixed_scan_and_native' if n in [202,203,204,205] else ('native_text_tables_graphics' if page['tables'] else 'native_text_and_graphics')
 page['native_accounting_scope']='Original mechanical candidate only; see versions/report.native.md. Addressed corrections can change the final glyph inventory.'
(ROOT/'_проверка/pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n')
(ROOT/'_проверка/corrections.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n')
summary={'source_sha256':hashlib.sha256(Path(src['source_pdf']).read_bytes()).hexdigest(),'report_sha256':hashlib.sha256(report.encode()).hexdigest(),'physical_pages':len(doc),'converted_pages':206,'checked_pages':sorted(checked),'visually_inspected_pages':sorted(viewed),'pending_review_pages':[n for n in range(1,207) if n not in checked],'full_document_verified':False,'corrections':len(log)}
(ROOT/'_проверка/review_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='pending_review_pages'},ensure_ascii=False,indent=2))
