import sys,re,json,hashlib
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import fitz
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
root=Path('result'); s=json.loads(Path('source.json').read_text()); idx=json.loads(Path(s['index']).read_text()); text=(root/'report.md').read_text(); chunks=re.split(r'(?=<!-- pdf_page: \d+ -->)',text)[1:]
sha=hashlib.sha256(Path(s['source_pdf']).read_bytes()).hexdigest(); doc=fitz.open(s['source_pdf']); assert len(doc)==303 and sha==idx['source_sha256']
assert [int(re.search(r'pdf_page: (\d+)',c)[1]) for c in chunks]==list(range(1,304))
missing=[];badanchors=[];anchors=set(re.findall(r'id="([^"]+)"',text))
for link in re.findall(r'\]\(([^)]+)\)|(?:href|src)="([^"]+)"',text):
 link=link[0] or link[1]
 if link.startswith('#'):
  if link[1:] not in anchors: badanchors.append(link)
 elif not re.match(r'[a-z]+:',link) and not (root/link).is_file(): missing.append(link)
asset_mismatch=[]
for p in idx['pages']:
 a=root/'assets'/f"page_{p['pdf_page']:04}.png"
 if hashlib.sha256(a.read_bytes()).hexdigest()!=p['image_sha256']: asset_mismatch.append(p['pdf_page'])
struct=[];unicode=[]
for n,c in enumerate(chunks,1):
 if any(0xe000<=ord(ch)<=0xf8ff or ch=='\ufffd' for ch in c): unicode.append(n)
 bs=BeautifulSoup(c,'html.parser')
 for ti,t in enumerate(bs.find_all('table'),1):
  rows=t.find_all('tr'); total=empty=0; grid={}; widths=[];overlap=False
  for ri,row in enumerate(rows):
   col=0
   for cell in row.find_all(['td','th'],recursive=False):
    while (ri,col) in grid: col+=1
    cs=int(cell.get('colspan',1));rs=int(cell.get('rowspan',1));total+=1; empty+=not bool(cell.get_text(strip=True))
    for rr in range(ri,ri+rs):
     for cc in range(col,col+cs):
      if (rr,cc) in grid: overlap=True
      grid[rr,cc]=1
    col+=cs
   widths.append(sum(1 for rr,cc in grid if rr==ri))
  if overlap or len(set(widths))>1 or empty/max(total,1)>.3:
   struct.append(dict(page=n,table=ti,rows=len(rows),widths=sorted(set(widths)),empty=empty,total=total,overlap=overlap))
checks=dict(source_sha256=sha,pages=303,page_order_valid=True,missing_local_links=missing,missing_anchors=badanchors,asset_hash_mismatch=asset_mismatch,unresolved_unicode_pages=unicode,table_structure_flags=struct)
(root/'_проверка/current_review/integrity.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
body=MarkdownIt('commonmark',{'html':True}).render(text)
(root/'_проверка/current_review/rendered.html').write_text('<html><head><meta charset="utf-8"><base href="../../"><style>body{font:16px Arial;max-width:1200px;margin:auto}table{display:block;overflow-x:auto;border-collapse:collapse;margin:20px 0}td,th{border:1px solid #777;padding:6px;min-width:80px}img{max-width:100%}</style></head><body>'+body+'</body></html>')
print(json.dumps({k:v for k,v in checks.items() if k!='table_structure_flags'},ensure_ascii=False));print('table flags',len(struct));print(struct)
