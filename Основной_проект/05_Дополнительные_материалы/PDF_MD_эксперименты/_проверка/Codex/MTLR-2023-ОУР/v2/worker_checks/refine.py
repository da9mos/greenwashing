"""Refine the provided mechanical candidate with the shared native converter.
No external services; raw native output and every transformation are retained.
"""
import importlib.util,json,re,hashlib,collections,html,sys
from pathlib import Path
S=json.load(open('source.json')); ROOT=Path(S['index']).parents[3]
spec=importlib.util.spec_from_file_location('native',ROOT/'tools/native_candidate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from bs4 import BeautifulSoup
base=Path('result/_проверка');(base/'native_pages').mkdir(exist_ok=True)
original_order=m.order_objects; original_render=m.render_glyphs
block_map={};font_map={};changes=[]
def render(units):
 # Tag chart-font encoded drawing instructions without altering native characters.
 groups=[]
 for u in units:
  tag=font_map[u['id']].startswith('Chartwell')
  if groups and groups[-1][0]==tag and groups[-1][1][-1]['line']==u['line']:groups[-1][1].append(u)
  else:groups.append((tag,[u]))
 return ''.join(('<br/>' if j and groups[j-1][1][-1]['line']!=g[0]['line'] else '') + (('<span class="chart-code">'+original_render(g)+'</span>') if tag else original_render(g)) for j,(tag,g) in enumerate(groups))
def order(objects):
 # Whole source blocks are kept together so adjacent prose columns cannot interleave line by line.
 grouped=collections.defaultdict(list);out=[]
 for o in objects:
  if o['kind']=='text':grouped[(block_map[o['source_ids'][0]], int((o['bbox'][0]+o['bbox'][2])/2 > page.rect.width/2))].append(o)
  else:out.append(o)
 for k,items in grouped.items():
  items.sort(key=lambda o:min(o['source_ids']))
  out.append({'bbox':[min(o['bbox'][0] for o in items),min(o['bbox'][1] for o in items),max(o['bbox'][2] for o in items),max(o['bbox'][3] for o in items)],'text':'\n'.join(o['text'] for o in items),'kind':'text','source_ids':[i for o in items for i in o['source_ids']]})
 if n not in [1,5,6,11,55,65,66,77,82,83,84,85,98]:
  top=[o for o in out if o['bbox'][3]<45];bottom=[o for o in out if o['bbox'][1]>page.rect.height*.94]
  rest=[o for o in out if o not in top and o not in bottom];left=[o for o in rest if (o['bbox'][0]+o['bbox'][2])/2 < page.rect.width/2];right=[o for o in rest if o not in left]
  return original_order(top)+original_order(left)+original_order(right)+original_order(bottom)
 return original_order(out)
m.render_glyphs=render;m.order_objects=order
records=[];parts=[];doc=m.fitz.open(S['source_pdf']);names=doc.resolve_names()
old=json.load(open(base/'pages.json'))

if not (base/'pages.native.json').exists(): (base/'pages.native.json').write_text(json.dumps(old,ensure_ascii=False,indent=2))
for n,page in enumerate(doc,1):
 block_map.clear();font_map.clear();i=0
 for bi,b in enumerate(page.get_text('rawdict')['blocks']):
  for l in b.get('lines',[]):
   for s in l['spans']:
    for c in s.get('chars',[]):block_map[i]=bi;font_map[i]=s['font'];i+=1
 body,info=m.convert_page(page)
 (base/'native_pages'/f'{n:04}.html').write_text(body)
 soup=BeautifulSoup(body,'html.parser');removed=[]
 for el in soup.select('span.chart-code'):removed.append(el.get_text());el.decompose()
 body=str(soup).replace('\ue135','◀').replace('\ue136','▶').replace('\x08','')
 links,unresolved=m.source_links(page,names,len(doc));links=links.replace('\ue135','◀').replace('\ue136','▶')
 info.update({'pdf_page':n,'conversion_status':'converted','review_status':'pending','semantic_source_review_completed':False,'verification_scope':'Обзор макета исходного изображения; посимвольная сверка всей страницы не выполнена.','issues':['Полная сверка текста, чисел, порядка блоков и связей по оригиналу не завершена.'],'content_type':'native_text_with_graphics' if n!=98 else 'graphics_only','printed_labels':[],'removed_chart_font_codes':removed,'unresolved_links':unresolved})
 if unresolved:info['issues'].append('Не все назначения исходных ссылок разрешены; адреса не выдумывались.')
 if info['ambiguous_cell_assignments']:info['issues'].append('Геометрически неоднозначные ячейки требуют проверки; см. ambiguous_cell_assignments.')
 for b in page.get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   t=''.join(s['text'] for s in l['spans']).strip()
   if l['bbox'][1]>page.rect.height*.93 and t.isdigit():info['printed_labels'].append(t)
 info['printed_labels']=list(dict.fromkeys(info['printed_labels']))
 if n==1:
  body='<h1>Отчёт об устойчивом развитии</h1>\n\n<p>2023</p>\n\n<p>Мечел. 20 лет.</p>'
  info['review_status']='checked';info['semantic_source_review_completed']=True;info['issues']=[];info['verification_scope']='Обложка просмотрена целиком; название, год и текст юбилейного логотипа перенесены визуально.'
 if n==98:
  info['review_status']='checked';info['semantic_source_review_completed']=True;info['issues']=[];info['verification_scope']='Задняя обложка просмотрена целиком: текст отсутствует, графика сохранена.'
 notice='' if n in [1,98] else '\n\n> Служебная пометка: рабочая транскрипция; полная сверка этой страницы по оригиналу не завершена. Сложные схемы и диаграммы см. также на исходном изображении.\n'
 part=f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+body+notice+links+f'\n\n<details>\n<summary>Источник: PDF-страница {n}</summary>\n\n![Полная исходная страница {n}](assets/page_{n:04}.png)\n\n</details>\n'
 (base/'native_pages'/f'{n:04}.md').write_text(part);parts.append(part);records.append(info)
 changes.append({'pdf_page':n,'chart_font_runs_removed':len(removed),'tables':info['tables'],'native_glyphs':info['native_glyphs'],'unicode_navigation_replaced':True})
 (base/'progress.json').write_text(json.dumps({'last_converted_page':n,'total':98}))
header='# Отчёт об устойчивом развитии\n\n> Служебная информация: рабочая версия полной конвертации 98 физических страниц. Текстовый слой и таблицы перенесены механически с адресными исправлениями. Полная сверка по оригиналу не выполнена; статус каждой страницы указан в `_проверка/pages.json`.\n\n'
Path('result/report.md').write_text(header+'\n'.join(parts))
(base/'pages.json').write_text(json.dumps({'pages':records},ensure_ascii=False,indent=2)+'\n')
(base/'refinement_log.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
print('Completed',len(records),'pages; tables',sum(x['tables'] for x in records))
