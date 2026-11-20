import re,json,sys,hashlib,collections
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
r=Path(__file__).resolve().parents[1];d=r/'_проверка'
s=(r/'report.md').read_text();old=(d/'report.native.md').read_text();md=MarkdownIt('commonmark',{'html':True})
def split(s):
 parts=re.split(r'<!-- pdf_page: (\d+) -->',s);return {int(parts[i]):parts[i+1] for i in range(1,len(parts),2)}
a,b=split(old),split(s)
def body(t):
 t=re.split(r'> Служебная пометка:|> Служебная информация:|<details>',t)[0]
 return BeautifulSoup(md.render(t),'html.parser').get_text()
changes=[]
for n in range(1,97):
 x=collections.Counter(c for c in body(a[n]) if not c.isspace());y=collections.Counter(c for c in body(b[n]) if not c.isspace())
 if x!=y:changes.append({'page':n,'removed':dict(x-y),'added':dict(y-x)})
refs=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',s);bad=[v for v in refs if not (r/v).is_file()]
anchors=set(re.findall(r'id="([^"]+)"',s));links=re.findall(r'href="#([^"]+)"',s);missing=[v for v in links if v not in anchors]
checks={'page_markers':re.findall(r'<!-- pdf_page: (\d+) -->',s),'pages_in_order':list(b)==list(range(1,97)),'image_references':len(refs),'missing_images':bad,'missing_internal_anchors':missing,'report_sha256':hashlib.sha256(s.encode()).hexdigest(),'character_deltas_excluding_whitespace':changes,'scope':'Character deltas between native body and final body; not semantic source review.'}
(d/'integrity.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in checks.items() if k!='page_markers'},ensure_ascii=False,indent=2))
