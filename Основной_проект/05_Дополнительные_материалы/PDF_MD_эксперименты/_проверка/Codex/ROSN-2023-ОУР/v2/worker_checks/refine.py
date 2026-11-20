import sys,json,re,time,collections
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf as f,pymupdf4llm
pymupdf4llm.use_layout(False)
out=Path('result'); temp=out/'_проверка/refined';temp.mkdir(exist_ok=True)
s=json.loads(Path('source.json').read_text());d=f.open(s['source_pdf'])
exceptions={1,4,5,8,21,31,47,60,64,82,94,103,111,134}; stats=[]
for i,p in enumerate(d):
 n=i+1
 if n in exceptions: continue
 old=p.cropbox; parts=[]; labels=[]; partstats=[]
 for b in p.get_text('blocks'):
  if b[1]>800 and re.fullmatch(r'\s*\d+\s*',b[4]): labels.append(b[4].strip())
 for k in range(2):
  p.set_cropbox(f.Rect(k*old.width/2,75,(k+1)*old.width/2,800))
  raw=p.get_text();md=pymupdf4llm.to_markdown(d,pages=[i],ignore_images=True,ignore_graphics=True,force_text=True,table_output='html',show_progress=False)
  md=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',md)
  md=re.sub('\u00ad[ \t]*\n[ \t]*','',md).replace('\u00ad','')
  partstats.append({'side':k,'source_chars':len(raw),'markdown_chars':len(md)})
  parts.append(md.strip());p.set_cropbox(old)
 body='\n\n'.join(parts)
 (temp/f'{n:04}.md').write_text(body)
 stats.append({'pdf_page':n,'printed_page_label':labels,'parts':partstats})
 (out/'_проверка/refine-stats.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2))
 print(n,len(body),flush=True)
