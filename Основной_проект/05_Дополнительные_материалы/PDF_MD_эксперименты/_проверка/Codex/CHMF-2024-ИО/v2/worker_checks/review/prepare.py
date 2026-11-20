import pymupdf,json,pathlib,subprocess
from PIL import Image,ImageDraw
root=pathlib.Path('result/_проверка/review');pdf=pymupdf.open(json.load(open('source.json'))['source_pdf'])
# First instance of each problematic sign per page; retained source coordinates.
items=[]
for n,page in enumerate(pdf,1):
 seen=set()
 for b in page.get_text('rawdict')['blocks']:
  for l in b.get('lines',[]):
   for s in l['spans']:
    for c in s['chars']:
     if c['c'] in '\x07\uf0fc\uf0b7' and c['c'] not in seen:
      seen.add(c['c']); r=pymupdf.Rect(c['bbox']);r.x0=max(0,r.x0-75);r.x1=min(page.rect.width,r.x1+195);r.y0-=8;r.y1+=8
      pix=page.get_pixmap(matrix=pymupdf.Matrix(3,3),clip=r);im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples);items.append((n,repr(c['c']),im))
for k in range(0,len(items),20):
 canvas=Image.new('RGB',(1800,1400),'#eee');d=ImageDraw.Draw(canvas)
 for j,(n,ch,im) in enumerate(items[k:k+20]):
  im.thumbnail((890,105));x=j%2*900;y=j//2*140;canvas.paste(im,(x,y+25));d.text((x,y+3),f'page {n} {ch}',fill='black')
 canvas.save(root/f'unicode_{k//20}.jpg')
# OCR only rasterized body regions; retain full words regardless of confidence.
for n in range(141,147):
 page=pdf[n-1];w=page.rect.width;h=page.rect.height
 sides=['right'] if n==141 else ['left'] if n==146 else ['left','right']
 for side in sides:
  clip=pymupdf.Rect(0 if side=='left' else w/2,20,w/2 if side=='left' else w,h-45)
  path=root/f'ocr_{n}_{side}.png';page.get_pixmap(matrix=pymupdf.Matrix(3,3),clip=clip).save(path)
  p=subprocess.run(['tesseract',str(path),str(root/f'ocr_{n}_{side}'),'-l','rus+eng','--psm','3'],capture_output=True,text=True)
  print(n,side,p.returncode,flush=True)
