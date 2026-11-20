import json,re,sys,hashlib,html
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
root=Path('result'); audit=root/'_проверка'
s=(audit/'report.native.md').read_text(); parts=re.split(r'<!-- pdf_page: \d+ -->',s)[1:]
registry=json.loads((audit/'pages.json').read_text()); pages=registry['pages'];changes=[]
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf
source=json.loads(Path('source.json').read_text());pdf=pymupdf.open(source['source_pdf'])
line_blocks={}
for n,page in enumerate(pdf,1):
 mapping={}
 for bi,block in enumerate(page.get_text('rawdict')['blocks']):
  if block['type']!=0:continue
  for line in block.get('lines',[]):
   chars=[c for span in line['spans'] for c in span['chars']]
   if not chars:continue
   box=[min(c['bbox'][0] for c in chars),min(c['bbox'][1] for c in chars),max(c['bbox'][2] for c in chars),max(c['bbox'][3] for c in chars)]
   mapping[tuple(round(v,2) for v in box)]=(bi,block['bbox'])
 line_blocks[n]=mapping
# Reorder the existing native objects; do not retype their text or numbers.
def reorder(n,regions):
 part=parts[n-1];matches=list(re.finditer(r'<table>.*?</table>|<p>.*?</p>',part,re.S))
 # PDF objects end before the links service block.
 end=part.find('> Служебная информация: ссылки'); end=end if end>=0 else part.find('<details>')
 matches=[m for m in matches if m.start()<end]; objs=pages[n-1]['objects']; assert len(matches)==len(objs),(n,len(matches),len(objs))
 items=[(o,m.group()) for o,m in zip(objs,matches)];used=set();out=[]
 for x0,y0,x1,y1,order in regions:
  group=[]
  for k,(o,t) in enumerate(items):
   x,y=(o['bbox'][0]+o['bbox'][2])/2,(o['bbox'][1]+o['bbox'][3])/2
   source_block=line_blocks[n].get(tuple(round(v,2) for v in o['bbox']))
   if source_block and source_block[1][2]-source_block[1][0]<250:
    y=(source_block[1][1]+source_block[1][3])/2
   if k not in used and x0<=x<x1 and y0<=y<y1:group.append((k,o,t));used.add(k)
  if order=='y':
   def sortkey(v):
    o=v[1]; b=line_blocks[n].get(tuple(round(z,2) for z in o['bbox']))
    top=b[1][1] if b and b[1][2]-b[1][0]<250 else o['bbox'][1]
    return (round(top/3),o['bbox'][0] if not b else b[1][0],o['bbox'][1])
   group.sort(key=sortkey)
  out.extend(t for _,_,t in group)
 out.extend(t for k,(o,t) in enumerate(items) if k not in used)
 parts[n-1]=part[:matches[0].start()]+'\n\n'.join(out)+part[matches[-1].end():]
 changes.append({'pdf_page':n,'object':'reading_order','action':'Переставлены исходные объекты по визуально установленным областям; текст и числа не переписаны.'})
def band(x0,x1,y0,y1,cuts=()):
 edges=[x0,*cuts,x1];return [(a,y0,b,y1,'y') for a,b in zip(edges,edges[1:])]
# Additional visually established reading regions. Tables remain indivisible native objects.
C=(225,390); R=(800,965)
layouts={
2:band(0,595,0,600)+band(0,595,600,850,(225,))+band(595,1140,0,850,R),
3:band(0,595,0,550)+band(0,595,550,850,C)+band(595,1140,0,850,R),
4:band(0,595,0,600)+band(0,595,600,850,C)+band(595,1140,0,850,R),
5:band(0,595,0,260)+band(0,595,260,405,C)+band(0,595,405,850)+band(595,1140,0,850),
8:band(0,595,0,140)+band(0,595,140,400,C)+band(0,595,400,850)+band(595,1140,0,850),
13:band(0,595,0,245)+band(0,595,245,850,C)+band(595,1140,0,245)+band(595,1140,245,850,R),
14:band(0,595,0,200)+band(0,595,200,700,(310,))+band(0,595,700,850)+band(595,1140,0,850,(880,)),
17:band(0,595,0,575,(315,))+band(0,595,575,850)+band(595,1140,0,850,R),
18:band(0,595,0,220)+band(0,595,220,850,(225,))+band(595,1140,0,630,R)+band(595,1140,630,850),
19:band(0,595,0,135)+band(0,595,135,540,(225,))+band(0,595,540,595)+band(0,595,595,850,C)+band(595,1140,0,365,R)+band(595,1140,365,415)+band(595,1140,415,640,R)+band(595,1140,640,850),
20:band(0,595,0,270)+band(0,595,270,850,C)+band(595,1140,0,710,R)+band(595,1140,710,850),
21:band(0,595,0,205)+band(0,595,205,670,C)+band(0,595,670,850)+band(595,1140,0,175)+band(595,1140,175,850,R),
23:band(0,595,0,850,C)+band(595,1140,0,850,R),
24:band(0,595,0,850,C)+band(595,1140,0,850,(800,)),
25:band(0,595,0,290,C)+band(0,595,290,850)+band(595,1140,0,850,R),
26:band(0,595,0,850,C)+band(595,1140,0,850,R),
27:band(0,595,0,540,C)+band(0,595,540,850)+band(595,1140,0,540,R)+band(595,1140,540,850),
28:band(0,595,0,155)+band(0,595,155,630,(310,))+band(0,595,630,850)+band(595,1140,0,850,(880,)),
29:band(0,595,0,520)+band(0,595,520,850)+band(595,1140,0,470,R)+band(595,1140,470,530)+band(595,1140,530,850,(800,)),
30:band(0,595,0,850,(270,))+band(595,1140,0,270,R)+band(595,1140,270,650)+band(595,1140,650,850,R),
31:band(0,595,0,850,C)+band(595,1140,0,850,R),
32:band(0,595,0,140)+band(0,595,140,410,(225,))+band(0,595,410,470)+band(0,595,470,850,C)+band(595,1140,0,140)+band(595,1140,140,850,R),
33:band(0,595,0,570,C)+band(0,595,570,850)+band(595,1140,0,850,R),
34:band(0,595,0,160)+band(0,595,160,630,(310,))+band(0,595,630,850)+band(595,1140,0,850,(890,)),
35:band(0,595,0,850,C)+band(595,1140,0,850,R),
36:band(0,595,0,850)+band(595,1140,0,850),
37:band(0,595,0,850,C)+band(595,1140,0,850,R),
38:band(0,595,0,850,C)+band(595,1140,0,260,R)+band(595,1140,260,650)+band(595,1140,650,850),
39:band(0,595,0,155)+band(0,595,155,630,(310,))+band(0,595,630,850,(310,))+band(595,1140,0,850,(890,)),
40:band(0,595,0,850,C)+band(595,1140,0,230)+band(595,1140,230,850,R),
41:band(0,595,0,850,C)+band(595,1140,0,310)+band(595,1140,310,850),
42:band(0,595,0,850,C)+band(595,1140,0,570)+band(595,1140,570,850,R),
43:band(0,595,0,310)+band(0,595,310,850,C)+band(595,1140,0,270)+band(595,1140,270,670,R)+band(595,1140,670,850),
44:band(0,595,0,590)+band(0,595,590,850,C)+band(595,1140,0,210)+band(595,1140,210,650,R)+band(595,1140,650,850),
45:band(0,595,0,175)+band(0,595,175,630,(310,))+band(0,595,630,850,(310,))+band(595,1140,0,850,(890,)),
46:band(0,595,0,850,C)+band(595,1140,0,850,R),
48:band(0,595,0,850,C)+band(595,1140,0,850,R),
54:band(0,595,0,850)+band(595,1140,0,190)+band(595,1140,190,850,R)
}
# The color matrix must keep its original contiguous source object range until replaced below.
layouts.pop(41)
for n,regions in layouts.items():reorder(n,regions)
# Physical page 6: KPI cards are read by row, then by card.
r=band(0,595,0,130)
for a,b in [(130,264),(264,418),(418,574),(574,733)]:
 r+=band(0,595,a,a+22) if a!=130 else []
 r+=band(0,595,a+22 if a!=130 else a,b,(265,415))
r+=band(0,595,733,850)
r+=band(595,1140,0,130)+band(595,1140,130,510,(945,))+band(595,1140,510,600)+band(595,1140,600,850,(865,))
reorder(6,r)
# Strategy: main narrative, chronology, then E/S/G columns.
reorder(10,band(0,595,0,265)+band(0,595,265,405,(225,390))+band(0,595,405,850)+band(595,1140,0,138)+band(595,1140,138,730,(800,965))+band(595,1140,730,850))
# Safety spread: preserve the two independent document columns.
reorder(22,band(0,595,0,295)+band(0,595,295,385,(245,385))+band(0,595,385,435)+band(0,595,435,675,(315,))+band(0,595,675,701)+band(0,595,701,770,(315,))+band(0,595,770,850)+band(595,1140,0,850,(880,)))
# Supply chain spread: independent document and KPI cards plus right-hand prose.
reorder(47,band(0,595,0,185)+band(0,595,185,680,(310,))+band(0,595,680,850,(310,))+band(595,1140,0,850,(800,965)))
# Methods and appendices, read each printed half separately.
reorder(49,band(0,595,0,850)+band(595,1140,0,850))
reorder(50,band(0,595,0,470)+band(0,595,470,620,(225,390))+band(0,595,620,850,(225,390))+band(595,1140,0,220,(800,))+band(595,1140,220,530,(800,965))+band(595,1140,530,850))
# Cover: visual reading of logo replaces unverified OCR.
parts[0]=parts[0].replace('> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена.\n\nЯ<br/>АКРОН','<p>АКРОН</p>')
changes.append({'pdf_page':1,'object':'logo','before':'Я / АКРОН','after':'АКРОН','basis':'Визуально прочитана обложка: декоративный знак логотипа не является буквой Я.'})
# Repair the first column and merged cells of the energy-saving table.
p=parts[15]; table=re.search(r'<table>.*?</table>',p,re.S).group(); soup=BeautifulSoup(table,'html.parser');rows=soup.find_all('tr')
for ri,text,span in [(1,'ПАО «Акрон»',8),(9,'ПАО «Дорогобуж»',1),(10,'АО «СЗФК»',3)]:
 td=soup.new_tag('td');td['rowspan']=str(span);td.string=text;rows[ri].insert(0,td)
p=p.replace(table,str(soup));
for name in ['ПАО «Акрон»','ПАО «Дорогобуж»','АО «СЗФК»']:p=p.replace('<p>'+name+'</p>','',1)
parts[15]=p;changes.append({'pdf_page':16,'object':'table','action':'Восстановлена первая колонка: Акрон — 8 строк, Дорогобуж — 1, СЗФК — 3. Проверены все строки и объединения по исходному изображению.'})
# Page 49: rightmost column and its five detached ticks.
p=parts[48];table=re.search(r'<table>.*?</table>',p,re.S).group();soup=BeautifulSoup(table,'html.parser'); rows=soup.find_all('tr')
for k,row in enumerate(rows[2:]):
 td=soup.new_tag('td');td.string='✓' if k in [0,1,4,5,6] else '';row.append(td)
p=p.replace(table,str(soup)); assert p.count('<p>\uf050</p>')==5;p=p.replace('<p>\uf050</p>','');parts[48]=p
changes.append({'pdf_page':49,'object':'table','action':'Восстановлена колонка АО «ВКК»: галочки в строках 1, 2, 5, 6, 7; остальные ячейки пустые. Все 9 строк и четыре компании сверены по изображению.'})
# Unicode artifacts inspected on each flagged source image.
for i,p in enumerate(parts):parts[i]=p.replace('\x07','').replace('\uf050','✓')
changes.append({'pdf_pages':[6,10,22,25,47,49,50],'object':'Unicode','action':'Удалён невидимый управляющий U+0007; шрифтовый U+F050 заменён видимым знаком ✓ по оригиналу. Данные и пустые ячейки не изменены.'})
# A colored competency matrix is not detected as a native table. Reconstruct from the image.
p=parts[40];a=p.index('<p>Член СД</p>');b=p.index('<p>О\xa0Компании</p>',a)
headers=['Член СД','Стратегия','Финансы и аудит','Агроиндустрия','Производство удобрений','IT, инновации','Корпоративное управление','ESG и устойчивое развитие','Управление рисками','Работа с персоналом и системами мотивации','Продажи']
names=['1. Попов Александр Валериевич','2. Гавриков Владимир Викторович','3. Арутюнов Николай Багратович','4. Дынкин Александр Александрович','5. Антонов Иван Николаевич','6. Данильченко Нина Викторовна','7. Колосовский Андрей Леонидович','8. Беликов Игорь Вячеславович','9. Швалюк Валерий Петрович']
matrix=['FF---FEFFE','E--E-F--F-','EF---F-EF-','F---FF----','FEFFEEFEFF','FF--EE-FE-','F-EFE-FEFE','FE---FFEE-','-E---E-FF-']
legend={'F':'К','E':'О','-':''};markup='<table>\n<tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr>\n'
for name,row in zip(names,matrix):
 assert len(row)==10
 markup+='<tr><td>'+name+'</td>'+''.join('<td>'+legend[c]+'</td>' for c in row)+'</tr>\n'
markup+='</table>\n\n<p>К — Наличие компетенций в полной мере; О — Наличие образования/опыта/навыков.</p>\n\n'
p=p[:a]+markup+p[b:];parts[40]=p
changes.append({'pdf_page':41,'object':'colored competency matrix','action':'Восстановлена таблица 9 × 10 по цветовым ячейкам оригинала. Два оттенка обозначены К и О с легендой; белые ячейки оставлены пустыми.'})
# Consolidate uniquely identifiable consecutive native lines from the same source block.
for n,part in enumerate(parts,1):
 original_parts=re.split(r'<!-- pdf_page: \d+ -->',s)[1:]
 original=original_parts[n-1]
 end=original.find('> Служебная информация: ссылки');end=end if end>=0 else original.find('<details>')
 native=list(re.finditer(r'<table>.*?</table>|<p>.*?</p>',original[:end],re.S))
 mapping={}
 for m,o in zip(native,pages[n-1]['objects']):
  b=line_blocks[n].get(tuple(round(z,2) for z in o['bbox']))
  if b and o['kind']=='text':mapping.setdefault(m.group().replace('\x07','').replace('\uf050','✓'),set()).add(b[0])
 matches=list(re.finditer(r'<p>.*?</p>',part,re.S));last=None;edits=[]
 for m in matches:
  ids=mapping.get(m.group(),set());bid=next(iter(ids)) if len(ids)==1 else None
  if last and bid is not None and bid==last[1] and not part[last[0].end():m.start()].strip():
   edits.append((last[0].end()-4,m.start()+3,'<br/>'))
  last=(m,bid)
 for a,b,value in reversed(edits):part=part[:a]+value+part[b:]
 parts[n-1]=part
# Start with the source title, and keep page boundaries unique.
intro='# Отчет об устойчивом развитии 2023\n\nГруппа «Акрон»\n\n> Служебная информация: рабочая версия полной конвертации. Все 54 физические страницы представлены текстом и исходными изображениями. Полная построчная сверка не выполнена; статусы и ограничения приведены в `_проверка/pages.json`. Изображения внутри раскрывающихся блоков сохраняют исходную графику.\n\n'
report=intro+''.join(f'<!-- pdf_page: {i} -->'+p for i,p in enumerate(parts,1))
(root/'report.md').write_text(report)
(audit/'corrections.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
