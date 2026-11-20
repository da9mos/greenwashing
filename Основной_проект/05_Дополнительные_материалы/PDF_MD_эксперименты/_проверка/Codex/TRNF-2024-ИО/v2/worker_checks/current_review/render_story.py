import sys,re,json
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf as fitz
from markdown_it import MarkdownIt
text=Path('result/report.md').read_text(); out=Path('result/_проверка/current_review');results=[]
for n in [1,9,30,31,42,53,54,67,68,69,70,71,103,144,165,176,177,184,185,190,194,195,228,241,243,244,254,260]:
 c=re.search(r'<!-- pdf_page: '+str(n)+r' -->.*?(?=<!-- pdf_page:|\Z)',text,re.S)[0]; c=c[:c.index('<details>')];h=MarkdownIt('commonmark',{'html':True}).render(c)
 story=fitz.Story(html=h,user_css='body {font-family:sans-serif;font-size:9pt} table{border-collapse:collapse}td,th{border:0.4pt solid #888;padding:3pt}p{margin:3pt}')
 target=out/f'render-{n}.pdf';writer=fitz.DocumentWriter(str(target));count=0
 while True:
  dev=writer.begin_page(fitz.Rect(0,0,1200,1600));more,_=story.place(fitz.Rect(20,20,1180,1580));story.draw(dev);writer.end_page();count+=1
  if not more or count>=12:break
 writer.close();d=fitz.open(target);d[0].get_pixmap(matrix=fitz.Matrix(1,1)).save(out/f'render-{n}.png');results.append(dict(page=n,render_pages=len(d),overflow_unresolved=bool(more),engine='PyMuPDF Story',source_images_excluded_from_preview=True))
(out/'render_checks.json').write_text(json.dumps(results,indent=2));print(results)
