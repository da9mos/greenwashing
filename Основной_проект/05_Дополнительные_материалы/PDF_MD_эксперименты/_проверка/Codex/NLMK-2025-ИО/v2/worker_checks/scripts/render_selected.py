import sys,re,pathlib
sys.path.insert(0,'/private/tmp/sber-pdf-libs');sys.path.insert(0,'/private/tmp/sber-diff-libs')
import pymupdf as f
from bs4 import BeautifulSoup
root=pathlib.Path(__file__).resolve().parents[3];out=root/'result/_проверка/render_selected';out.mkdir(exist_ok=True)
s=(root/'result/report.md').read_text()
for n in [115,119,125]:
 body=re.search(r'<!-- pdf_page: '+str(n)+r' -->(.*?)(?=<!-- pdf_page:|\Z)',s,re.S)[1];soup=BeautifulSoup(body,'html.parser');tables=''.join(str(t) for t in soup.find_all('table'))
 for width in [1440,390]:
  path=out/f'page_{n}_{width}.pdf';w=f.DocumentWriter(str(path));story=f.Story(html=f'<h1>PDF {n}: selected tables</h1>'+tables,user_css='body {font-family:sans-serif;font-size:12px} table {border-collapse:collapse;margin-bottom:20px} td {border:1px solid #aaaaaa;padding:5px}');rect=f.Rect(0,0,width,2000)
  story.write(w,lambda a,b:(rect,rect+ (12,12,-12,-12),None));w.close();doc=f.open(path);doc[0].get_pixmap().save(str(out/f'page_{n}_{width}.png'))
