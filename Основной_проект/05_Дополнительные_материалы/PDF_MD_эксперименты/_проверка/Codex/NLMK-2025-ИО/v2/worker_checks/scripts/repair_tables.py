import sys,json,html,re,collections,importlib.util,pathlib
sys.path.insert(0,'/private/tmp/sber-pdf-libs');sys.path.insert(0,'/private/tmp/sber-diff-libs')
import pymupdf as fitz
from bs4 import BeautifulSoup
ROOT=pathlib.Path(__file__).resolve().parents[3]
SRC=json.loads((ROOT/'source.json').read_text())
spec=importlib.util.spec_from_file_location('native',str(pathlib.Path(SRC['source_pdf']).parents[1]/'tools/native_candidate.py'));native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
pdf=fitz.open(SRC['source_pdf'])
# Targeted repairs only: column boundaries and body extents read from original PDF rules.
configs={115:[([733.9,839.3,1077.4,1139.8,1306.4],250,781.08)],116:[([53.9,159.3,397.4,459.8,626.4],90,794.52),([734.2,839.6,1077.7,1140.1,1306.7],90,764.39)],118:[([53.9,159.3,397.4,459.8,626.4],90,701.70),([734.2,839.6,1077.7,1140.1,1306.7],90,558.61)],119:[([53.9,291.7,508.6,626.5],132,751.90),([734.2,960.3,1239.8,1306.8],132,771.48)],125:[([53.9,110.0,435.1,626.5],90,767.96),([734.2,790.3,1115.4,1306.8],90,791.30)]}
def repair(n):
 pg=pdf[n-1];units=[]
 for bi,b in enumerate(pg.get_text('rawdict')['blocks']):
  for li,l in enumerate(b.get('lines',[])):
   for s in l['spans']:
    for c in s.get('chars',[]):units.append(dict(id=len(units),sequence=len(units),line=(bi,li),bbox=c['bbox'],text=c['c'],flags=s['flags']))
 out=[]; used=set();stats=[]
 for xs,top,bottom in configs[n]:
  segments=[]
  for d in pg.get_drawings():
   for it in d['items']:
    if it[0]!='l':continue
    a,b=it[1:];x0,x1=sorted([a.x,b.x]);y=a.y
    if abs(a.y-b.y)>.1 or not top<y<bottom+.5:continue
    if min(abs(x0-x) for x in xs)<.75 and min(abs(x1-x) for x in xs)<.75 and x1-x0>30:segments.append((x0,y,x1))
  ys=sorted(set([top,bottom]+[round(y,2) for _,y,_ in segments]));ys=[v for i,v in enumerate(ys) if not i or v-ys[i-1]>.5]
  percol=[]
  for j in range(len(xs)-1):
   xc=(xs[j]+xs[j+1])/2;percol.append([0]+[i for i,y in enumerate(ys[1:-1],1) if any(a-.2<xc<b+.2 and abs(z-y)<.1 for a,z,b in segments)]+[len(ys)-1])
  selected=[u for u in units if xs[0]-.5<((u['bbox'][0]+u['bbox'][2])/2)<xs[-1]+.5 and top<((u['bbox'][1]+u['bbox'][3])/2)<bottom]
  lines=collections.defaultdict(list)
  for u in selected:lines[u['line']].append(u)
  fullrows=set()
  for us in lines.values():
   x0=min(u['bbox'][0] for u in us);x1=max(u['bbox'][2] for u in us);yc=sum((u['bbox'][1]+u['bbox'][3])/2 for u in us)/len(us)
   if any(x0<x-2 and x1>x+2 for x in xs[1:-1]):
    ri=max(i for i,y in enumerate(ys[:-1]) if y<=yc);fullrows.add(ri)
  # Source section headings have no separate column associations.
  for ri in fullrows:
   for es in percol:
    if ri not in es:es.append(ri)
    if ri+1 not in es:es.append(ri+1)
    es.sort()
  rows=[]
  for ri in range(len(ys)-1):
   cells=[]
   if ri in fullrows:
    us=[u for u in selected if ys[ri]<=((u['bbox'][1]+u['bbox'][3])/2)<ys[ri+1]]
    cells=[f'<td colspan="{len(xs)-1}">'+native.render_glyphs(us)+'</td>'];used.update(u['id'] for u in us)
   else:
    for j,es in enumerate(percol):
     if ri not in es:continue
     end=es[es.index(ri)+1] if es.index(ri)+1<len(es) else ri+1
     us=[u for u in selected if xs[j]-.5<=((u['bbox'][0]+u['bbox'][2])/2)<xs[j+1]-.5 and ys[ri]<=((u['bbox'][1]+u['bbox'][3])/2)<ys[end]]
     cells.append(f'<td rowspan="{end-ri}">'+native.render_glyphs(us)+'</td>');used.update(u['id'] for u in us)
   rows.append('<tr>'+''.join(cells)+'</tr>')
  expected={u['id'] for u in selected};assert expected<=used,(n,expected-used)
  out.append(dict(bbox=[xs[0],top,xs[-1],bottom],text='<table>\n'+'\n'.join(rows)+'\n</table>'))
  stats.append(dict(bbox=out[-1]['bbox'],rows=len(rows),columns=len(xs)-1,source_glyphs=len(selected)))
 remaining=collections.defaultdict(list)
 for u in units:
  if u['id'] not in used:remaining[u['line']].append(u)
 for us in remaining.values():out.append(dict(bbox=[min(u['bbox'][0] for u in us),min(u['bbox'][1] for u in us),max(u['bbox'][2] for u in us),max(u['bbox'][3] for u in us)],text='<p>'+native.render_glyphs(us)+'</p>'))
 body='\n\n'.join(o['text'] for o in native.order_objects(out))
 expected=collections.Counter(c for u in units for c in u['text'] if not c.isspace());actual=collections.Counter(c for c in BeautifulSoup(body,'html.parser').get_text() if not c.isspace());assert expected==actual,(n,expected-actual,actual-expected)
 return body,stats
if __name__=='__main__':
 s=(ROOT/'result/report.md').read_text();log={}
 for n in configs:
  pattern=r'(<!-- pdf_page: '+str(n)+r' -->\n<a id="pdf-page-'+str(n)+r'"></a>\n)(.*?)(?=<!-- pdf_page:|\Z)'
  m=re.search(pattern,s,re.S);old=m[2];suffix=old[old.index('> Служебная информация: ссылки исходного PDF'):] if '> Служебная информация: ссылки исходного PDF' in old else old[old.index('<details>'):]
  body,log[n]=repair(n);s=s[:m.start(2)]+'\n'+body+'\n\n'+suffix+s[m.end(2):]
 (ROOT/'result/report.md').write_text(s)
 (ROOT/'result/_проверка/table_repairs.json').write_text(json.dumps(log,ensure_ascii=False,indent=2))
