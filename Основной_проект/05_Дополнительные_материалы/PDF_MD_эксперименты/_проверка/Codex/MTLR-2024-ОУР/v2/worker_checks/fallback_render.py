from pathlib import Path
import sys,re,json
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
import pymupdf as f
base=Path(__file__).resolve().parents[1];s=(base/'report.md').read_text();out=base/'_проверка/render_fallback';out.mkdir(exist_ok=True)
for n in [1,15,16,128]:
 part=re.search(r'<!-- pdf_page: '+str(n)+r' -->(.*?)(?=<!-- pdf_page:|\Z)',s,re.S)[1]
 part=part.split('> Служебная информация: ссылки исходного PDF')[0]
 if n==1:part='# Отчёт об устойчивом развитии 2024\n'+part
 h=MarkdownIt('commonmark',{'html':True}).render(part)
 for width in [1440,390]:
  css='body{font-family:sans-serif;font-size:16px;} table{border-collapse:collapse;}td{border:1px solid #aaa;padding:4px;}p{margin:4px;}sup{font-size:10px;}'
  story=f.Story(html=h,user_css=css);writer=f.DocumentWriter(str(out/f'p{n}_{width}.pdf'))
  rect=f.Rect(0,0,width,2200);more=True;i=0
  while more and i<20:
   dev=writer.begin_page(rect);more,_=story.place(rect+ (10,10,-10,-10));story.draw(dev);writer.end_page();i+=1
  writer.close();doc=f.open(out/f'p{n}_{width}.pdf');doc[0].get_pixmap().save(out/f'p{n}_{width}.png')
  print(n,width,len(doc), 'remaining',more)
(out/'method.txt').write_text('Fallback: PyMuPDF Story, not Chrome; first sheets of selected source-page fragments at 1440/390. Font substitution and CSS differ from browser. This does not verify all report rendering.\n')
