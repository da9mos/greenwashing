import sys,json,re,html
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
out=Path('result');check=out/'_проверка';text=(out/'report.md').read_text();body=MarkdownIt('commonmark',{'html':True}).render(text);soup=BeautifulSoup(body,'html.parser');ids={a['id'] for a in soup.find_all(id=True)};bad=[];assets=[]
for tag in soup.find_all(['a','img']):
 v=tag.get('href') or tag.get('src') or ''
 if v.startswith('#'):
  if v[1:] not in ids:bad.append(v)
 elif not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',v):
  if not (out/v).exists():bad.append(v)
  else:assets.append(v)
assert not bad,bad
rv={'markdown_rendered_to_html':True,'browser_visual_check':'unavailable: local Chromium launch denied by sandbox MachPortRendezvous','local_links_missing':bad,'page_anchors':len(ids),'image_links':len(soup.find_all('img')),'tables':len(soup.find_all('table')),'native_replacement_glyphs':text.count('\ufffd'),'rendered_samples':[]}
for n in [1,97,117]:
 block=re.search(r'<!-- pdf_page: '+str(n)+r' -->(.*?)(?=<!-- pdf_page: |\Z)',text,re.S).group(1)
 block=re.sub(r'<details>.*?</details>','',block,flags=re.S);block=re.sub(r'!\[.*?\]\(.*?\)','',block)
 h=MarkdownIt('commonmark',{'html':True}).render(block)
 css='body{font-family:sans-serif;font-size:15px}table{border-collapse:collapse;width:100%}td{border:1px solid #999;padding:5px;vertical-align:top}h2{font-size:24px}blockquote{color:#735300}'
 doc=pymupdf.open();p=doc.new_page(width=1450,height=2900);result=p.insert_htmlbox(p.rect+ (20,20,-20,-20),h,css=css,scale_low=0);p.get_pixmap(matrix=pymupdf.Matrix(.8,.8)).save(str(check/f'render-{n}.png'));rv['rendered_samples'].append({'pdf_page':n,'scale':result[1]})
(check/'render_validation.json').write_text(json.dumps(rv,ensure_ascii=False,indent=2));print(json.dumps(rv,ensure_ascii=False))
