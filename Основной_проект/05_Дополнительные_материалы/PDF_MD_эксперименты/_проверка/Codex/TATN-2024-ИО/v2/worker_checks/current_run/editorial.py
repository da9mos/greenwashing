import sys,re,json,html
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf
from bs4 import BeautifulSoup
s=Path('result/report.md').read_text();a=re.split(r'<!-- pdf_page: (\d+) -->',s);doc=pymupdf.open(json.load(open('source.json'))['source_pdf']);log=[]
def body(n):return a[n*2]
def replacebody(n,new):
 old=body(n); tail=old[old.index('> Служебная информация: ссылки исходного PDF'):] if '> Служебная информация: ссылки исходного PDF' in old else old[old.index('<details>'):]
 a[n*2]=f'\n<a id="pdf-page-{n}"></a>\n\n'+new+'\n\n'+tail
 log.append(n)
def cleantext(t):return ' '.join(t.split())
# Contents: four visible columns; each source arrow opens one entry; retain printed destinations.
p=doc[1]; entries=[]
for x0,x1 in [(65,350),(350,700),(715,1015),(1020,1340)]:
 lines=[]
 for b in p.get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   x,y,_,_=l['bbox']
   if not(x0<=x<x1 and 95<y<795):continue
   ss=l['spans'];txt=cleantext(''.join(z['text'] for z in ss if z['font']!='TatSymbol-Regular').replace('\x07',''))
   start=any(z['font']=='TatSymbol-Regular' and z['text'].strip() in ['2','3'] for z in ss)
   if txt or start:lines.append((y,x,txt,start))
 group=[]
 for y,x,t,start in sorted(lines):
  if start and group:entries.append(group);group=[]
  if t:group.append(t)
 if group:entries.append(group)
rows=[]
for entry in entries:
 nums=[x for x in entry if re.fullmatch(r'\d+',x)]
 title=' '.join(x for x in entry if not re.fullmatch(r'\d+',x))
 rows.append((title,' '.join(nums)))
Path('result/_проверка/current_run/contents_rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
replacebody(2,'<p>2 | 3</p>\n\n## Содержание\n\n| Раздел | Печатная страница |\n|---|---|\n'+'\n'.join('| '+t+' | '+v+' |' for t,v in rows))
# Separator pages: source tables contain multiple independent entries in one cell.
seps=[3,18,22,30,45,55,83,103,117,125,141,167]
for n in seps:
 t=body(n);t=t[:t.index('> Служебная информация: ссылки исходного PDF')] if '> Служебная информация: ссылки исходного PDF' in t else t[:t.index('<details>')]
 t=t.split('> Служебная пометка:')[0]
 t=re.sub(r'<p>ШМУЦ</p>\s*','',t)
 soup=BeautifulSoup(t,'html.parser')
 for table in soup.find_all('table'):
  rows2=[]
  for tr in table.find_all('tr'):
   cells=tr.find_all('td',recursive=False)
   if len(cells)!=2:continue
   col1=[cleantext(x) for x in cells[0].get_text('\n').split('\n') if cleantext(x)]
   col2=[cleantext(x) for x in cells[1].get_text('\n').split('\n') if cleantext(x)]
   # Text wraps within title; match number of entries using known source line joins.
   if len(col1)!=len(col2):
    joins={'и\u00a0расследование инцидентов','и расследование инцидентов','и\u00a0климатической повестки','и климатической повестки','культурного и исторического наследия','с коренным местным населением, ведущим','традиционный образ жизни','Кодекса корпоративного управления','об\u00a0устойчивом\u00a0развитии','об\u00a0устойчивом\u00a0развитии, отражающих вклад','в\u00a0реализацию национальных целей развития'}
    merged=[]
    for x in col1:
     if (x in joins or x.startswith(('и расследование','и климатической','культурного и','с коренным','традиционный','Кодекса','об устойчивом','в реализацию'))) and merged:merged[-1]+=' '+x
     else:merged.append(x)
    col1=merged
   if len(col1)==len(col2):rows2.extend(zip(col1,col2))
   else:rows2=[];break
  if rows2:
   new=soup.new_tag('table')
   for x,y in rows2:
    tr=soup.new_tag('tr')
    for val in [x,y]:td=soup.new_tag('td');td.string=val;tr.append(td)
    new.append(tr)
   table.replace_with(new)
 t=str(soup);t=re.sub(r'<a id="pdf-page-\d+"></a>','',t).strip()
 # Logotypes and chapter numerals belong to visible design, not OCR garbage.
 chapter={3:'01',18:'02',22:'03',30:'04',45:'05',55:'06',83:'07',103:'08',117:'09',125:'10',141:'12',167:'14'}[n]
 replacebody(n,'<p>ТАТНЕФТЬ</p>\n<p>'+chapter+'</p>\n'+t)
# cover logotype missing from native text
x=body(1);a[2]=x.replace('<p>ОТ СМЕЛОГО ШАГА</p>','<p>ТАТНЕФТЬ</p>\n\n<p>ОТ СМЕЛОГО ШАГА</p>');log.append(1)
# visible cover for chapter 13: assemble entries explicitly
replacebody(160,'<p>ТАТНЕФТЬ</p>\n<p>13</p>\n<h2>Об Отчете</h2>\n\n| Раздел | Печатная страница |\n|---|---|\n| Существенные темы | 323 |\n| Общественное заверение Отчета | 326 |\n| Заключение независимого практикующего специалиста | 327 |\n| Заявления о прогнозах | 331 |')
# Reorder page 5 by thematic blocks. All text comes from the native candidate.
t=body(5);ps=re.findall(r'<p>(.*?)</p>',t,re.S); texts=[BeautifulSoup(x,'html.parser').get_text() for x in ps]
def span(start,end):return ' '.join(texts[texts.index(start):texts.index(end)+1])
new='<h2>МЫ – ТАТНЕФТЬ!</h2>\n\n<p>МИССИЯ; ВИДЕНИЕ; КУЛЬТУРНЫЙ КОД; ЦЕННОСТИ КОМПАНИИ; СТРАТЕГИЯ УСТОЙЧИВОСТИ; БИЗНЕС-МОДЕЛЬ; ЦЕЛЕПОЛАГАНИЕ; МОТИВАЦИЯ</p>\n\n'
new+='<p>'+span('3 столпа, которые поддерживают нашу деятельность','и в том, что ее ждут великие свершения.')+'</p>\n'
for title,start,end in [('ОПЫТ ПРОШЛОГО','фундамент, прямо влияющий на настоящее,','отражает приверженность традициям'),('ЭНЕРГИЯ НАСТОЯЩЕГО','катализация энергии жизни происходит здесь','друг в друга'),('УСТОЙЧИВОСТЬ БУДУЩЕГО','это результат наших действий сегодня,','и прозрачно, как лента Мёбиуса')]:new+='<h3>'+title+'</h3>\n<p>'+span(start,end)+'</p>\n'
new+='<p>1 2 3 4 5 6</p>\n'
for x in texts:
 if re.match(r'[1-4]\. ',x):new+='<p>'+x+'</p>\n'
new+='<p>'+span('5. Орден за заслуги','2017 г.')+'</p>\n<p>6. Орден за доблестный труд 2025 г.</p>'
replacebody(5,new)
# OCR blocks 164: certificate and auditor's first page, transcribed from the source images.
t=body(164);pre=t.split('> Служебная пометка:')[0];left,right=pre.split('<p>ИНТЕГРИРОВАННЫЙ',1)
certificate='''<h3>СВИДЕТЕЛЬСТВО</h3>
<p>Российский союз промышленников и предпринимателей</p>
<p>об общественном заверении корпоративного нефинансового отчета</p>
<p>Интегрированный годовой отчет ПАО «Татнефть» им. В.Д.Шашина за 2024 год прошел процедуру общественного заверения в Совете РСПП по нефинансовой отчетности, индексам и рейтингам устойчивого развития:</p>
<p>Интегрированный годовой отчет ПАО «Татнефть» им. В.Д.Шашина за 2024 год содержит значимую информацию по основным направлениям ответственной деловой практики в соответствии с принципами Социальной хартии российского бизнеса, с достаточной полнотой раскрывает сведения о деятельности Компании в этих направлениях.</p>
<p>Заверяющее заключение Совета РСПП об общественном заверении Интегрированного годового отчета ПАО «Татнефть» им. В.Д.Шашина за 2024 год направлено в Компанию, которая может публиковать его без каких-либо изменений и использовать для целей внутрикорпоративных и внешних, таких как в целях коммуникации с заинтересованными сторонами.</p>
<p>Регистрационный номер 288.04.037.01.24</p>
<p>Президент РСПП А.Шохин</p>
<p>Москва, 2025</p>'''
ocr=t.split('точность OCR не подтверждена.\n\n')[1].split('> Служебная информация:')[0]
ocr=ocr[ocr.index('Публичному акционерному'):]
fixes={'по Группе раскрытым':'по Группе «Татнефть»<sup>1</sup>, раскрытым','® GRI':'• GRI','инициативы по отчетности?':'инициативы по отчетности<sup>2</sup>','GRI (СР! Content<br/>|пдех)»3':'GRI (GRI Content<br/>Index)»<sup>3</sup>','`В периметр':'<sup>1</sup> В периметр','2 GRI Sustainability':'<sup>2</sup> GRI Sustainability','«Указатель GRi&gt;':'<sup>3</sup> Приложение «Указатель GRI»'}
for x,y in fixes.items():ocr=ocr.replace(x,y)
left=re.sub(r'<a id="pdf-page-164"></a>','',left).strip()
replacebody(164,left+'\n\n'+certificate+'\n\n<p>ИНТЕГРИРОВАННЫЙ'+right+'\n\n'+ocr)
# OCR 165: correct confirmed defects, preserve all body text and line order.
t=body(165);pre,ocr=t.split('> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена.\n\n',1);ocr=ocr.split('> Служебная информация:')[0]
for x,y in {'ГОД. 7<br/>':'','e Проведение':'• Проведение','® Изучение':'• Изучение','© Оценку':'• Оценку','GRI (СЕ! Content Index)':'GRI (GRI Content Index)','том алаяпений п собпюлении тоебований. не относяшихся к Поименимым коитериям.':'том числе заявлений о соблюдении требований, не относящихся к Применимым критериям.','в отношении прогнозного характера':'в отношении заявлений прогнозного характера'}.items():ocr=ocr.replace(x,y)
pre=re.sub(r'<a id="pdf-page-165"></a>','',pre).strip();replacebody(165,pre+'\n\n'+ocr)
# Auditor conclusion must precede forecast statements on the right half. Remove OCR noise and duplicate native footer.
t=body(166);nativepart=t.split('> Служебная пометка:')[0];forecast=nativepart[nativepart.index('<p>Заявления о прогнозах</p>'):]
ocr=t.split('точность OCR не подтверждена.\n\n')[1].split('> Служебная информация:')[0]
ocr=ocr[:ocr.index('<br/>юридического<br/>')]
for x,y in {'(OPH3 21606080523)':'(ОРНЗ 21606080523)','‘ул.':'ул.','<br/>ФБК<br/>(000<br/>':'<br/>','(000 «ФБК).':'(ООО «ФБК»).','саморегулируемой = организации = аудиторов':'саморегулируемой организации аудиторов'}.items():ocr=ocr.replace(x,y)
footer='<p>ФБК</p><p>Общество с ограниченной ответственностью «Финансовые и бухгалтерские консультанты» (ООО «ФБК»).</p><p>Адрес юридического лица в пределах места нахождения юридического лица: 101000, г. Москва, ул. Мясницкая, д. 44, стр. 2.</p>'
replacebody(166,'<p>330 | 331</p>\n\n'+ocr+'\n\n'+footer+'\n\n'+forecast)
Path('result/report.md').write_text(a[0]+''.join('<!-- pdf_page: '+a[i]+' -->'+a[i+1] for i in range(1,len(a),2)))
Path('result/_проверка/current_run/editorial_pages.json').write_text(json.dumps(log))
print('Edited',log,'contents rows',len(rows))
