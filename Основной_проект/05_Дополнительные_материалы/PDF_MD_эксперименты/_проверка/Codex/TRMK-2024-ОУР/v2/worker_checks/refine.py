from pathlib import Path
import sys,json,re,ast,html,collections,hashlib
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
import pymupdf
S=json.load(open('source.json')); D=pymupdf.open(S['source_pdf']); root=Path('result'); checks=root/'_проверка'
original=(checks/'baseline/report.md').read_text(); records=json.load(open(checks/'baseline/pages.json'))['pages']
# Reuse the verified glyph formatting and ordering helpers, not a second converter.
tool=Path(S['index']).parents[3]/'tools/native_candidate.py'
module=ast.parse(tool.read_text()); ns={'defaultdict':collections.defaultdict,'html':html}
for node in module.body:
 if isinstance(node,ast.FunctionDef) and node.name in ['render_glyphs','order_objects']:
  exec(compile(ast.Module(body=[node],type_ignores=[]),str(tool),'exec'),ns)
changes=[]; parts=[]
def normalize(t):return t.replace('\uf02d','Оглавление').replace('\uf0e4','↗').replace('\uf0e6','↘').replace('\x07','')
def repaired_table(page, xs, ys):
 units=[]
 for bi,b in enumerate(page.get_text('rawdict')['blocks']):
  for li,l in enumerate(b.get('lines',[])):
   for sp in l['spans']:
    for c in sp['chars']:
     units.append(dict(text=c['c'],bbox=c['bbox'],line=(bi,li),sequence=len(units),flags=sp['flags']))
 rows=[]
 for y0,y1 in zip(ys,ys[1:]):
  cells=[]
  for x0,x1 in zip(xs,xs[1:]):
   cell=[u for u in units if x0<=(u['bbox'][0]+u['bbox'][2])/2<x1 and y0<=(u['bbox'][1]+u['bbox'][3])/2<y1]
   cells.append('<td>'+ns['render_glyphs'](cell)+'</td>')
  rows.append('<tr>'+''.join(cells)+'</tr>')
 return '<table>\n'+'\n'.join(rows)+'\n</table>'
def group_objects(objects,page):
 lookup={}
 for bi,b in enumerate(page.get_text('dict')['blocks']):
  for li,l in enumerate(b.get('lines',[])):
   lookup[tuple(round(v,1) for v in l['bbox'])]=bi
 grouped=[]; groups={}
 for o in objects:
  if o['kind']!='text':grouped.append(o);continue
  key=lookup.get(tuple(round(v,1) for v in o['bbox']))
  if key is None:grouped.append(o);continue
  # Source blocks can contain separate columns: preserve separate runs.
  key=(key, int(o['bbox'][0]//623), round(o['bbox'][0]/35))
  if key not in groups:groups[key]=[]
  groups[key].append(o)
 for values in groups.values():
  values.sort(key=lambda v:(v['bbox'][1],v['bbox'][0]))
  grouped.append({'kind':'text','bbox':[min(v['bbox'][0] for v in values),min(v['bbox'][1] for v in values),max(v['bbox'][2] for v in values),max(v['bbox'][3] for v in values)],'text':'<p>'+'<br/>'.join(v['text'][3:-4] for v in values)+'</p>'})
 return grouped

def layout(objs,offset=0):
 if len(objs)<2:return objs
 # Identify spanning objects, then read the columns between those bands.
 candidates=[290,355] if offset==0 else [894,956]
 narrow=[o for o in objs if 60<o['bbox'][2]-o['bbox'][0]<270]
 gutter=min(candidates,key=lambda g:sum(o['bbox'][0]<g-5 and o['bbox'][2]>g+5 for o in narrow))
 spans=sorted([o for o in objs if o['bbox'][0]<gutter-5 and o['bbox'][2]>gutter+5],key=lambda o:o['bbox'][1])
 for span in spans:
  a=[o for o in objs if o is not span and o['bbox'][3]<=span['bbox'][1]+2]
  b=[o for o in objs if o is not span and o['bbox'][1]>=span['bbox'][3]-2]
  if len(a)+len(b)+1==len(objs):
   return layout(a,offset)+[span]+layout(b,offset)
 left=[o for o in objs if o['bbox'][0]<gutter];right=[o for o in objs if o['bbox'][0]>=gutter]
 if left and right and not spans:return ns['order_objects'](left)+ns['order_objects'](right)
 return ns['order_objects'](objs)

for n,section in re.findall(r'<!-- pdf_page: (\d+) -->(.*?)(?=<!-- pdf_page:|\Z)',original,re.S):
 n=int(n);r=records[n-1];p=D[n-1]
 content=section.split('</a>',1)[1]
 cut=len(content)
 for token in ['> Служебная пометка:', '> Служебная информация:', '<details>']:
  if token in content:cut=min(cut,content.index(token))
 native=content[:cut]
 markup=re.findall(r'<p>.*?</p>|<table>.*?</table>',native,re.S)
 assert len(markup)==len(r['objects']),(n,len(markup),len(r['objects']))
 objs=[dict(o,text=t) for o,t in zip(r['objects'],markup)]
 nav=[];footer=[];body=[]
 for o in objs:
  if n not in [1,2,3,4,128] and o['bbox'][3]<65:nav.append(o)
  elif n not in [1,2,128] and o['bbox'][1]>765:footer.append(o)
  else:body.append(o)
 # Address the three visually inspected faulty table geometries by source positions.
 if n in [8,31,35]:
  if n==8:
   for o in body:
    if o['kind']=='table':
     y=o['bbox'][1]
     if 330<y<600:o['text']=repaired_table(p,[708,758,1014,1095,1206],[338,373,391,409,427,445,463,481,499,517,535,553,571,589])
     elif y>600:o['text']=repaired_table(p,[708,758,1014,1095,1206],[638,673,691,709,727,746])
  else:
   if n==31:xs=[42,106,234,410,539];ys=[141,175,349,613,676]
   else:xs=[708,820,1010,1206];ys=[543,567,637,685]
   ts=[o for o in body if o['kind']=='table' and o['bbox'][0]<(600 if n==31 else 1210)]
   assert len(ts)==1
   ts[0]['text']=repaired_table(p,xs,ys)
  if n==8:
   for o in body:
    if o['kind']!='table':continue
    soup=BeautifulSoup(o['text'],'html.parser');rows=soup.find_all('tr')
    groups=[(1,4,'1'),(5,8,'2')] if len(rows)==13 else [(1,4,'3')]
    for start,count,label in groups:
     first=rows[start].find_all('td',recursive=False)[0];first.string=label;first['rowspan']=str(count)
     for row in rows[start+1:start+count]:row.find_all('td',recursive=False)[0].decompose()
    o['text']=str(soup)
  changes.append({'page':n,'object':'table geometry','action':'Cells reconstructed from original glyphs using visually established column and semantic row boundaries; no numeric rewriting.'})
 if n==117:
  old=next(o for o in body if o['kind']=='table' and o['bbox'][0]<100 and o['bbox'][1]<200)
  soup=BeautifulSoup(old['text'],'html.parser');rows=soup.find_all('tr');split=[]
  for lo,hi,box in [(0,4,[42,173,258,399]),(5,9,[323,173,539,399])]:
   trs=[]
   for row in rows:
    cells=row.find_all('td',recursive=False);assert len(cells)==9
    assert not cells[4].get_text(strip=True)
    trs.append('<tr>'+''.join(str(c) for c in cells[lo:hi])+'</tr>')
   split.append(dict(kind='table',bbox=box,text='<table>\n'+'\n'.join(trs)+'\n</table>'))
  body.remove(old);body.extend(split)
  changes.append({'page':n,'object':'two independent emission tables','action':'Split accidental joint grid into two tables; removed verified whitespace separator column. All native data retained.'})
 if n==120:
  obj=next(o for o in body if o['kind']=='table' and o['bbox'][0]<100 and 240<o['bbox'][1]<300)
  soup=BeautifulSoup(obj['text'],'html.parser');rows=soup.find_all('tr')
  for i,row in enumerate(rows):
   cells=row.find_all('td',recursive=False)
   if i==1:
    assert not cells[2].get_text(strip=True);cells[2].decompose()
   elif i==5:cells[-1]['colspan']='3'
   else:
    assert len(cells)==8 and not cells[5].get_text(strip=True);cells[5].decompose()
  obj['text']=str(soup)
  changes.append({'page':n,'object':'employment contract table','action':'Removed artificial empty column after checking source seven-column layout; restored both three-year group headers. All native data retained.'})
 body=group_objects(body,p)
 if p.rect.width>1000:
  left=[o for o in body if (o['bbox'][0]+o['bbox'][2])/2<623.62];right=[o for o in body if o not in left]
  body=layout(left)+layout(right,538.6)
 else:body=ns['order_objects'](body)
 bodytext='\n\n'.join(o['text'] for o in body)
 # The glyph inventory must remain unchanged for all unmodified body tables.
 if n not in [8,31,35,117,120]:
  expected=collections.Counter(BeautifulSoup(''.join(o['text'] for o in objs if o not in nav and o not in footer),'html.parser').get_text())
  actual=collections.Counter(BeautifulSoup(bodytext,'html.parser').get_text())
  assert {k:v for k,v in expected.items() if not k.isspace()}=={k:v for k,v in actual.items() if not k.isspace()},(n,expected-actual,actual-expected)
 links=''
 if '> Служебная информация: ссылки исходного PDF' in section:
  links=section[section.index('> Служебная информация: ссылки исходного PDF'):section.index('<details>')].strip()
 furniture=''
 if nav or footer:
  furniture='<details>\n<summary>Навигация и колонтитулы исходной страницы</summary>\n\n'+'\n\n'.join(o['text'] for o in nav+footer)+'\n\n</details>'
 status=''
 checked=n in [1,2,4,5,128]
 r['conversion_status']='converted';r['review_status']='checked' if checked else 'pending';r['semantic_source_review_completed']=checked
 r['verification_scope']='Full visual source reading' if checked else 'Unicode glyph crops checked; native block regrouping and page geometry; full semantic source review pending'
 r['diagnostic_review']={'unicode':'checked' if r['unresolved_unicode'] else 'not_applicable','ambiguous_cell_assignments':'none' if not r['ambiguous_cell_assignments'] else 'pending','table_detection_error':'none' if not r['table_detection_error'] else 'pending'}
 r['unresolved_unicode']=0
 r['issues']=[] if checked else ['Полная построчная сверка страницы по оригиналу не завершена; порядок блоков и связи данных требуют проверки.']
 if r['tables'] and not checked:r['issues'].append('Не все ячейки и объединения таблиц сверены по оригиналу; исходное изображение сохранено.')
 if r.get('ocr_chars'):
  r['ocr_review']='Residual OCR output rejected: duplicates of native text and decorative artifacts; source images inspected. Full page acceptance is separate.'
  changes.append({'page':n,'object':'residual OCR','action':'Removed detached duplicated/native and decorative OCR fragments, retained native body text and full source image.'})
 if not checked:status='> Служебная пометка: converted / pending — полная сверка порядка чтения, таблиц и графики по оригиналу не завершена.\n\n'
 parts.append(f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+status+normalize(bodytext)+'\n\n'+normalize(furniture)+'\n\n'+normalize(links)+f'\n\n<details>\n<summary>Источник: PDF-страница {n}</summary>\n\n![Полная исходная страница {n}](assets/page_{n:04d}.png)\n\n</details>')
 r['printed_designations']=[BeautifulSoup(o['text'],'html.parser').get_text() for o in footer if re.fullmatch(r'\d+',BeautifulSoup(o['text'],'html.parser').get_text().strip())]
 r['content_type']='native text with tables/graphics' if r['tables'] else ('native text with source graphics')
 if r['tables']:r['conversion_notes']=['Mechanical table geometry retained except documented repairs; visual review pending.']
 (checks/'pages.json').write_text(json.dumps({'pages':records},ensure_ascii=False,indent=2)+'\n')
report='# ОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ 2024\n\n> Служебная информация: рабочая версия полного переноса 128 физических страниц. Текстовый слой, таблицы и исходные изображения сохранены; полная сверка документа по оригиналу не завершена. Статусы по каждой странице — в `_проверка/pages.json`.\n\n'+'\n\n'.join(parts)+'\n'
(root/'report.md').write_text(report)
(checks/'changes.json').write_text(json.dumps({'changes':changes,'global_changes':['Preserved baseline before refinement','Resolved 121 native Unicode diagnostic occurrences by inspecting all source glyph crops','Replaced contents pictogram with Оглавление, corrected page 8 arrows, removed invisible control code','Regrouped native lines by PDF text block while retaining glyph content','Separated running navigation and footers from reading body','Page-local pending notes retained; only pages 1,2,4,5,128 accepted after source reading']},ensure_ascii=False,indent=2)+'\n')
print('Wrote',len(parts),'pages; chars',len(report))
