import sys,json
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf as f,pymupdf4llm
pymupdf4llm.use_layout(False)
s=json.loads(Path('source.json').read_text());d=f.open(s['source_pdf']);out=Path('result/_проверка/table-refined');out.mkdir(exist_ok=True)
exceptions={1,4,5,8,21,31,47,60,64,82,94,103,111,112,134}
for i,p in enumerate(d):
 n=i+1
 if n in exceptions:continue
 old=p.cropbox;counts=[]
 for k in range(2):
  p.set_cropbox(f.Rect(k*old.width/2,75,(k+1)*old.width/2,800));ts=p.find_tables(strategy='lines_strict').tables;counts.append(len(ts));p.set_cropbox(old)
 if not any(counts):continue
 parts=[]
 for k in range(2):
  p.set_cropbox(f.Rect(k*old.width/2,75,(k+1)*old.width/2,800));md=pymupdf4llm.to_markdown(d,pages=[i],ignore_images=True,ignore_graphics=False,force_text=True,table_output='markdown',show_progress=False);parts.append(md);p.set_cropbox(old)
 (out/f'{n:04}.md').write_text('\n\n'.join(parts));print(n,counts,flush=True)
