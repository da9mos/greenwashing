from pathlib import Path
import re,sys,json,hashlib
sys.path.insert(0,'/private/tmp/sber-diff-libs');sys.path.insert(0,'/private/tmp/sber-pdf-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
import pymupdf as fitz
r=Path('result');out=r/'_проверка/render';out.mkdir(exist_ok=True)
text=(r/'report.md').read_text();rendered=MarkdownIt('commonmark',{'html':True}).enable('table').render(text)
soup=BeautifulSoup(rendered,'html.parser')
for table in list(soup.find_all('table')):
 w=soup.new_tag('div');w['class']='scroll';table.wrap(w)
css='body{font-family:Arial,sans-serif;line-height:1.5;max-width:1320px;margin:24px;padding:12px}table{border-collapse:collapse;min-width:600px}td,th{border:1px solid #aaa;padding:8px;vertical-align:top}.scroll{overflow-x:auto}img{max-width:100%;height:auto}p{margin:12px 0}summary{cursor:pointer}'
# Relative links from the actual HTML location remain portable within the result bundle.
for im in soup.find_all('img'):im['src']='../../'+im['src']
(out/'report.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+css+'</style><body>'+str(soup)+'</body></html>')
parts=re.split(r'<!-- pdf_page: \d+ -->',text)[1:]
for n in [1,16,41,49,50]:
 p=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).render(parts[n-1]),'html.parser')
 if n==1:
  for d in p.find_all('details'):d.decompose()
  content=str(p)
 else:content=str(p.find('table'))
 for width in ([1440,390] if n in [1,49] else [1440]):
  story=fitz.Story(html=content,user_css='body{font-family:sans-serif;font-size:12px}table{border-collapse:collapse}td,th{padding:5px;border:1px solid #888}',em=12)
  target=out/f'mupdf_page_{n:04}_{width}.pdf';writer=fitz.DocumentWriter(str(target))
  more=True;count=0
  while more and count<30:
   rect=fitz.Rect(0,0,width,1100);device=writer.begin_page(rect);more,filled=story.place(rect+ (15,15,-15,-15));story.draw(device);writer.end_page();count+=1
  writer.close();doc=fitz.open(target)
  doc[0].get_pixmap().save(str(target.with_suffix('.png')))
  target.unlink()
(out/'render_check.json').write_text(json.dumps({'report_sha256':hashlib.sha256((r/'report.md').read_bytes()).hexdigest(),'browser_render_status':'blocked','browser_error':'Chrome headless exits SIGABRT under current execution restrictions','fallback':'MuPDF Story previews: cover and tables on physical pages 16, 41, 49, 50; 1440 px and selected 390 px','limitations':'Fallback is not Chrome; it does not verify browser overflow or the entire rendered document.'},ensure_ascii=False,indent=2))
