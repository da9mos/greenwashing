import json,pathlib,subprocess,concurrent.futures
s=json.load(open('source.json')); base=pathlib.Path(s['index']).parent;out=pathlib.Path('result/_проверка')
nums=[1,2,7,9,18,25,32,39,45,46,47,55,61,67,73,75,76,85,86,90,96,99,104,125,127]
def run(n):
 target=out/f'graphic_ocr_{n:04}'
 subprocess.run(['tesseract',str(base/f'page_{n:04}.png'),str(target),'-l','rus+eng','--psm','3'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
 print(n,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:list(ex.map(run,nums))
