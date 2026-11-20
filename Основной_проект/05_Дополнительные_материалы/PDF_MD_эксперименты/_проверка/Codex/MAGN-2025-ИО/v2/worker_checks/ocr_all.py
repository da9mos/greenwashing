import fitz,json,subprocess,io
from pathlib import Path
from PIL import Image,ImageEnhance,ImageFilter
s=json.loads(Path('source.json').read_text());d=fitz.open(s['source_pdf']);out=Path('result/_проверка/ocr')
for n in [278,279,280,281]:
 for j,im in enumerate(sorted(d[n-1].get_image_info(xrefs=True),key=lambda v:v['bbox'][0]),1):
  b=d.extract_image(im['xref']);p=out/f'scan_{n}_{j}.png';img=Image.open(io.BytesIO(b['image']));img.resize((img.width*3,img.height*3)).save(p)
  subprocess.run(['tesseract',str(p),str(out/f'text_{n}_{j}'),'-l','rus+eng','--psm','3'],capture_output=True)
  print(n,j,flush=True)
