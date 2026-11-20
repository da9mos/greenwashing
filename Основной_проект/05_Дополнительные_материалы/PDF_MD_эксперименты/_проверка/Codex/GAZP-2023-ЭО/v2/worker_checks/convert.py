import sys,json,hashlib,shutil,subprocess,re,time
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
root=Path(__file__).resolve().parents[2];out=root/'result';check=out/'_проверка'
s=json.loads((root/'source.json').read_text());src=Path(s['source_pdf']);registry=json.loads(Path(s['index']).read_text());base=Path(s['index']).parent
doc=pymupdf.open(src); states=[]
(check/'source.json').write_text(json.dumps({**s,'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'actual_pages':len(doc),'method':'PyMuPDF4LLM legacy (layout disabled); local Tesseract rus+eng for image text; full source page images retained'},ensure_ascii=False,indent=2))
for i,p in enumerate(doc):
 n=i+1; dest=out/'assets'/f'page_{n:04}.png';shutil.copy2(base/f'page_{n:04}.png',dest)
 raw=p.get_text();(check/'pages'/f'{n:04}.source.txt').write_text(raw)
 issues=['Полная постраничная сверка текста, чисел, таблиц и графики по оригиналу не выполнена.']
 if n in [1,76,77,78,79]:
  # Rasterize at 300dpi so small scanned appendix body is read, not just its native header.
  img=check/'pages'/f'{n:04}.ocr.png';p.get_pixmap(dpi=300).save(img)
  proc=subprocess.run(['tesseract',str(img),str(check/'pages'/f'{n:04}.ocr'),'-l','rus+eng','--psm','3'],capture_output=True,text=True)
  if proc.returncode: raise RuntimeError(proc.stderr)
  text=(check/'pages'/f'{n:04}.ocr.txt').read_text();img.unlink()
  issues.append('Локальный OCR rus+eng: возможны ошибки распознавания, структуры и чисел; требуется сверка.')
  kind='scan' if n==1 else 'mixed'
 elif not raw.strip():text='';kind='blank_or_graphic'
 else:
  text=pymupdf4llm.to_markdown(doc,pages=[i],ignore_images=True,ignore_graphics=True,show_progress=False,margins=0,table_strategy='lines_strict')
  kind='text_and_vector_graphics'
 (check/'pages'/f'{n:04}.md').write_text(text)
 state={'pdf_page':n,'printed_page':None,'content_type':kind,'source_text_chars':len(raw),'converted_chars':len(text),'conversion_status':'converted','review_status':'pending','issues':issues,'image':f'assets/page_{n:04}.png','method':'tesseract rus+eng' if n in [1,76,77,78,79] else 'pymupdf4llm legacy'}
 states.append(state);(check/'pages.json').write_text(json.dumps({'pages':states},ensure_ascii=False,indent=2))
 print(n,len(text),flush=True)
