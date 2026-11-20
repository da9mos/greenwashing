from pathlib import Path
import re,sys,json
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1];s=(root/'report.md').read_text()
for n in [1,2,3,60,104,188]:
 t=re.search(r'<!-- pdf_page: '+str(n)+r' -->(.*?)(?=<!-- pdf_page:|\Z)',s,re.S)[1];t=re.split('> Служебная информация: ссылки исходного PDF|<details>',t)[0]
 if n==1:t='# ГОДОВОЙ ОТЧЕТ 2025\n\n'+t
 body=MarkdownIt('commonmark',{'html':True}).enable('table').render(t)
 story=pymupdf.Story(html=body,user_css='body{font-family:sans-serif;font-size:14px}p{margin:8px 0}table{border-collapse:collapse;width:100%;margin:12px 0}td,th{border:1px solid #aaa;padding:5px}sup{font-size:9px}')
 path=root/f'_проверка/render_{n:04}.pdf';writer=pymupdf.DocumentWriter(str(path));more=True
 while more:
  device=writer.begin_page(pymupdf.Rect(0,0,1600,2400));more,_=story.place(pymupdf.Rect(30,30,1570,2370));story.draw(device);writer.end_page()
 writer.close();d=pymupdf.open(path);d[0].get_pixmap(matrix=pymupdf.Matrix(.8,.8)).save(root/f'_проверка/render_{n:04}.png');print(n,len(d))
