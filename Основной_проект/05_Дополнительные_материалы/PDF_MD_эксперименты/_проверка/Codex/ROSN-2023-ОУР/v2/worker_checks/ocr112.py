import sys,json,subprocess
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf as f
s=json.loads(Path('source.json').read_text());d=f.open(s['source_pdf']);p=d[111];out=Path('result/_проверка/pages')
for k in range(2):
 clip=f.Rect(k*p.rect.width/2,130,(k+1)*p.rect.width/2,795)
 im=out/f'0112-scan-{k}.png';p.get_pixmap(matrix=f.Matrix(3,3),clip=clip).save(im)
 t=subprocess.run(['tesseract',str(im),'stdout','-l','rus+eng','--psm','3'],capture_output=True,text=True)
 (out/f'0112-scan-{k}.txt').write_text(t.stdout)
 print(k,len(t.stdout),flush=True)
