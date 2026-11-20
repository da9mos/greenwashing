import fitz,json,collections,io
from pathlib import Path
from PIL import Image,ImageDraw
s=json.loads(Path('source.json').read_text());d=fitz.open(s['source_pdf']);r=fitz.open('result/_проверка/font_working.pdf');seen={}
for n,p in enumerate(d,1):
 for sp in p.get_texttrace():
  for code,gid,origin,bbox in sp['chars']:
   if code==65533:seen.setdefault((sp['font'],gid),(n,bbox))
items=list(seen.items());out=Path('result/_проверка/diagnostics');print('unique missing glyphs',len(items))
for batch in range(0,len(items),24):
 im=Image.new('RGB',(1500,120*12),'white');draw=ImageDraw.Draw(im)
 for k,((fam,gid),(n,bbox)) in enumerate(items[batch:batch+24]):
  x=(k%2)*750;y=(k//2)*120
  rect=fitz.Rect(bbox);rect.x0=max(0,rect.x0-70);rect.x1=min(d[n-1].rect.width,rect.x1+170);rect.y0=max(0,rect.y0-8);rect.y1+=8
  pix=d[n-1].get_pixmap(clip=rect,matrix=fitz.Matrix(2,2));crop=Image.open(io.BytesIO(pix.tobytes('png')));crop.thumbnail((735,90));im.paste(crop,(x,y+22));
  matches=[chr(c[0]) for sp in r[n-1].get_texttrace() for c in sp['chars'] if abs(c[2][0]-origin[0])<.01 and abs(c[2][1]-origin[1])<.01] if False else []
  draw.text((x+5,y+3),f'PDF {n} | {fam} | GID {gid}',fill='black')
 im.save(out/f'font_atlas_{batch//24}.png')
