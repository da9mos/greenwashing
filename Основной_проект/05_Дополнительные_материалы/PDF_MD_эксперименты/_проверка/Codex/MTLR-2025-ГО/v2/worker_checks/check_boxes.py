import json,fitz,re
from pathlib import Path
from PIL import Image,ImageDraw
D=fitz.open(json.load(open('source.json'))['source_pdf']); tiles=[]
for n in range(53,67):
 rows=json.load(open(f'result/_проверка/table_rows_{n}.json'));p=D[n-1];im=Image.open(f'result/assets/page_{n:04}.png');sx=im.width/p.rect.width;sy=im.height/p.rect.height
 for r in rows:
  ls=[l for b in p.get_text('dict')['blocks'] for l in b.get('lines',[]) if r['y0']<=l['bbox'][1]<r['y1'] and ''.join(s['text'] for s in l['spans'])=='X' and ((l['bbox'][0]<600)==(r['half']==0))]
  x=min(l['bbox'][0] for l in ls);y=min(l['bbox'][1] for l in ls)
  crop=im.crop((int((x-3)*sx),int((y-2)*sy),int((x+85)*sx),int((y+54)*sy)));crop.thumbnail((220,120))
  tile=Image.new('RGB',(330,155),'white');tile.paste(crop,(0,25));dr=ImageDraw.Draw(tile);st=r['columns'][3].split('<br/>');sel=[i+1 for i,t in enumerate(st) if t.startswith('☒')];dr.text((0,0),f'p{n} {r["number"]} selected={sel}',fill='black');tiles.append(tile)
for start in range(0,len(tiles),24):
 batch=tiles[start:start+24];out=Image.new('RGB',(1320,((len(batch)+3)//4)*155),'white')
 for k,t in enumerate(batch):out.paste(t,((k%4)*330,(k//4)*155))
 out.save(f'result/_проверка/checkboxes_{start//24}.png')
print(len(tiles))
