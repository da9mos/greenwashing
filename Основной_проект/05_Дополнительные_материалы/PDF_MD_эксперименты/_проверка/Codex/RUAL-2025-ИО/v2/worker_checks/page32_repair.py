exec(open('result/_проверка/repair.py').read().split("report=Path('result/report.md')")[0])
from collections import defaultdict,Counter
from bs4 import BeautifulSoup
report=Path('result/report.md');parts=re.split(r'(<!-- pdf_page: \d+ -->)',report.read_text());doc=pymupdf.open(src['source_pdf']);page=doc[31];w,h=page.rect.width,page.rect.height
units=[]
for bi,b in enumerate(page.get_text('rawdict')['blocks']):
 for li,l in enumerate(b.get('lines',[])):
  for sp in l['spans']:
   for c in sp.get('chars',[]):units.append({'id':len(units),'sequence':len(units),'line':(bi,li),'text':c['c'],'bbox':c['bbox'],'flags':sp['flags']})
assigned=set();audit=[]
def region(x0,y0,x1,y1):
 selected=[u for u in units if u['id'] not in assigned and x0<=(u['bbox'][0]+u['bbox'][2])/2/w<x1 and y0<=(u['bbox'][1]+u['bbox'][3])/2/h<y1]
 assigned.update(u['id'] for u in selected);audit.append({'rect_fraction':[x0,y0,x1,y1],'glyphs':len(selected)})
 return orig.render_glyphs(selected)
def table(edges,ys):
 rows=[]
 for a,b in zip(ys,ys[1:]):rows.append('<tr>'+''.join('<td>'+region(x0,a,x1,b)+'</td>' for x0,x1 in zip(edges,edges[1:]))+'</tr>')
 return '<table>\n'+'\n'.join(rows)+'\n</table>'
body=table([.04,.126,.28,.39,.445],[.13,.185,.515,.63,.932])+'\n\n'+table([.555,.638,.792,.904,.956],[.13,.185,.306,.448,.586,.683])
# Below-table prose in two columns; source lines remain intact.
body+='\n\n<p>'+region(.55,.683,.762,.92)+'</p>\n\n<p>'+region(.762,.683,.96,.92)+'</p>'
remaining=defaultdict(list)
for u in units:
 if u['id'] not in assigned:remaining[u['line']].append(u);assigned.add(u['id'])
body+='\n\n'+'\n\n'.join('<p>'+orig.render_glyphs(v)+'</p>' for v in remaining.values())
assert len(assigned)==len(units)
source=Counter(c for u in units for c in u['text'] if not c.isspace());rendered=Counter(c for c in BeautifulSoup(body,'html.parser').get_text() if not c.isspace());assert source==rendered
c=parts[64];m=re.search(r'<a id="pdf-page-32"></a>\s*',c);start=m.end();end=c.index('> Служебная пометка: распознанный',start);nextpart=c.index('> Служебная информация:',end)
extra='\n\n> Служебная информация: текст внутри пиктограмм ЦУР, прочитанный по изображению: «13 БОРЬБА С ИЗМЕНЕНИЕМ КЛИМАТА»; «8 ДОСТОЙНАЯ РАБОТА И ЭКОНОМИЧЕСКИЙ РОСТ»; «3 ХОРОШЕЕ ЗДОРОВЬЕ И БЛАГОПОЛУЧИЕ»; «11 УСТОЙЧИВЫЕ ГОРОДА И НАСЕЛЕННЫЕ ПУНКТЫ». Точная связь пиктограмм с продолжениями строк требует полной сверки.\n\n'
parts[64]=c[:start]+body+extra+c[nextpart:];report.write_text(''.join(parts));Path('result/_проверка/page32_regions.json').write_text(json.dumps({'page':32,'regions':audit,'all_glyphs_once':True,'rendered_character_inventory_matches':True,'review_status':'pending'},ensure_ascii=False,indent=2))
