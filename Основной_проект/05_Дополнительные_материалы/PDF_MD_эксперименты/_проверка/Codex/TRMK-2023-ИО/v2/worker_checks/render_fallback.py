from pathlib import Path
import sys,json,re,hashlib
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf as f
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
s=Path('result/report.md').read_text();md=MarkdownIt('commonmark',{'html':True}).enable('table')
out=Path('result/_проверка/render');out.mkdir(exist_ok=True)
css='body {font-family:sans-serif;font-size:14px;} p {margin:5px 0;} h1 {font-size:28px;} h2 {font-size:22px;} table {border-collapse:collapse;} td,th {border:1px solid #bbb;padding:5px;vertical-align:top;} th {background-color:#eee;} blockquote {color:#555;}'
def render(text,path,width,height):
 soup=BeautifulSoup(md.render(text),'html.parser')
 for t in soup.find_all(['details','img']):t.decompose()
 story=f.Story(str(soup),user_css=css)
 # fixed pages ensure fallback cannot silently loop on a wide table
 pdf=f.open();more=True;count=0
 while more and count<30:
  writer=f.DocumentWriter(str(path.with_suffix('.pdf')) if count==0 else str(path.with_name(path.stem+f'_{count}.pdf')))
  dev=writer.begin_page(f.Rect(0,0,width,height));more,_=story.place(f.Rect(20,20,width-20,height-20));story.draw(dev);writer.end_page();writer.close()
  count+=1
  if count==1:
   dd=f.open(path.with_suffix('.pdf'));dd[0].get_pixmap().save(path.with_suffix('.png'));dd.close()
 return {'file':path.with_suffix('.png').name,'pages':count,'complete':not more,'width':width}
results=[]
for w in [1440,390]:results.append(render(s.split('<!-- pdf_page: 2 -->')[0],out/f'fallback_width_{w}',w,1000))
for n in [18,19,23,27,39,40]:
 part=s.split(f'<!-- pdf_page: {n} -->')[1].split('<!-- pdf_page:')[0]
 results.append(render(part,out/f'fallback_page_{n:02}',1440,5000 if n==27 else 2500))
(out/'fallback_render_check.json').write_text(json.dumps({'engine':'PyMuPDF Story, local HTML renderer; not Chrome/CSS equivalence','report_sha256':hashlib.sha256(s.encode()).hexdigest(),'results':results,'browser_status':'failed: Chrome headless launch SIGABRT under current execution restrictions'},ensure_ascii=False,indent=2))
print(results)
