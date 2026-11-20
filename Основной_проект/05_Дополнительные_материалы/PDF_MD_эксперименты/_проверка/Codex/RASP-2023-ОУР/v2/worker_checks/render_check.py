import sys,re
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
import fitz
root=Path(__file__).resolve().parents[1]
s=(root/'report.md').read_text();parts=re.split(r'<!-- pdf_page: \d+ -->',s)[1:]
css='body{font-family:sans-serif;font-size:11pt}td,th{border:1px solid #aaa;padding:4px}table{border-collapse:collapse}img{width:400px}p{margin:3px 0}h2{font-size:18pt}'
writer=fitz.DocumentWriter(str(root/'_проверка/rendered_objects.pdf'))
for n in [1,4,11,13,19,21,26,27,35,43,58,62]:
 text=parts[n-1].split('> Служебная информация: ссылки исходного PDF')[0]
 text=re.sub(r'<details>.*?</details>','',text,flags=re.S)
 story=fitz.Story(html=MarkdownIt('commonmark',{'html':True}).render(text),user_css=css)
 more=True
 while more:
  device=writer.begin_page(fitz.Rect(0,0,1190,842));more,_=story.place(fitz.Rect(30,30,1160,812));story.draw(device);writer.end_page()
writer.close()
d=fitz.open(root/'_проверка/rendered_objects.pdf')
for i in [0,1,2,3,len(d)-1]:
 p=d[i].get_pixmap(matrix=fitz.Matrix(1,1));p.save(str(root/f'_проверка/rendered_{i+1:02}.png'))
print('Rendered pages',len(d))
