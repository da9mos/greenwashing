"""Addressed repairs to the existing candidate. Grid boundaries read from source drawings and page images.
Uses the supplied native converter's glyph serializer; no OCR/API/model-generated numeric data.
"""
from pathlib import Path
import sys,json,re,importlib.util,hashlib,html,collections
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf as fitz
from bs4 import BeautifulSoup
base=Path('result'); check=base/'_проверка'
spec=importlib.util.spec_from_file_location('native','/Users/nikitachukreev/Documents/Документы — MacBook Pro — Nikita/Система/11_Проект_Сбер/2_итерация/Тесты_PDF_в_MD_DeepSeek_Codex/tools/native_candidate.py'); native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
s=(base/'report.md').read_text(); chunks={int(m[1]):m[2] for m in re.finditer(r'<!-- pdf_page: (\d+) -->(.*?)(?=<!-- pdf_page:|\Z)',s,re.S)}
source=json.load(open('source.json'));doc=fitz.open(source['source_pdf']); audit=[]; selected={}; used={}
def prepare(n):
 units=[]
 for bi,b in enumerate(doc[n-1].get_text('rawdict')['blocks']):
  for li,l in enumerate(b.get('lines',[])):
   for sp in l['spans']:
    for ch in sp['chars']:
     units.append({'id':len(units),'sequence':len(units),'block':bi,'line':(bi,li),'text':'•' if sp['font']=='Wingdings2-SC700' and ch['c']=='y' else ch['c'],'bbox':ch['bbox'],'flags':sp['flags']})
 selected[n]=units;used[n]=collections.Counter()
def box(n,r):
 vals=[u for u in selected[n] if r[0]<=(u['bbox'][0]+u['bbox'][2])/2<r[2] and r[1]<=(u['bbox'][1]+u['bbox'][3])/2<r[3]]
 used[n].update(u['id'] for u in vals)
 return native.render_glyphs(vals)
def para(n,r):return '<p>'+box(n,r)+'</p>'
def grid(n,xs,ys,merges=None):
 merges=merges or {}; skip=set();out=['<table>']
 for ri in range(len(ys)-1):
  out.append('<tr>')
  for ci in range(len(xs)-1):
   if (ri,ci) in skip:continue
   rs,cs=merges.get((ri,ci),(1,1))
   for rr in range(ri,ri+rs):
    for cc in range(ci,ci+cs):
     if (rr,cc)!=(ri,ci):skip.add((rr,cc))
   out.append(f'<td rowspan="{rs}" colspan="{cs}">'+box(n,[xs[ci],ys[ri],xs[ci+cs],ys[ri+rs]])+'</td>')
  out.append('</tr>')
 out.append('</table>');return '\n'.join(out)
def commit(n,body,description):
 # Keep existing source link annotations and full-page visual assets.
 c=chunks[n];tail=c[c.index('<details>'):]
 links=''
 if '> Служебная информация: ссылки исходного PDF' in c:links=c[c.index('> Служебная информация: ссылки исходного PDF'):c.index('<details>')]
 # Prove that all native body characters in the repaired areas survive once.
 missing=[u for u in selected[n] if u['id'] not in used[n] and 75<(u['bbox'][1]+u['bbox'][3])/2<790]
 duplicate=[k for k,v in used[n].items() if v!=1]
 # Excluded regions consist of already-established navigation/footers only, or must be retained.
 if missing:
  body+='\n\n> Служебная пометка: дополнительные исходные текстовые элементы вне восстановленной сетки (порядок требует проверки).\n\n<p>'+native.render_glyphs(missing)+'</p>'
  used[n].update(u['id'] for u in missing)
 if duplicate:raise ValueError((n,'duplicate glyph IDs',duplicate[:20]))
 chunks[n]=f'\n<a id="pdf-page-{n}"></a>\n\n> Служебная пометка: converted / pending — полная сверка этой страницы по оригиналу не завершена. Геометрия указанных таблиц восстановлена по исходным линиям и изображению.\n\n{body}\n\n{links}{tail}'
 audit.append({'pdf_page':n,'repair':description,'method':'Границы ячеек заданы по оригинальным линиям и визуально просмотренному изображению; содержимое ячеек сериализовано функцией render_glyphs общей программы native_candidate.py.','body_glyph_ids_used_once':not duplicate,'retained_outside_grid_glyphs':len(missing),'review_status':'pending'})
# 35: one table spanning both printed pages, not two unrelated tables with empty columns.
n=35;prepare(n)
body='## '+box(n,[45,85,548,125])+'\n\n'
ys=[140,167.5,258.24,365.95,483.31,637.51,769.04]
left=[45,156.85,301.04,547];right=[643,893.42,1147]
rows=[]
for i in range(len(ys)-1):
 cells=[box(n,[left[j],ys[i],left[j+1],ys[i+1]]) for j in range(3)]+[box(n,[right[j],ys[i],right[j+1],ys[i+1]]) for j in range(2)]
 rows.append('<tr>'+''.join('<td>'+x+'</td>' for x in cells)+'</tr>')
body+='<table>\n'+'\n'.join(rows)+'\n</table>';commit(n,body,'Соединены пять столбцов карты заинтересованных сторон на развороте, восстановлены пять строк групп ЗС.')
# 152: labels and six enterprise columns belong to the same rows across the spread.
n=152;prepare(n)
body=para(n,[118,90,548,170])+'\n\n'
ys=[182,213.7]+sorted({round(item[1].y,2) for dr in doc[n-1].get_drawings() for item in dr['items'] if item[0]=='l' and abs(item[1].y-item[2].y)<.1 and 232<item[1].y<764})
left=[45,380.55,459.07,548];right=[643,727.09,809.79,892.49,975.19,1057.89,1146]
rows=[]
for i in range(len(ys)-1):
 cells=[box(n,[left[j],ys[i],left[j+1],ys[i+1]]) for j in range(3)]+[box(n,[right[j],ys[i],right[j+1],ys[i+1]]) for j in range(6)]
 rows.append('<tr>'+''.join('<td>'+x+'</td>' for x in cells)+'</tr>')
body+='<table>\n'+'\n'.join(rows)+'\n</table>\n\n'+para(n,[45,775,548,800])+'\n\n'+para(n,[1060,775,1147,800])
commit(n,body,'Собраны девять столбцов единой таблицы ОТиПБ с привязкой всех 26 строк к показателю, коэффициенту, единице и предприятию; сохранены надстрочные 13–14 и обе сноски.')
# 156: four independent acronym/expansion columns.
n=156;prepare(n);body='## '+box(n,[45,85,548,130])+'\n\n'
for x0,xm,x1 in [(45,96.7,291),(303,354.66,549),(643,694.81,889),(900,952.04,1147)]:
 ys=sorted({round(item[1].y,2) for dr in doc[n-1].get_drawings() for item in dr['items'] if item[0]=='l' and abs(item[1].y-item[2].y)<.1 and abs(min(item[1].x,item[2].x)-x0)<1 and item[1].y>150})
 body+=grid(n,[x0,xm,x1],ys)+'\n\n'
commit(n,body,'Восстановлены четыре самостоятельных двухколоночных списка сокращений, связи каждой аббревиатуры с расшифровкой и порядок колонок.')
# 118: biota table.
n=118;prepare(n)
body=para(n,[118,95,548,165])+'\n\n'+para(n,[45,175,548,198])+'\n\n'+grid(n,[45,129.45,548],[205,226.6,262.20,309.26,345.54,381.26,464.60,558.71,643.18,678.65])
body+='\n\n'+para(n,[643,95,1147,137])+'\n\n'+para(n,[643,145,855,310])+'\n\n'+para(n,[864,145,1147,310]);commit(n,body,'Убраны фиктивные строки/колонки в таблице биоты; текст результатов сохранён в соответствующей категории. Восстановлены две колонки следующей печатной страницы.')
# 127: volunteering table; preserve left page in explicit column order.
n=127;prepare(n)
body=para(n,[118,95,325,400])+'\n\n'+para(n,[339,95,548,400])+'\n\n'+para(n,[118,420,548,450])+'\n\n'+para(n,[118,460,325,720])+'\n\n'+para(n,[339,460,548,720])
body+='\n\n'+para(n,[643,95,1147,135])+'\n\n'+para(n,[643,145,855,340])+'\n\n'+para(n,[864,145,1147,340])+'\n\n'+para(n,[643,355,1147,376])+'\n\n'+grid(n,[643,736.87,912.05,1147],[380,403,486.71,581.95,677.20,724.82,784.35]);commit(n,body,'Восстановлены три столбца и пять направлений волонтёрства; сохранены тексты соседних блоков в порядке колонок.')
# 21: board committee table.
n=21;prepare(n)
body=para(n,[100,95,548,123])+'\n\n'+grid(n,[45,99.78,303.31,437.95,549],[123,163,184,309.83,797.70])
body+='\n\n'+para(n,[643,95,1147,137])+'\n\n'+para(n,[643,145,855,460])+'\n\n'+para(n,[864,145,1147,460]);commit(n,body,'Восстановлены категории и три комитета, годы, заседания и вопросы; удалены ложные колонки детектора.')
# 14: right-page project table has an intentionally empty third column.
n=14;prepare(n)
body=para(n,[118,100,325,460])+'\n\n'+para(n,[339,100,548,460])+'\n\n'+para(n,[643,95,1147,170])+'\n\n'+para(n,[643,180,855,280])+'\n\n'+para(n,[864,180,1147,280])+'\n\n'+para(n,[643,299,1147,317])
body+='\n\n'+grid(n,[643,924.09,1058.74,1147],[317,344.5,367,560.53,692.06,797.54],{(1,0):(1,3)})
commit(n,body,'Собраны описание, результат и намеренно пустая колонка подробной информации для трёх проектов; восстановлен объединённый заголовок категории.')
# 120: the first category spans three subcategories.
n=120;prepare(n)
body=para(n,[45,85,549,200])+'\n\n'+grid(n,[45,179.15,252.85,548],[203,369.35,512.22,595.56,750.08],{(0,0):(3,1),(3,1):(1,2)})+'\n\n'+grid(n,[643,777.83,1147],[203,310.08,369.60,452.69]);commit(n,body,'Восстановлены планы природоохранной деятельности с общей категорией для трёх направлений и отдельными проектами на правой половине разворота.')
# 79: right-side chart and occupational-disease table.
n=79;prepare(n)
body=para(n,[118,105,325,470])+'\n\n'+para(n,[339,95,548,470])+'\n\n'+para(n,[118,480,548,520])+'\n\n'+para(n,[118,530,325,740])+'\n\n'+para(n,[339,530,548,740])+'\n\n'+para(n,[643,105,855,470])
body+='\n\n'+para(n,[875,105,1147,140])+'\n\n'+native_table if False else body
# Exact chart values and labels come from geometry, not numeric transcription.
body+='\n\n'+para(n,[875,105,1147,140])+'\n\n'+grid(n,[875,895,1147],[140,159.62,181.17,202.43])+'\n\n'+para(n,[875,235,1147,290])+'\n\n'+grid(n,[875,1038.9,1092.05,1147],[298,318.31,349.20,369.09,388.98]);commit(n,body,'Диаграмма профессиональной заболеваемости отделена от таблицы заболеваний; восстановлены строки диагноза, числа случаев и доли.')
# 146: nested tables are represented explicitly under their outer recommendation/context.
n=146;prepare(n)
body=para(n,[45,100,549,148])+'\n\n'+para(n,[45,150,549,197])+'\n\n'
body+=grid(n,[45,119.06,388.35,470.55,549],[200,245])+'\n\n'+para(n,[45,245,116,345])+'\n\n'+para(n,[124,250,381,266])+'\n\n'
body+=grid(n,[124,191.62,284.03,381],[267,286.7,330.72,366.34,409.79,444.84,479.90,514.95],{(4,0):(2,1)})+'\n\n'+para(n,[124,525,381,541])+'\n\n'
body+=grid(n,[124,190.06,282.61,381],[541.7,560.5,596.14,643.18,678.80,731.22,758.44,785.66],{(2,0):(2,1),(5,0):(2,1)})
body+='\n\n'+para(n,[643,100,1147,148])+'\n\n'+para(n,[643,155,713,285])+'\n\n'+para(n,[721,155,982,260])+'\n\n'+para(n,[986,155,1147,260])+'\n\n'+para(n,[721,265,982,280])+'\n\n'+grid(n,[721,810.43,935.72,982],[280.5,305.2,355.18,413.17,462.75,512.34,587.12,628.31,669.50,745.23,786.41]);commit(n,body,'Вложенные таблицы рисков, возможностей и переходных климатических рисков вынесены в отдельные сетки с сохранением контекста рекомендаций TCFD и ссылок GRI.')
# 147: reconstruct rowspans in the climate risk management section.
n=147;prepare(n)
body=para(n,[45,100,549,148])+'\n\n'+grid(n,[45,119.06,388.35,470.55,549],[150,264])+'\n\n'+para(n,[45,267,549,299])+'\n\n'+grid(n,[45,119.06,388.35,470.55,549],[300,374.36,438.25,560.5],{(0,1):(3,1),(0,3):(3,1)})+'\n\n'+para(n,[45,561,549,604])+'\n\n'+grid(n,[45,119.06,388.35,470.55,549],[605,776.35])+'\n\n'+para(n,[643,100,1147,148])+'\n\n'+grid(n,[643,717.17,986.46,1068.66,1147],[150,287.55,445.44]);commit(n,body,'Восстановлены объединённые ячейки TCFD: общая практика управления для трёх рекомендаций, отдельные ссылки на разделы, показатели и цели.')
# Save history first.
(check/'before/grids-report.md').write_text(s)
(base/'report.md').write_text('\n\n'.join(f'<!-- pdf_page: {n} -->'+chunks[n].rstrip() for n in range(1,159))+'\n')
(check/'grid_repairs.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
records=json.loads((check/'pages.json').read_text())
for a in audit:
 r=records['pages'][a['pdf_page']-1];r['grid_repairs']=a;r['issues'].append('Восстановленная по исходной геометрии сетка требует окончательной построчной сверки; страница остаётся pending.');r['source_image_inspected']=True
(check/'pages.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(audit,ensure_ascii=False,indent=2))
