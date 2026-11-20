import sys,json,unicodedata
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import fitz
from PIL import Image,ImageDraw
src=json.load(open('source.json')); d=fitz.open(src['source_pdf']); records=[]; tiles=[]
for n,p in enumerate(d,1):
 for b in p.get_text('rawdict')['blocks']:
  for l in b.get('lines',[]):
   chars=[c for s in l['spans'] for c in s['chars']]
   bad=[c for c in chars if any(unicodedata.category(t) in ('Co','Cs') or t=='\ufffd' or (unicodedata.category(t)=='Cc' and not t.isspace()) for t in c['c'])]
   if not bad: continue
   r=fitz.Rect(l['bbox']); r.x0=max(0,r.x0-4); r.x1=min(p.rect.width,r.x1+4); r.y0=max(0,r.y0-4); r.y1=min(p.rect.height,r.y1+4)
   pix=p.get_pixmap(matrix=fitz.Matrix(2,2),clip=r,alpha=False); im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
   idx=len(records); records.append({'id':idx,'page':n,'text':''.join(c['c'] for c in chars),'bad':[c['c'] for c in bad],'bbox':list(r)})
   if im.width>1450: im.thumbnail((1450,100))
   tile=Image.new('RGB',(1500,max(65,im.height+25)),'white'); ImageDraw.Draw(tile).text((0,0),f'{idx}: page {n}',fill='black'); tile.paste(im,(0,23)); tiles.append(tile)
json.dump(records,open('result/_проверка/review/unicode_lines.json','w'),ensure_ascii=False,indent=2)
for start in range(0,len(tiles),22):
 subset=tiles[start:start+22]; sheet=Image.new('RGB',(1500,sum(t.height for t in subset)),'#cccccc'); y=0
 for t in subset: sheet.paste(t,(0,y)); y+=t.height
 sheet.save(f'result/_проверка/review/unicode_{start//22}.png')
print('lines',len(records)); print([(i['id'],i['page'],repr(i['text'])) for i in records])
