import sys,json
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf as f
from PIL import Image,ImageDraw
s=json.load(open('source.json')); d=f.open(s['source_pdf']); samples={}
for p in d:
 for b in p.get_text('rawdict')['blocks']:
  for l in b.get('lines',[]):
   for sp in l['spans']:
    if not sp['font'].startswith('Roboto'):continue
    for c in sp['chars']:
     if ord(c['c'])>126 or ord(c['c'])<32:
      samples.setdefault(ord(c['c']),(p.number,c['bbox']))
items=sorted(samples.items());json.dump({str(k):v for k,v in items},open('result/_проверка/glyph_samples.json','w'))
for start in range(0,len(items),100):
 batch=items[start:start+100];out=Image.new('RGB',(1000,((len(batch)+9)//10)*95),'white');dr=ImageDraw.Draw(out)
 for i,(code,(pn,box)) in enumerate(batch):
  r=f.Rect(box);r.x0-=1;r.x1+=1;r.y0-=1;r.y1+=1
  pix=d[pn].get_pixmap(matrix=f.Matrix(3,3),clip=r,alpha=False);im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples);im.thumbnail((80,60))
  x=(i%10)*100;y=(i//10)*95;out.paste(im,(x,y));dr.text((x,y+65),f'{code:04X} p{pn+1}',fill='black')
 out.save(f'result/_проверка/glyph_atlas_{start}.png')
print('unique',len(items))
