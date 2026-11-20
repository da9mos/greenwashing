import sys,json,importlib.util,types,re,shutil,hashlib
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import fitz
src=json.load(open('source.json')); tool=Path(src['index']).parents[3]/'tools/native_candidate.py'
spec=importlib.util.spec_from_file_location('native',tool); native=importlib.util.module_from_spec(spec); spec.loader.exec_module(native)
d=fitz.open(src['source_pdf']); report=Path('result/report.md'); shutil.copy2(report,'result/_проверка/report.before_review.md'); parts=re.split(r'(?=<!-- pdf_page: \d+ -->)',report.read_text()); changes=[]
# Correct the diagnosed spread-wide table inference with source horizontal rules.
def corrected_tables(p,half,ymin,ymax,xs):
 seg=[]; edges=[ymin,ymax]
 for dr in p.get_drawings():
  for it in dr['items']:
   if it[0]=='l':
    a,b=it[1],it[2]
    if abs(a.y-b.y)<.1 and min(a.x,b.x)>=xs[0]-.2 and max(a.x,b.x)<=xs[-1]+.2 and ymin<a.y<ymax:
     seg.append((a.y,min(a.x,b.x),max(a.x,b.x))); edges.append(a.y)
   elif it[0]=='re':
    r=it[1]
    if dr.get('fill') and abs(r.x0-xs[0])<2 and abs(r.x1-xs[-1])<2:
     for y in [r.y0,r.y1]:
      if ymin<y<ymax: edges.append(y); seg.append((y,xs[0],xs[-1]))
 ys=[]
 for y in sorted(edges):
  if not ys or y-ys[-1]>.5: ys.append(y)
 # source text lines that cross a column boundary identify section rows
 lines=[l for b in p.get_text('dict')['blocks'] for l in b.get('lines',[]) if xs[0]<=l['bbox'][0]<xs[-1]]
 rows=[types.SimpleNamespace(cells=[None]*4) for _ in range(len(ys)-1)]
 occupied=set()
 for ri,(y0,y1) in enumerate(zip(ys,ys[1:])):
  crossing=any(y0<=(l['bbox'][1]+l['bbox'][3])/2<y1 and any(l['bbox'][0]<x-1 and l['bbox'][2]>x+1 for x in xs[1:-1]) for l in lines)
  if crossing:
   rows[ri].cells[0]=(xs[0],y0,xs[-1],y1)
   occupied.update((ri,c) for c in range(4)); continue
  for ci in range(4):
   if (ri,ci) in occupied: continue
   end=ri+1; mid=(xs[ci]+xs[ci+1])/2
   while end<len(ys)-1 and not any(abs(y-ys[end])<.5 and x0-.2<=mid<=x1+.2 for y,x0,x1 in seg):
    # do not merge into a section row
    if any(ys[end]<=(l['bbox'][1]+l['bbox'][3])/2<ys[end+1] and any(l['bbox'][0]<x-1 and l['bbox'][2]>x+1 for x in xs[1:-1]) for l in lines): break
    end+=1
   rows[ri].cells[ci]=(xs[ci],y0,xs[ci+1],ys[end]); occupied.update((r,ci) for r in range(ri,end))
 return types.SimpleNamespace(bbox=(xs[0],ymin,xs[-1],ymax),rows=rows)
newinfo={}
for n in range(90,96):
 p=d[n-1]; regions=[]
 if n==90:
  # declaration is a distinct two-column table; preserve its source detector result
  regions.extend(p.find_tables(clip=fitz.Rect(30,120,540,200),strategy='lines').tables)
  regions.append(corrected_tables(p,0,229.004,759.08,[36.85,76.535,202.203,395.15,532.914]))
  regions.append(corrected_tables(p,1,129.807,784.21,[657.638,697.323,822.991,1015.937,1153.701]))
 else:
  # grid endpoints vary slightly across source pages; retain source line endpoints
  for half in [0,1]:
   seg=[it for dr in p.get_drawings() for it in dr['items'] if it[0]=='l' and abs(it[1].y-it[2].y)<.1 and min(it[1].x,it[2].x)>half*p.rect.width/2 and max(it[1].x,it[2].x)<(half+1)*p.rect.width/2 and it[1].y>75 and abs(it[1].x-it[2].x)>20]
   from collections import Counter
   pts=Counter(round(x,1) for it in seg for x in [it[1].x,it[2].x]); xs=sorted(x for x,c in pts.items() if c>=3)
   # GRI's four source columns. SASB uses a different grid on the lower right of 95.
   if len(xs)!=5: print('GRID',n,half,pts); xs=([36.85,78.22,202.2,395.15,532.914] if half==0 else [657.638,699.01,822.99,1015.48,1153.701])
   end=max(it[1].y for it in seg)
   if n==95 and half==1:
    regions.append(corrected_tables(p,half,74.837,330,[657.638,699.01,822.99,1015.48,1153.701]))
    # retain native detector for the separate SASB table
    regions.extend(p.find_tables(clip=fitz.Rect(650,420,1160,800),strategy='lines').tables)
   else: regions.append(corrected_tables(p,half,74.837,end,xs))
 class Proxy:
  def get_text(self,*a,**kw): return p.get_text(*a,**kw)
  def find_tables(self,**kw): return types.SimpleNamespace(tables=regions)
 body,info=native.convert_page(Proxy()); newinfo[n]=info
 old=parts[n]; tail=old[old.index('<details>'):]; links=old[old.index('> Служебная информация: ссылки исходного PDF'):] if '> Служебная информация: ссылки исходного PDF' in old else ''
 parts[n]=f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+body+'\n\n'+tail
 changes.append({'page':n,'action':'Rebuilt diagnosed table geometry from source horizontal rule segments, separating spread halves; native glyph assignment and character accounting pass. Full semantic cell review remains pending.'})
# Replace only source-confirmed invalid glyph classes. Colored legend markers retain color from native spans.
s=''.join(parts)
s=s.replace('\x03','').replace('\x02','')
for n in range(1,116):
 piece=re.search(r'<!-- pdf_page: '+str(n)+r' -->.*?(?=<!-- pdf_page: |\Z)',s,re.S).group()
 colors=[sp['color'] for b in d[n-1].get_text('dict')['blocks'] for l in b.get('lines',[]) for sp in l['spans'] for c in sp['text'] if c=='\ue804']
 for color in colors: piece=piece.replace('\ue804',f'<span style="color:#{color:06x}">●</span>',1)
 s=re.sub(r'<!-- pdf_page: '+str(n)+r' -->.*?(?=<!-- pdf_page: |\Z)',lambda m:piece,s,count=1,flags=re.S)
s=s.replace(parts[0],'# Отчет об устойчивом развитии 2025\n\n> Служебная информация: рабочая конвертация всех 115 физических страниц. Полная сверка содержания, порядка чтения, таблиц и диаграмм не завершена; реестр — `_проверка/pages.json`. Исходные страницы приложены для визуальной опоры.\n\n',1)
s=s.replace('<p>Отчет</p>\n\n<p>об устойчивом</p>\n\n<p>развитии</p>','<p>Отчет об устойчивом развитии</p>')
# cover's logo is graphical text, read visually
s=s.replace('<a id="pdf-page-1"></a>','<a id="pdf-page-1"></a>\n\n<p>ТМК</p>',1)
# source-confirmed blank reverse cover
s=s.replace('<a id="pdf-page-115"></a>','<a id="pdf-page-115"></a>\n\n<!-- Задняя обложка: однотонное зеленое поле, текста нет. -->',1)
report.write_text(s)
json.dump(newinfo,open('result/_проверка/review/repaired_table_accounting.json','w'),ensure_ascii=False,indent=2)
json.dump(changes,open('result/_проверка/review/changes.json','w'),ensure_ascii=False,indent=2)
print('saved',len(s),'characters')
