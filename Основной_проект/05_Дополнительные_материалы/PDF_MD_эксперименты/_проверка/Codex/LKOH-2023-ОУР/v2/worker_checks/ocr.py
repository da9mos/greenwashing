import json,subprocess
from pathlib import Path
import pymupdf
s=json.load(open('source.json'));d=pymupdf.open(s['source_pdf'])
for n in [114,115]:
 p=d[n-1]
 for half in [0,1]:
  r=p.rect;clip=pymupdf.Rect(r.width*half/2,0,r.width*(half+1)/2,r.height)
  dest=f'result/_проверка/pages/{n:04}-half{half+1}'
  p.get_pixmap(matrix=pymupdf.Matrix(3,3),clip=clip).save(dest+'.png')
  subprocess.run(['tesseract',dest+'.png',dest,'-l','rus+eng','--psm','3'],check=True,stdout=subprocess.DEVNULL)
  print(n,half+1,flush=True)
