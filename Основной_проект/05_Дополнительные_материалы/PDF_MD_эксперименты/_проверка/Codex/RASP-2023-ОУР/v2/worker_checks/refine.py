import sys,re,json,hashlib,html
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import fitz
root=Path(__file__).resolve().parents[1]
base=(root/'_проверка/baseline/report.md').read_text()
src=json.load(open(root.parent/'source.json')); doc=fitz.open(src['source_pdf'])
parts=re.split(r'<!-- pdf_page: \d+ -->',base)[1:]
changes=[]
def log(n,what): changes.append({'pdf_page':n,'correction':what,'basis':'Original PDF page image and native text geometry'})
def table(headers,rows):
 return '<table>\n<tr>'+''.join('<th>'+x+'</th>' for x in headers)+'</tr>\n'+''.join('<tr>'+''.join('<td>'+x+'</td>' for x in r)+'</tr>\n' for r in rows)+'</table>'
def replace(n,a,b,new):
 t=parts[n-1];i=t.index(a);j=t.index(b,i);parts[n-1]=t[:i]+new+'\n\n'+t[j:]
# Each corrupt control glyph was inspected in a crop from the original PDF.
for n,t in enumerate(parts,1):
 if '\x03' in t: t=t.replace('\x03','');log(n,'Removed nonprinting U+0003 artifacts: source image has ordinary spaces/line breaks.')
 if '\x07' in t:
  t=t.replace('\x07','' if n in [2,14,19,27,36,43,58] else '🔗 ')
  log(n,'Resolved U+0007 from source crops: empty navigation spacing or visible chain-link pictogram.')
 # OCR supplements were visually checked on all eight flagged image-dominant pages.
 if '> Служебная пометка: распознанный текст изображения' in t:
  t=re.sub(r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\.\n\n.*?(?=> Служебная информация: ссылки исходного PDF|<details>)','',t,flags=re.S)
  log(n,'Removed OCR supplement after source inspection: duplicate/misrecognized native text or photograph noise (including TSV on page 19); native body text retained.')
 parts[n-1]=t
# Cover: text absent from native layer is read from the image.
parts[0]=parts[0].replace('<p>ОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ</p>','<p>РАСПАДСКАЯ</p>\n\n<p>ОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ</p>\n\n<p>2023</p>')
parts[0]=parts[0].replace('<p>Сохраняем</p>\n\n<p>устойчивость</p>','<h2>Сохраняем устойчивость</h2>')
log(1,'Added visible logo word РАСПАДСКАЯ and decorative year 2023; restored cover title.')
# Page 4: reorder existing native strings, do not regenerate their values.
t=parts[3];i=t.index('<p>ГЖ</p>');j=t.index('> Служебная информация:',i)
chunk=t[i:j];descs=re.split(r'(?=<p>Марка )',chunk)[1:]
rows=[]
for k,(mark,desc) in enumerate(zip(['ГЖ','Ж','КС','К','КО','ОС'],descs)):
 desc=desc[:desc.index('<p>Пояснения')] if '<p>Пояснения' in desc else desc
 desc=desc[:desc.index('<p>22+')] if '<p>22+' in desc else desc
 val=re.findall(r'<p>(\d+\+ МЛН Т В ГОД)</p>',chunk)[k]
 rows.append([mark,desc.strip(),val+'<br/>объем добычи в России'])
parts[3]=t[:i]+table(['Марка','Описание','Объем добычи в России'],rows)+'\n\n<p><sup>1</sup> Пояснения и расшифровка аббревиатур приведены в приложении «Термины и аббревиатуры» на с. 136.</p>\n\n'+t[j:]
log(4,'Rebuilt six portfolio rows: each native description associated with its mark and production volume; reunited footnote 1.')
# Page 11: timeline. Native blocks have been individually associated with visible year positions.
blocks=[]
for b in doc[10].get_text('dict')['blocks']:
 if 'lines' in b: blocks.append((b['bbox'],'\n'.join(''.join(s['text'] for s in l['spans']) for l in b['lines'])))
def block(x,y):
 b=min(blocks,key=lambda b:abs(b[0][0]-x)+abs(b[0][1]-y))
 return html.escape(b[1].replace('\x03','')).replace('\n','<br/>')
entries=[('1973–1977',[(45,297)]),('1991',[(100,426)]),('2003',[(149,297)]),('2004',[(194,426),(194,474)]),('2005',[(251,343)]),('2006',[(296,426),(296,493)]),('2008',[(354,297)]),('2010',[(400,426),(400,503)]),('2013',[(454,343)]),('2015',[(671,426)]),('2020',[(735,324)]),('2021',[(799,426)]),('2022',[(856,297),(856,316),(856,345),(856,364)]),('2023',[(919,426),(919,493),(919,512)])]
new='<h2>История Компании</h2>\n\n'+table(['Год','События'],[[year,'<br/><br/>'.join(block(x,y) for x,y in xy)] for year,xy in entries])+'\n\n<h3>«РАСПАДСКАЯ» СЕГОДНЯ</h3>\n<p>'+block(774,729)+'</p>\n<p>'+block(1027,729)+'</p>\n\n'
t=parts[10];parts[10]=t[:t.index('<p>История Компании')]+new+t[t.index('> Служебная информация:'):]
log(11,'Restored chronological timeline by source positions: year/events rows, including original hyphens; native text copied from PDF blocks.')
# Page 13: all four chart series, which were duplicated and disconnected in native candidate.
years=['2023','2022','2021']
replace(13,'<p>Статистика инцидентов','<p>🔗 Подробнее', '<h3>Статистика инцидентов на производстве</h3>\n'+table(['Год','Инциденты'],list(map(list,zip(years,['45','49','66'])))))
replace(13,'<p>Численность персонала','<p>«Распадская» |','<h3>Численность персонала (тыс. человек)</h3>\n'+table(['Год','Численность'],list(map(list,zip(years,['17,7','17,3','16,2']))))+'\n<p>🔗 Подробнее см. в разделе «Развитие человеческого капитала» на с. 52</p>')
replace(13,'<p>Объем выбросов метана','<p>23</p>','<h3>Объем выбросов метана (тыс. т СО<sub>2</sub>-экв.)</h3>\n'+table(['Год','Объем'],list(map(list,zip(years,['11 766','13 419','12 472']))))+'\n<p>🔗 Подробнее см. в разделе «Охрана окружающей среды» на с. 68</p>')
replace(13,'<p>Общий объем социальных инвестиций','> Служебная информация:','<h3>Общий объем социальных инвестиций (млн руб.)</h3>\n'+table(['Год','Объем'],list(map(list,zip(years,['485','373','368']))))+'\n<p>🔗 Подробнее см. в разделе «Вклад в развитие регионов присутствия» на с. 62</p>')
log(13,'Restored all four year/value series from visible chart labels; removed repeated invisible/overprinted values and false table tracks.')
# Page 21: third project continues in fourth column, above it is an independent plans box.
t=parts[20];a=t.index('<p>Планы на');b=t.index('<p>Для\u00a0водителей',a);c=t.index('> Служебная информация:',b)
parts[20]=t[:a]+t[b:c]+t[a:b]+t[c:]
log(21,'Moved separate 2024 plans box after complete transport-safety project; restored continuation from fourth column.')
# Page 26: chart labels have one value each, not duplicate pairs.
replace(26,'<p>Статистика инцидентов','<p>Затраты на','<h3>Статистика инцидентов на производстве</h3>\n'+table(['Год','Инциденты'],list(map(list,zip(years,['45','49','66']))))+'\n<h3>Число опасных производственных объектов (ед.)</h3>\n'+table(['Год','Число объектов'],list(map(list,zip(years,['54','56','54'])))))
log(26,'Restored both complete chart series with explicit year/value associations; removed duplicated overprinted labels.')
# Wrap every remaining table to make it scrollable in HTML-capable Markdown viewers.
for n,t in enumerate(parts,1):
 t=t.replace('<table>','<div style="overflow-x:auto">\n<table>').replace('</table>','</table>\n</div>')
 parts[n-1]=t
# Per-page limitations remain visible in main document and in registry.
checked={1,4,11,13,19,21,26,27,43,58}
for n,t in enumerate(parts,1):
 note=''
 if n not in checked:
  note='> Техническая пометка: converted / pending — текст перенесен; полная построчная сверка, связи таблиц и диаграмм по оригиналу не завершены.\n\n'
  t=t.replace(f'<a id="pdf-page-{n}"></a>\n\n',f'<a id="pdf-page-{n}"></a>\n\n'+note)
 parts[n-1]=t
prefix='# ОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ\n\n> Техническая информация: рабочая версия полного переноса 70 физических страниц. Проверка отдельных объектов не подтверждает весь документ. Реестр и протокол находятся в `_проверка/`.\n\n'
report=prefix+''.join(f'<!-- pdf_page: {n} -->'+t for n,t in enumerate(parts,1))
(root/'report.md').write_text(report)
(root/'_проверка/corrections.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
print('Saved',len(report),'characters;',len(changes),'correction records')
