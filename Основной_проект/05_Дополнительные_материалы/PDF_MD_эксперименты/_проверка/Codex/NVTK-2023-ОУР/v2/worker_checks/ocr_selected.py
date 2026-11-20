import subprocess
from pathlib import Path
for n in [1,2,133,138]:
 p=Path(f'result/_проверка/pages/ocr_{n:04}')
 subprocess.run(['tesseract',f'result/assets/page_{n:04}.png',str(p),'-l','rus+eng','--psm','3'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 print(n,flush=True)
