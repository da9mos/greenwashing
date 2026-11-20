from pathlib import Path
import sys,re,json,html,hashlib,collections
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
root=Path(__file__).resolve().parents[1];checks=root/'_проверка'
base=(checks/'baseline_report.md').read_text();parts=re.split(r'<!-- pdf_page: (\d+) -->',base);pages={int(parts[i]):parts[i+1] for i in range(1,len(parts),2)}
records=json.loads((checks/'pages.json').read_text());log=[]
def table(headers,rows):
 return '<table>\n<tr>'+''.join('<th>'+x+'</th>' for x in headers)+'</tr>\n'+'\n'.join('<tr>'+''.join('<td>'+x+'</td>' for x in row)+'</tr>' for row in rows)+'\n</table>'
def replace_body(n,body):
 old=pages[n]; links=re.search(r'> Служебная информация: ссылки исходного PDF.*?(?=<details>)',old,re.S)
 asset=re.search(r'<details>.*?</details>',old,re.S)[0]
 pages[n]=f'\n<a id="pdf-page-{n}"></a>\n\n'+body+'\n\n'+(links[0] if links else '')+asset+'\n\n'
def note(n,msg):log.append({'pdf_page':n,'action':msg,'evidence':'Original PDF raster, not another transcription'})
# Source font controls are not text. U+0007: right-angle list marker; U+0008: blank spacer.
for n,t in pages.items():
 a=t.count('\x07');b=t.count('\x08')
 if a or b:
  pages[n]=t.replace('\x07','• ').replace('\x08',' ')
  if n==186:pages[n]=pages[n].replace('* • В бизнес','* В бизнес')
  note(n,f'Font-map controls: U+0007={a}, U+0008={b}; restored list marker / blank spacer by rendered font samples. Page-wide review remains separate.')
# Cover: include wordmark and source title, no invented metadata.
replace_body(1,'# ГОДОВОЙ ОТЧЕТ 2025\n\nТАТНЕФТЬ\n\n2025\n\nБУДУЩЕЕ В КАЖДОМ ШАГЕ')
note(1,'Cover visually transcribed, including wordmark.')
# Openers: source annotation captions provide text and exact PDF destinations.
openers={3:'01',9:'02',11:'',28:'03',50:'04',103:'05',130:'06',144:'07',152:'08',162:'09',169:'10',194:'11',204:'12'}
for n,num in openers.items():
 soup=BeautifulSoup(pages[n],'html.parser');rows=[];seen=set()
 for a in soup.select('ul a'):
  caption=' '.join(a.get_text().split());m=re.match(r'(.*?)\s+(\d+)$',caption)
  if not m:continue
  label,value=m.groups()
  if n==50 and value=='160':label='Взаимодействие с коренным местным населением, ведущим традиционный образ жизни'
  if n==103 and value=='204':label='Содействие социальному развитию'
  if n==103 and value=='255':label='Развитие туристско-рекреационного кластера'
  if n==194 and value=='400':label='Отчет независимого аудитора по заданию, обеспечивающему ограниченную уверенность'
  if n==204 and value=='408':label='Приложение 1. Отчет о соблюдении принципов и рекомендаций кодекса корпоративного управления'
  key=label,value
  if key in seen:continue
  seen.add(key);rows.append([f'<a href="{html.escape(a["href"],quote=True)}">{html.escape(label)}</a>',value])
 if n==50:
  order=['98','100','110','115','126','146','160','162','173','180','194'];rows.sort(key=lambda r:order.index(r[1]))
 title=BeautifulSoup(rows[0][0],'html.parser').get_text()
 body='## '+(num+'. ' if num else '')+title+'\n\nТАТНЕФТЬ — БУДУЩЕЕ В КАЖДОМ ШАГЕ\n\n'+table(['',''],rows)
 if n==3:body+='\n\n159 млрд руб. — прибыль, причитающаяся акционерам'
 if n==9:body+='\n\nСозданная стоимость — 1 869 млрд руб.'
 # All annotation destinations are already retained within the new table.
 replace_body(n,body);pages[n]=re.sub(r'> Служебная информация: ссылки исходного PDF.*?(?=<details>)','',pages[n],flags=re.S)
 note(n,'Opener restructured; source wordmark transcribed; OCR noise removed after visual inspection; links retained from PDF annotation destinations.')
# Two native tables on page 65, geometry independently verified: remove detector-only columns.
body65=[]
for side in [1,2]:
 soup=BeautifulSoup((checks/f'page65_half{side}.html').read_text(),'html.parser')
 for p in soup.find_all('p'):body65.append(str(p))
 t=soup.find('table');rr=[]
 for row in t.find_all('tr'):
  vals=[''.join(c.decode_contents()) for c in row.find_all('td') if c.get_text(strip=True)]
  if vals:rr.append(vals)
 assert len(rr[0])==6 and len(rr[1])==6
 headers=['']+[a+'<br/>'+b for a,b in zip(rr[0],rr[1])]
 s='<table>\n<tr>'+''.join('<th>'+v+'</th>' for v in headers)+'</tr>\n'
 for vals in rr[2:]:
  if len(vals) not in [1,7]: vals=[' '.join(vals)]
  assert len(vals) in [1,7],vals
  s+='<tr>'+('<td colspan="7">'+vals[0]+'</td>' if len(vals)==1 else ''.join('<td>'+v+'</td>' for v in vals))+'</tr>\n'
 body65.append(s+'</table>')
replace_body(65,'\n\n'.join(body65));note(65,'Two separate seven-column tables reconstructed from native cells using existing converter on two source halves. Every value and header visually compared; no numbers recomputed.')
# Raster-only chart values, read directly from labels.
replace_body(67,'''## ВКЛАД В ОХРАНУ ОКРУЖАЮЩЕЙ СРЕДЫ ПО БИЗНЕС-НАПРАВЛЕНИЯМ

'''+table(['','Доля'],[['Нефтегазопереработка','60,6 %'],['Разведка и добыча','31,7 %'],['Нефтегазохимия','3,4 %'],['Прочие СП/ПСО','2,4 %'],['Рознично-сбытовая сеть','1,6 %'],['Энергетика','0,7 %'],['Композиционные материалы','0,4 %'],['Шинный бизнес','0,4 %'],['Машиностроение','0 %']])+'''

## ВКЛАД В ОХРАНУ ОКРУЖАЮЩЕЙ СРЕДЫ В СООТВЕТСТВИИ С КЛАССИФИКАТОРОМ СЕРА 2000

'''+table(['','Доля'],[['Охрана атмосферного воздуха и предотвращение изменения климата','45,9 %'],['Защита и экологическая реабилитация земель, поверхностных и подземных водных объектов','22,7 %'],['Обращение со сточными водами','20,9 %'],['Обращение с отходами','10 %'],['Другие направления деятельности в области охраны окружающей среды','0,5 %'],['Радиационная безопасность окружающей среды (за исключением мер по предотвращению аварий и катастроф)','0,04 %'],['Научно-исследовательская деятельность и разработки в области охраны окружающей среды','0,006 %'],['Снижение шумового и вибрационного воздействия','0,005 %'],['Сохранение биоразнообразия и охрана природных территорий','0,001 %']])+'\n\n132 | 133')
note(67,'Both raster charts fully transcribed from visible labels; replaced incomplete OCR. Percentages preserved as printed, without normalization.')
# Page 136: left source lines already correct; repair adjacent table and right reading order.
t=pages[136];left=t[t.index('<p>КОРПОРАТИВНОЕ УПРАВЛЕНИЕ'):t.index('<p>ВОЗРАСТНОЙ СОСТАВ')]
left+='\n<h3>ВОЗРАСТНОЙ СОСТАВ</h3>\n'+table(['от 30 до 50 лет','старше 50 лет'],[['2 человека','13 человек'],['13%','87%']])+'\n<h3>ГЕОГРАФИЧЕСКАЯ ПРИНАДЛЕЖНОСТЬ</h3>\n'+table(['Россия','Иные страны'],[['14 человек','1 человек'],['93,3%','6,7%']])
right='''
<h2>Деятельность Совета директоров</h2>
<p>GRI 2-17 | МЭР 36</p>
<p>Для обеспечения эффективной работы Совета директоров Компания предоставляет информационно-технические ресурсы с защищенным каналом связи для доставки материалов по повестке заседаний, обеспечивает проведение заседаний в формате видеоконференций и реализует процедуры информирования Совета директоров, в т. ч. о критически важных проблемах в случае их возникновения.</p>
<p>Совет директоров осуществляет свою деятельность на основании утвержденного плана работы с повесткой вопросов на каждое полугодие. План рассматриваемых вопросов формируется с учетом предложений членов Совета директоров, исполнительных органов и топ-менеджеров. Заседания Совета директоров проводятся в очной и заочной форме в соответствии с утвержденным планом, а также по мере необходимости, но, как правило, не реже одного раза в месяц.</p>
<p>Вопросы устойчивого развития включены в повестку заседаний Совета директоров на постоянной основе, получают должное внимание и своевременное реагирование. В 2025 году Совет директоров провел 16 заседаний и рассмотрел 82 вопроса. С решениями Совета директоров можно ознакомиться на сайте Компании: www.tatneft.ru.</p>
<h3>КОЛИЧЕСТВО ЗАСЕДАНИЙ</h3>
'''+table(['','2023','2024','2025'],[['ОЧНОЕ','12','12','12'],['ЗАОЧНОЕ','5','5','4']])+'''
<h3>ТЕМАТИКА ВОПРОСОВ</h3>
'''+table(['вид заседания','2023','2024','2025'],[['Корпоративная практика','42','36','25'],['Борьба с коррупцией','1','1','1'],['Стратегия развития Компании','4','3','11'],['Инвестиционная деятельность','1','1','1'],['Аудит','1','1','2'],['Производство','10','9','4'],['Устойчивое развитие','4','5','3'],['Персонал','1','1','2'],['Финансы','22','23','24'],['ИТОГО','86','80','82']])+'\n<p>270 | 271</p>'
replace_body(136,left+right);note(136,'Resolved 2024 header ambiguity, recovered complete question-topic table, split age/geography tables, transcribed meeting chart, restored reading order of right columns. All blocks compared to source raster.')
# Additional source-verified diagnostic pages.
t=pages[33]
# Reuse native wording and numbers; replace broken chart/table relationships.
start=t.index('<p>ФОНД ОПЛАТЫ ТРУДА');end=t.index('<p>ИНТЕГРИРОВАННЫЙ',start)
vals=re.findall(r'<p>(.*?)</p>',t[start:end],re.S)
assert vals==['ФОНД ОПЛАТЫ ТРУДА | МЛН РУБ.','2025','2024','2023','112 037','93 441','79 051']
t=t[:start]+'<h3>'+vals[0]+'</h3>'+table(['Год','млн руб.'],[[vals[i],vals[i+3]] for i in range(1,4)])+t[end:]
soup=BeautifulSoup(t,'html.parser');tab=soup.find('table',string=None)
# Select native revenue table, not the chart just reconstructed.
revenue=next(x for x in soup.find_all('table') if 'Расчет выручки' in x.get_text())
values=[c.get_text() for c in revenue.find_all('tr')[2].find_all('td')]
assert values==['37 458','47 729','41 500','-6 228']
new=table(['Расчет выручки на одного работника*','2023','2024','2025','2025/2024 +/-','2025/2024 %'],[['выручка на 1-го работника, тыс. руб./чел.']+values+['87']])
t=t.replace(str(revenue),new) if str(revenue) in t else re.sub(r'<table>\s*<tr><td[^>]*>Расчет выручки.*?</table>',new,t,flags=re.S)
t=re.sub(r'<p>выручка на 1-го работника, тыс.</p>\s*<p>87</p>\s*<p>руб./чел.</p>','',t)
t=t[:t.index('> Служебная пометка: распознанный текст изображения')]
t=re.sub(r'^.*?<p>ПЕРСОНАЛ</p>','<p>ПЕРСОНАЛ</p>',t,count=1,flags=re.S)
replace_body(33,t);note(33,'Revenue row restored to label plus five numeric cells; chart years linked to values; OCR noise removed after full-page comparison.')
replace_body(77,'''## Загрязняющие вещества

GRI 3-3 | 305-6 | 305-7; SASB EM-EP-120a.1 | EM-RM-120a.1; МЭР 19; СОКБ 7

В 2025 году валовые выбросы загрязняющих веществ в атмосферный воздух по Группе «Татнефть» составили 90,3 тыс. т, что на 0,11% меньше показателя за 2024 год. Снижение выбросов загрязняющих веществ в атмосферный воздух достигается за счет осуществления соответствующих мероприятий:

### ЭНЕРГОХОЗЯЙСТВО И ТРАНСПОРТ

- сероочистка ПНГ
- внедрение экономайзеров
- повышение экокласса транспорта
- газовозвратные колонки на АЗС

результат:

- снижение выбросов диоксида серы, оксида азота, угарного газа, летучих органических соединений
- экономия топлива

### ГЕРМЕТИЧНОСТЬ И СНИЖЕНИЕ ПОТЕРЬ

- поддержание технического состояния оборудования
- дооснащение системами УЛФ
- снижение сжигания ПНГ
- замена факелов на бессажевые

результат:

- сокращение выбросов метана, летучих органических соединений, сажи
- возврат ресурсов в производственный процесс

### ТЕХНОЛОГИЧЕСКАЯ МОДЕРНИЗАЦИЯ И ЦИФРОВИЗАЦИЯ

- модернизация производства с применением лучших технологий и цифровых решений

результат:

- снижение неорганизованных выбросов
- оптимизация процессов горения

### ВЫБРОСЫ ЗАГРЯЗНЯЮЩИХ ВЕЩЕСТВ ОТ СТАЦИОНАРНЫХ ИСТОЧНИКОВ | ТЫС. Т

'''+table(['Год','тыс. т'],[['2025','90,3'],['2024','90,4'],['2023','102,2']])+'''

### РАСПРЕДЕЛЕНИЕ ВЫБРОСОВ ЗАГРЯЗНЯЮЩИХ ВЕЩЕСТВ В АТМОСФЕРНЫЙ ВОЗДУХ ПО БИЗНЕС-НАПРАВЛЕНИЯМ

'''+table(['','Доля'],[['Разведка и добыча','67 %'],['Нефтегазопереработка','21,1 %'],['Нефтегазохимия','4,27 %'],['Энергетика','3,0 %'],['Розничный бизнес','2,76 %'],['Композиционные материалы','0,9 %'],['Шинный бизнес','0,63 %'],['Прочие СП/ПСО','0,24 %'],['Машиностроение','0,1 %']])+'''

### СОСТАВ ВЫБРОСОВ ГАЗООБРАЗНЫХ ЗАГРЯЗНЯЮЩИХ ВЕЩЕСТВ

'''+table(['','Доля'],[['Летучие органические соединения','50 %'],['Оксид углерода','16 %'],['Углеводороды (без ЛОС)','15 %'],['Оксид азота (в пересчете на NO₂)','9 %'],['Диоксид серы','9 %'],['Прочие','1 %']])+'\n\n152 | 153')
note(77,'Both raster distribution charts transcribed; native emissions chart linked to years; full text and lists compared to original.')
t=pages[119];t=t[t.index('<p>СОДЕЙСТВИЕ'):t.index('> Служебная пометка: распознанный текст изображения')]
replace_body(119,t);note(119,'Full-page visual comparison; removed spurious OCR of decorative list marks. Original repeated wording «людей пожилых людей» retained.')

# Scans: retain all OCR words, separated by actual logical pages; no confidence filtering.
for n in [201,202,203]:
 old=pages[n];native=old[:old.index('> Служебная пометка: распознанный текст изображения')]
 native=re.sub(r'^\s*<a.*?</a>','',native,flags=re.S)
 body=native+'\n> Служебная пометка: текст тела распознан локальным Tesseract rus+eng по отдельным половинам разворота. Полная пословная сверка не завершена; возможны ошибки OCR. Подписи и печати сохранены на исходном изображении.\n\n'
 for side in [1,2]:
  txt=(checks/f'ocr/page_{n:04}_{side}.txt').read_text().strip()
  # only confirmed corrections from the viewed originals
  txt=txt.replace('кбудущему','к будущему').replace('8 483 006 т СО--экв.','8 483 006 т СО₂-экв.').replace('8 483 006 тСО.-экв.','8 483 006 т СО₂-экв.')
  if n==201 and side==1:
   txt=txt.replace('СК!','GRI').replace('СЕ»','GRI»')
  body+=f'<!-- scanned_logical_page: {2*(n-201)+side} -->\n\n'+txt+'\n\n'
 replace_body(n,body);note(n,'Re-OCRed entire scan body at 216 dpi in independent halves, without discarding low-confidence words. Complete proofread pending.')
# Inline pending status is explicit for every unreviewed page.
checked={1,3,9,11,28,33,50,65,67,77,103,119,130,136,144,152,162,169,194,204}
for n in pages:
 if n not in checked:
  pages[n]=pages[n].replace(f'<a id="pdf-page-{n}"></a>',f'<a id="pdf-page-{n}"></a>\n\n> Служебная пометка: converted / review pending. Полная сверка текста, порядка чтения, таблиц и графики этой страницы не завершена.')
prefix='# ГОДОВОЙ ОТЧЕТ 2025\n\n> Служебная информация: рабочая версия полного переноса 258 физических страниц. Использован механический кандидат по глифам PDF; исправления и объём фактической сверки перечислены в `_проверка/`. Остальные страницы имеют статус converted / pending. Изображения служат визуальной опорой.\n\n'
# Keep only a single top-level document title.
pages[1]=pages[1].replace('# ГОДОВОЙ ОТЧЕТ 2025','## ГОДОВОЙ ОТЧЕТ 2025')
report=prefix+''.join(f'<!-- pdf_page: {n} -->'+pages[n] for n in range(1,259));(root/'report.md').write_text(report)
for r in records['pages']:
 n=r['pdf_page'];r['baseline_issues']=r.get('baseline_issues',r['issues']);r['conversion_status']='converted';r['review_status']='checked' if n in checked else 'pending';r['semantic_source_review_completed']=n in checked
 r['verification_scope']='Full page visually compared to PDF raster and corrected' if n in checked else 'Native transfer accounting; full semantic/visual review pending'
 r['review_actions']=[x['action'] for x in log if x['pdf_page']==n]
 r['issues']=[] if n in checked else ['Полная сверка страницы по оригиналу не завершена: требуется проверить порядок чтения, связи ячеек, сноски и текст графики.']
 if n in [201,202,203]:r['issues'].append('OCR тела выполнен; требуется полная пословная сверка, включая имена, идентификаторы, даты и числовые значения.')
 r['diagnostic_review']='source overview inspected; only listed corrections verified' if r['baseline_issues'] and n not in checked else ('full source page inspected' if n in checked else 'pending')
 r['report_page_sha256']=hashlib.sha256(pages[n].encode()).hexdigest()
 records['report_sha256']=hashlib.sha256(report.encode()).hexdigest()
(checks/'pages.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
(checks/'corrections.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n')
print('Saved',len(pages),'pages;',len(checked),'checked;',len(log),'correction records')
