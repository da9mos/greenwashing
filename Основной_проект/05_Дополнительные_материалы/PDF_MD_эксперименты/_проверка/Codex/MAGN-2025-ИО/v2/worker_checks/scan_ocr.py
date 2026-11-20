import fitz,json,subprocess
from pathlib import Path
from PIL import Image
s=json.loads(Path('source.json').read_text());d=fitz.open(s['source_pdf']);out=Path('result/_проверка/ocr');out.mkdir(exist_ok=True)
for n in [278,279,280,281]:
 p=d[n-1];images=p.get_image_info(xrefs=True);image=max(images,key=lambda x:fitz.Rect(x['bbox']).get_area());data=d.extract_image(image['xref']);path=out/f'scan_{n}.{data["ext"]}';path.write_bytes(data['image']);print(n,data['width'],data['height'],flush=True)
 subprocess.run(['tesseract',str(path),str(out/f'page_{n}'),'-l','rus+eng','--psm','3'],capture_output=True)
