import sys,inspect,re,json,hashlib
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf as fitz
from PIL import Image
from collections import Counter
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
import importlib.util
src=Path(json.loads(Path('source.json').read_text())['source_pdf']); tool=src.parent.parent/'tools/native_candidate.py'
spec=importlib.util.spec_from_file_location('native',tool); native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
code=inspect.getsource(native.convert_page).replace('return body, {','return body, units, ordered, {');exec(code,native.__dict__)
doc=fitz.open(src); target=Path('result/report.md');full=target.read_text(); chunks=re.split(r'(?=<!-- pdf_page: \d+ -->)',full); prefix=chunks.pop(0); chunks={int(re.search(r'pdf_page: (\d+)',c)[1]):c for c in chunks}
log=[]
def repair(n,regions):
 page=doc[n-1]; _,units,objects,_=native.convert_page(page); iw,ih=Image.open(f'result/assets/page_{n:04}.png').size; sx=page.rect.width/iw;sy=page.rect.height/ih
 removed=set(); added=[]
 for xs,ys in regions:
  xs=[v*sx for v in xs];ys=[v*sy for v in ys]; cells=[]
  for ri in range(len(ys)-1):
   row=[]
   for ci in range(len(xs)-1):
    us=[u for u in units if xs[ci]<=(u['bbox'][0]+u['bbox'][2])/2<xs[ci+1] and ys[ri]<=(u['bbox'][1]+u['bbox'][3])/2<ys[ri+1]]
    removed.update(u['id'] for u in us);row.append('<td>'+native.render_glyphs(us)+'</td>')
   cells.append('<tr>'+''.join(row)+'</tr>')
  added.append(dict(bbox=[xs[0],ys[0],xs[-1],ys[-1]],text='<table>\n'+'\n'.join(cells)+'\n</table>',kind='table',source_ids=[]))
 out=[]
 for o in objects:
  remain=[u for u in units if u['id'] in o['source_ids'] and u['id'] not in removed]
  if len(remain)==len(o['source_ids']):out.append(o)
  elif remain:
   # Any portion outside a corrected table keeps its own PDF line and position.
   lines={}
   for u in remain:lines.setdefault(u['line'],[]).append(u)
   for us in lines.values():
    out.append(dict(bbox=[min(u['bbox'][0] for u in us),min(u['bbox'][1] for u in us),max(u['bbox'][2] for u in us),max(u['bbox'][3] for u in us)],text='<p>'+native.render_glyphs(us)+'</p>',kind='text',source_ids=[u['id'] for u in us]))
 out+=added;body='\n\n'.join(o['text'] for o in native.order_objects(out));body=re.sub(r'<p>\s*</p>\s*','',body)
 rendered=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).render(body),'html.parser').get_text()
 assert Counter(c for c in rendered if not c.isspace())==Counter(u['text'] for u in units if not u['text'].isspace()),n
 # Retain original source-link appendix and image reference.
 old=chunks[n]; appendix=old[old.index('> Служебная информация: ссылки'):] if '> Служебная информация: ссылки' in old else old[old.index('<details>'):]
 chunks[n]=f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+body+'\n\n'+appendix
 log.append(dict(page=n,regions_pixels=regions,original_glyphs=len(units),corrected_region_glyphs=len(removed),character_inventory_matches=True))
# Grids follow visible source borders; no numbers are retyped.
repair(53,[([112,180,625,775,925,1110],[1096,1163,1197,1230,1263,1327,1361,1393,1488,1523])])
repair(54,[([112,180,625,775,925,1110],[110,178,209,305,369,498,626,722,819,947,1107,1361,1425,1492])])
repair(67,[([105,444,581,694,829,986,1114],[111,163,189,240,266,342,368,394]),([112,437,565,699,822,941,1107],[834,935,986,1063,1088,1190,1266,1292,1393,1469])])
repair(68,[([112,437,565,699,822,941,1107],[266,367,418,519,545,570,622,672,698,775]),([112,437,565,699,822,941,1107],[930,1031,1082,1133,1159,1236,1287,1362,1388,1464,1540,1565])])
repair(69,[([112,437,565,699,822,941,1107],[375,476,502,527,629,679,730,782,833,858,934])])
repair(70,[([99,277,416,512,616,721,825,923,1022,1121],[602,679,730,781,882,910]),([94,275,412,510,616,721,824,923,1022,1124],[935,1013,1064,1115,1216,1243])])
repair(103,[([112,650,800,930,1107],[1260,1332,1367,1432,1468,1535])])
repair(144,[([80,489,577,748,860,960,1128,1237,1326,1495,1605],[230,426,492,525,559,592,626,655,688,721,754,788,821,885,919,953])])
repair(165,[([112,425,509,637,765,894,1107],[165,226,257,348,379,410,442,474,506])])
repair(184,[([77,290,389,474,559,645,744,829,900,985,1070,1143],[492,754,955,1016,1105,1306,1450,1540])])
repair(185,[([77,290,389,474,559,645,744,829,900,985,1070,1143],[111,373,461,521,586])])
repair(190,[([123,502,1107],[639,1126])])
repair(194,[([85,269,439,595,765,922,1135],[123,255,307,349,406,451,508,564,621,664,699]),([112,397,1107],[1052,1118,1543])])
repair(241,[([77,133,984,1466,1637],[140,223,279,362,417,472,528,611,666,721,777,832,915,971,1026,1082])])
repair(243,[([77,133,984,1466,1637],[140,223,279,334,390,445,528,583,639,694,750,805,860,916,1027])])
repair(244,[([77,133,984,1466,1637],[140,223,279,334])])
# Explicit missing leading columns in continuation rows, retaining native text.
for n in [254,260]:
 soup=BeautifulSoup(chunks[n],'html.parser'); t=soup.find('table'); rows=t.find_all('tr',recursive=False)
 if n==254:
  for row in rows[2:]:
   for _ in range(4):row.insert(0,soup.new_tag('td'))
 else:
  first=rows[2]; cell=soup.new_tag('td',rowspan='3');first.insert(0,cell)
 chunks[n]=str(soup)
 log.append(dict(page=n,repair='Restore source-empty leading column(s), preserving original native cells.'))
# Headings accidentally included as extra-width table rows belong outside the table.
for n,heading in [(180,'6.7.7.'),(228,'7.8.5.')]:
 soup=BeautifulSoup(chunks[n],'html.parser')
 for t in soup.find_all('table'):
  extracted=[]
  for row in list(t.find_all('tr',recursive=False)):
   cells=row.find_all('td',recursive=False)
   if len(cells)==1 and int(cells[0].get('colspan',1))==5:
    extracted.append(cells[0].get_text(' ',strip=True));row.decompose()
  if extracted:
   h=soup.new_tag('h3');h.string=' '.join(extracted);t.insert_after(h)
 chunks[n]=str(soup);log.append(dict(page=n,repair='Move section heading out of table.'))
target.write_text(prefix+''.join(chunks[n] for n in range(1,304)))
Path('result/_проверка/current_review/geometry_repairs.json').write_text(json.dumps(log,ensure_ascii=False,indent=2))
print('repaired', [x['page'] for x in log])
