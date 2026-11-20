"""Addressed repairs to the supplied mechanical candidate, using source glyphs.
This is not a replacement converter. Explicit regions follow source inspection.
"""
import sys,json,re,html,zipfile,pathlib,importlib.util,hashlib,collections
ROOT=pathlib.Path(__file__).resolve().parents[1]
source=json.load(open(ROOT.parent/'source.json'))
script=pathlib.Path(source['source_pdf']).parents[1]/'tools/native_candidate.py'
spec=importlib.util.spec_from_file_location('native',script);native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
import pymupdf as fitz
D=fitz.open(source['source_pdf'])
with zipfile.ZipFile(ROOT/'_проверка/native_before_review.zip') as z:original=z.read('report.md').decode();registry=json.loads(z.read('_проверка/pages.json'))
parts=re.split(r'<!-- pdf_page: (\d+) -->',original);P={int(parts[i]):parts[i+1] for i in range(1,len(parts),2)}
changes=[]; units={}
def U(n):
 if n not in units:
  a=[]
  for bi,b in enumerate(D[n-1].get_text('rawdict')['blocks']):
   for li,l in enumerate(b.get('lines',[])):
    for sp in l['spans']:
     for c in sp['chars']:a.append(dict(sequence=len(a),line=(bi,li),text=c['c'],bbox=c['bbox'],flags=sp['flags']))
  units[n]=a
 return units[n]
def R(n,box):
 x0,y0,x1,y1=box
 return native.render_glyphs([u for u in U(n) if x0<=(u['bbox'][0]+u['bbox'][2])/2<x1 and y0<=(u['bbox'][1]+u['bbox'][3])/2<y1])
def para(n,box):return '<p>'+R(n,box)+'</p>'
def table(n,xs,ys,merged=()):
 out=['<table>']
 for i,(a,b) in enumerate(zip(ys,ys[1:])):
  if i in merged:cells=['<td colspan="'+str(len(xs)-1)+'">'+R(n,(xs[0],a,xs[-1],b))+'</td>']
  else:cells=['<td>'+R(n,(x,a,y,b))+'</td>' for x,y in zip(xs,xs[1:])]
  out.append('<tr>'+''.join(cells)+'</tr>')
 return '\n'.join(out+['</table>'])
def details(n):return f'<details>\n<summary>Источник: PDF-страница {n}</summary>\n\n![Полная исходная страница {n}](assets/page_{n:04}.png)\n\n</details>'
def suffix(n):
 m=re.search(r'> Служебная информация: ссылки исходного PDF.*?(?=<details>)',P[n],re.S)
 linktext=m[0].strip() if m else ''
 if n==2:linktext=re.sub(r'[\x00-\x1f\ufffd]+',' … ',linktext);linktext=re.sub(r'(?:\s*…\s*)+',' … ',linktext)
 return (linktext+'\n\n' if m else '')+details(n)
def replace(n,body,reason):
 P[n]=f'\n<a id="pdf-page-{n}"></a>\n\n'+body+'\n\n'+suffix(n)+'\n\n';changes.append(dict(pdf_page=n,object='body',correction=reason,evidence=f'assets/page_{n:04}.png and original PDF glyph geometry'))
# OCR residuals: preserve original verbatim in the version archive and the audit log.
for n,t in list(P.items()):
 m=re.search(r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\.\n\n(.*?)(?=\n\n)',t,re.S)
 if m:
  changes.append(dict(pdf_page=n,object='supplemental OCR',removed_candidate=m[1],correction='Removed duplicate/misread native text, navigation/logo or decorative marks after structural image inspection; source artwork retained.',evidence=f'assets/page_{n:04}.png',scope='OCR residual only; not full page acceptance'))
  P[n]=t[:m.start()]+t[m.end():]
replace(1,'<p>РАСПАДСКАЯ</p>\n\n<p>Отчет об устойчивом развитии за 2025 год</p>','Cover title joined in reading order; logo transcribed; false OCR АЕ removed.')
# Contents: explicit source row bands; printed repeated 2.3 intentionally retained.
groups=[(1,'О компании',243,282,849,[165,185,205,225,245,265,285],133),(2,'Управление устойчивым развитием',243,282,849,[362,382,402,436,456],324),(3,'Охрана труда и промышленная безопасность',243,282,849,[543,563,583,603,623],504),(4,'Социальная ответственность',243,282,849,[718,738],670),(5,'Охрана окружающей среды',1025,1065,1633,[165,185,205,225,245,265,285],133),(6,'Корпоративное управление',1025,1065,1633,[362,382,402,422,442],324),(7,'Технологическое развитие и цифровая трансформация',1025,1065,1633,[523,543,563],484),(8,'Приложения',1025,1065,1633,[639,660,680,700,720,753,773],600)]
# Retain the PDF annotation destinations as separately labelled source links, without guessing from printed numbering.
toc=[]
toc_titles={}
for num,title,nx,tx,x1,ys,hy in groups:
 toc.append(f'## {num}. {title}')
 toc.append('<table>\n<tr><th>Раздел</th><th>Название</th><th>Страница</th></tr>')
 for i,y in enumerate(ys):
  end=ys[i+1]-.2 if i+1<len(ys) else y+(34 if num==2 and i==2 else 20)
  no=html.unescape(R(2,(nx,y,tx-1,end))).replace('<br/>',' ')
  raw=html.unescape(R(2,(tx,y,x1,end))).replace('<br/>',' ')
  raw=re.sub(r'[\x00-\x1f\ufffd]+',' … ',raw);raw=re.sub(r'(?:\s*…\s*)+',' … ',raw)
  match=re.match(r'(.*?)\s*…\s*(\d+)\s*$',raw)
  assert match,(num,raw)
  toc_titles.setdefault(num,[]).append(match[1].strip())
  toc.append('<tr><td>'+no+'</td><td>'+html.escape(match[1].strip())+'</td><td>'+match[2]+'</td></tr>')
 toc.append('</table>')
replace(2,'\n\n'.join(toc),'Repaired contents: removed damaged dot leaders and restored associations of subsection, title and printed page. Source duplicate 2.3 retained.')
# Section dividers: explicit source body, subsection labels paired with titles via original link annotations.
section_pages={3:('1','О Компании'),20:('2','Управление устойчивым развитием'),35:('3','Охрана труда и промышленная безопасность'),58:('4','Социальная ответственность'),95:('5','Охрана окружающей среды'),124:('6','Корпоративное управление'),161:('7','Технологическое развитие и цифровая трансформация'),174:('8','Приложения')}
for n,(num,title) in section_pages.items():
 # Read source annotation rectangles for each subsection, pair split number/title annotations by destination and vertical band.
 links=[]
 names=D.resolve_names()
 for l in D[n-1].get_links():
  if l.get('page',-1)<0 and l.get('nameddest'):
   key=l['nameddest']
   variants=[key]
   try:variants.append(key.encode('latin1').decode('utf8'))
   except (UnicodeError,AttributeError):pass
   for key in variants:
    if key in names:l['page']=names[key].get('page',-1);break
  r=l['from'];text=' '.join(D[n-1].get_textbox(r).split())
  if r.y0>400 and l.get('page',-1)>=0 and (re.match(r'^[1-8]\.\d',text) or (links and links[-1][0]==l['page'] and abs(links[-1][1]-r.y0)<30)):
   if links and links[-1][0]==l['page'] and abs(links[-1][1]-r.y0)<30:links[-1][2]+=' '+text
   else:links.append([l['page'],r.y0,text])
 assert links, n
 entries=[]
 for dest,y,t in links:
  no=re.match(r'^([1-8]\.\d+)',t)[1]
  idx=int(no.split('.')[1])-1
  entries.append((idx,dest,no+' '+toc_titles[int(num)][idx]))
 entries.sort()
 body=f'## {num}. {title}\n\n'+'\n'.join(f'- <a href="#pdf-page-{dest+1}">{html.escape(t)}</a>' for idx,dest,t in entries)
 replace(n,body,'Rebuilt section divider list from source annotation rectangles; removed false tables/navigation fragments. Source image retained.')
# Production injuries: separate source tables and source superscripts.
n=52
body='## Производственный травматизм (продолжение)\n\n'+para(n,(99,260,470,310))+'\n\n'+table(n,[116,319,367,414,465],[320,350,420,470,520,565])+'\n\n'+para(n,(480,260,1000,310))+'\n\n'+table(n,[490,817,877,940,990],[320,360,413,465,517,565])+'\n\n'+para(n,(1040,230,1650,325))+'\n\n'+para(n,(1040,325,1650,700))+'\n\n'+para(n,(95,785,1000,830))
replace(n,body,'Separated two independent injury tables; restored four columns and 3<sup>2</sup>; preserved all source footnotes and LTIFR callout.')
# Wage, fines, parental leave: explicitly bounded source tables, no invented gap column.
n=183
body='\n\n'.join([para(n,(95,140,850,225)),table(n,[99,600,700,790,850],[240,270,300,325,352,382,410,438,465,493,521,549,579],merged=[1,4,7]),para(n,(95,590,850,670)),table(n,[99,600,700,790,850],[680,710,775]),para(n,(880,140,1640,225)),table(n,[883,1400,1485,1575,1640],[240,270,307,330,350,372,395,415,435,457,479,501,522,542,578,602,627,650,704,730,754,775],merged=[1,5,9,13,17])])
replace(n,body,'Split three unrelated tables; restored year columns, full-width category rows and word законодательство; copied all values from source glyphs.')
# Innovation table missed by ruled-table detection.
n=165
replace(n,'## Приоритетные инновационные проекты 2026 года\n\n'+table(n,[468,750,1225,1580],[230,266,405,555])+'\n\n'+para(n,(760,580,1600,650)),'Restored the three-column/two-project table by inspected source cell bounds, preserving source glyphs.')
# Information security principles: source diagram flattened to an explicit list, image retains geometry.
n=170
boxes=[(110,260,330,340),(380,260,560,340),(650,260,830,340),(110,370,330,445),(650,370,830,445),(110,490,330,545),(650,490,830,545),(110,595,330,655),(650,595,830,655),(110,705,450,760),(500,705,830,760)]
replace(n,'## Принципы обеспечения информационной безопасности «Распадской»\n\n'+'\n'.join('- '+R(n,b) for b in boxes),'Grouped multiline labels of security-principles diagram; retained every principle and original diagram.')
# Explicit chart rows and labels: read values from source glyph regions.
def chart(n,titlebox,xs,ys):
 return para(n,titlebox)+'\n\n<table>\n<tr><th>Год</th><th>Значение</th></tr>\n'+ '\n'.join('<tr><td>'+R(n,(xs[0],a,xs[1],b))+'</td><td>'+R(n,(xs[1],a,xs[2],b))+'</td></tr>' for a,b in zip(ys,ys[1:]))+'\n</table>'
n=18
replace(n,para(n,(95,125,550,180))+'\n\n'+para(n,(95,185,550,330))+'\n\n'+chart(n,(570,185,1050,245),[570,625,1050],[255,300,345,380])+'\n\n'+para(n,(1060,100,1650,450)),'Bound chart years to emission-reduction values; preserved title, units and expenditure callout.')
n=54
replace(n,'\n\n'.join([para(n,(95,120,820,230))+'\n\n'+para(n,(95,230,820,325)),para(n,(95,335,395,775)),chart(n,(415,338,800,390),[415,470,800],[399,444,490,525]),para(n,(415,525,1050,800)),para(n,(95,800,1100,830))]),'Restored chart year/value associations and separated left-column health text, PPE callout and footnote.')
n=57
replace(n,'\n\n'.join([para(n,(95,120,950,235)),chart(n,(485,275,830,320),[485,535,850],[340,385,430,470]),chart(n,(485,485,830,532),[485,535,850],[550,595,640,680]),para(n,(870,285,1650,700)),para(n,(95,785,1650,830))]),'Separated two incident/production-object charts and their year/value rows; retained insurance amount and both footnotes.')
n=62
# Donut associations follow inspected legend colours, not angular estimation.
donut=[((1280,514,1390,536),(1520,480,1610,515)),((1280,537,1400,575),(1300,290,1390,325)),((1435,535,1560,575),(1425,265,1490,300))]
donut_table='<table>\n<tr><th>Категория</th><th>Доля, %</th></tr>\n'+'\n'.join('<tr><td>'+R(n,l)+'</td><td>'+R(n,v)+'</td></tr>' for l,v in donut)+'\n</table>'
replace(n,'\n\n'.join([para(n,(95,125,480,225)),chart(n,(95,230,480,265),[95,145,480],[278,323,369,402]),para(n,(495,230,870,265)), '<table><tr><th>Год</th><th>До 30 лет</th><th>От 30 до 50 лет</th><th>Старше 50 лет</th></tr>\n'+ '\n'.join('<tr>'+''.join('<td>'+R(n,(a,y,b,y+30))+'</td>' for a,b in zip([495,550,650,775],[550,650,775,870]))+'</tr>' for y in [278,323,369])+'</table>',para(n,(1270,230,1640,275)),donut_table,para(n,(95,803,900,830))]),'Bound personnel chart years, age groups and donut categories to their source values using legend colours; source footnote retained.')
n=89
percent_boxes=[(370,350,430,380),(125,465,175,498),(170,335,215,380),(210,310,255,335),(250,290,285,320),(285,290,320,320)]
rows=[]
for y,v in zip([370,393,416,439,462,485],percent_boxes):rows.append('<tr><td>'+R(n,(470,y,700,y+23))+'</td><td>'+R(n,v)+'</td></tr>')
replace(n,'\n\n'.join([para(n,(95,125,500,215)),para(n,(95,245,500,280)),'<table><tr><th>Направление</th><th>Доля, %</th></tr>\n'+'\n'.join(rows)+'\n</table>',para(n,(1010,330,1630,430)),table(n,[1040,1480,1630],[440,468,494,518,543,568,593,617,645])]),'Bound donut percentages to source legend categories and kept the separate expenditure table with its own units.')
n=118
replace(n,'\n\n'.join([para(n,(95,120,650,230)),para(n,(95,265,470,295)),chart(n,(95,300,470,333),[95,145,470],[345,390,435,470]),para(n,(95,495,470,525)),chart(n,(95,535,470,565),[95,145,470],[577,622,667,705]),para(n,(880,140,1650,200))+'\n\n'+para(n,(880,200,1525,410))+' '+R(n,(1525,350,1650,410))+'\n\n'+para(n,(880,415,1650,505))+'\n\n'+para(n,(880,505,1650,550))]),'Bound both water charts to their years; preserved water-abstraction change, explanation, units and source cross-reference.')
n=47
replace(n,'\n\n'.join(para(n,b) for b in [(90,130,485,780),(487,130,865,780),(875,130,1255,780),(1265,130,1650,780)]),'Restored four independent text columns; corrected interleaving of ventilation and gas-control sentences.')
n=99
replace(n,'\n\n'.join([para(n,(95,130,1650,225)),para(n,(95,245,615,325)),para(n,(95,340,615,565)),para(n,(630,245,1120,325)),para(n,(630,340,1120,565)),para(n,(1150,245,1650,325)),para(n,(1150,340,1650,565)),para(n,(95,790,1000,825))]),'Restored three conference columns, pairing each conference with its activities; retained footnote and logos in source image.')

# Native full-page body retained elsewhere; all unreviewed page statuses remain pending.
text='# Отчет об устойчивом развитии за 2025 год\n\n> Служебная информация: рабочая версия полного переноса 204 физических страниц. Полная постраничная сверка не завершена. Статусы и нерешённые места — в `_проверка/pages.json`; исходные изображения доступны у каждой страницы.\n\n'+''.join(f'<!-- pdf_page: {n} -->'+P[n] for n in range(1,205))
(ROOT/'report.md').write_text(text)
(ROOT/'_проверка/corrections.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
(ROOT/'_проверка/pages.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n')
print('written',len(text),'changes',len(changes))
