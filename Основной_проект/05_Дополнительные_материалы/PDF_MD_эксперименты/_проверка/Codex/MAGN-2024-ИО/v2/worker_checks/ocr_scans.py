import fitz,json,subprocess
from PIL import Image
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
r=Path('result/_проверка');doc=fitz.open(json.load(open('source.json'))['source_pdf']);tasks=[]
for n in range(279,283):
 pg=doc[n-1]
 for j,info in enumerate(pg.get_image_info(xrefs=True)):
  if info['width']<400 or info['height']<600:continue
  pix=fitz.Pixmap(doc,info['xref']);im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples) if pix.n==3 else Image.open(__import__('io').BytesIO(pix.tobytes('png'))).convert('RGB')
  path=r/f'scan_{n}_{j}.png';im.resize((im.width*4,im.height*4)).save(path);tasks.append((n,j,path))
def run(t):
 n,j,p=t;res=subprocess.run(['tesseract',str(p),str(p.with_suffix('')),'-l','rus+eng','--psm','3'],capture_output=True,text=True);return(n,j,res.returncode,res.stderr)
with ThreadPoolExecutor(max_workers=4) as ex:
 for x in ex.map(run,tasks):print(x)
