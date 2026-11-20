from pathlib import Path
import sys,re,json
sys.path.insert(0,'/private/tmp/sber-pdf-libs');import pymupdf as f
sys.path.insert(0,'/private/tmp/sber-diff-libs');from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1];out=root/'_проверка/render';out.mkdir(exist_ok=True)
md=MarkdownIt('commonmark',{'html':True}).enable('table');s=(root/'report.md').read_text()
full=BeautifulSoup(md.render(s),'html.parser')
for im in full.find_all('img'):im['src']='../../'+im['src']
for t in list(full.find_all('table')):
 wrap=full.new_tag('div');wrap['class']='scroll';t.wrap(wrap)
css='body{font:16px/1.5 Arial,sans-serif;max-width:1200px;margin:auto;padding:24px}table{border-collapse:collapse;min-width:600px}td,th{border:1px solid #ccd;padding:6px;vertical-align:top}.scroll{overflow-x:auto}img{max-width:100%}details{margin:16px 0}blockquote{color:#657}'
(out/'report.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+css+'</style>'+str(full))
parts=re.split(r'<!-- pdf_page: \d+ -->',s)[1:];results=[]
for n in [1,4,33,37,57,69,123,159]:
 soup=BeautifulSoup(md.render(parts[n-1]),'html.parser')
 for x in soup.find_all(['details','ul']):
  if x.name=='details' or x.find('a'):x.decompose()
 # This is a paginated MuPDF HTML proof, not Chrome or responsive browser testing.
 for w in [1440,390]:
  smallcss='body{font-family:sans-serif;font-size:14px}td,th{border:1px solid #aaa;padding:4px;vertical-align:top}table{border-collapse:collapse}p{margin:4px 0}blockquote{color:#777}'
  story=f.Story(html=str(soup),user_css=smallcss);path=out/f'selected_p{n:03d}_{w}.pdf';writer=f.DocumentWriter(str(path));pagecount=0;more=True
  while more and pagecount<30:
   rect=f.Rect(0,0,w,1200);dev=writer.begin_page(rect);more,filled=story.place(rect+ (16,16,-16,-16));story.draw(dev);writer.end_page();pagecount+=1
  writer.close()
  d=f.open(path)
  d[0].get_pixmap().save(out/f'selected_p{n:03d}_{w}.png')
  results.append({'pdf_page':n,'width':w,'proof_pages':len(d),'complete_layout':not more})
(out/'render_check.json').write_text(json.dumps({'engine':'MuPDF Story (fallback)','chrome_status':'launch failed: SIGABRT / TargetClosedError; no Chrome screenshots obtained','scope':'Selected HTML text/table proofs only; not browser responsiveness or full PDF comparison','results':results},ensure_ascii=False,indent=2))
print(results)
