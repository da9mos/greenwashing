from pathlib import Path
import sys,json,re,hashlib,collections
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf as fitz
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
root=Path('result');p=root/'_проверка';s=(root/'report.md').read_text();doc=fitz.open(json.load(open('source.json'))['source_pdf']);changes=[]
def norm(t):return ' '.join(t.split())
def section(m):
 n=int(m[1]);c=m[2];heads={}
 for bi,b in enumerate(doc[n-1].get_text('dict')['blocks']):
  for line in b.get('lines',[]):
   spans=line['spans'];t=norm(''.join(x['text'] for x in spans));size=max((x['size'] for x in spans),default=0)
   if len(re.findall('[А-Яа-яЁё]',t))>=5 and size>=12 and not re.search(r'\d',t):heads[t]=(2 if size>=17 else 3,bi)
 def heading(pm):
  t=norm(BeautifulSoup(pm[1],'html.parser').get_text());v=heads.get(t)
  if not v:return pm[0]
  level,bi=v;changes.append({'pdf_page':n,'text':t,'level':level,'source_block':bi});return f'<h{level}>'+pm[1]+f'</h{level}>'
 c=re.sub(r'<p>(.*?)</p>',heading,c,flags=re.S)
 return '<!-- pdf_page: '+str(n)+' -->'+c
s=re.sub(r'<!-- pdf_page: (\d+) -->(.*?)(?=<!-- pdf_page:|\Z)',section,s,flags=re.S)
(root/'report.md').write_text(s)
(p/'heading_restoration.json').write_text(json.dumps({'scope':'Структурная разметка исходных строк по размеру шрифта; не семантическая сверка непроверенных страниц.','changes':changes},ensure_ascii=False,indent=2)+'\n')
sha=hashlib.sha256(s.encode()).hexdigest()
for f in ['native_coverage.json','revision_coverage.json','validation.json']:
 d=json.loads((p/f).read_text());d['report_sha256']=sha;(p/f).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
d=json.loads((p/'pages.json').read_text());inspected=set(json.loads((p/'validation.json').read_text())['source_images_inspected'])
for r in d['pages']:
 r['source_image_inspected']=r['pdf_page'] in inspected
 r['display_review_status']='blocked'
 r['display_review_issue']='Chrome не запустился в ограниченной среде; HTML создан, снимки отсутствуют.'
(p/'pages.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
# Validate final serialization after heading markup changes.
assert list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',s)))==list(range(1,159))
soup=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).enable('table').render(s),'html.parser');ids={x['id'] for x in soup.find_all(id=True)}
for el in soup.find_all(['a','img']):
 url=el.get('href') if el.name=='a' else el.get('src')
 if not url:continue
 if url.startswith('#'):assert url[1:] in ids,url
 elif '://' not in url and not url.startswith('mailto:'):assert (root/url).is_file(),url
(p/'render/render_check.json').write_text(json.dumps({'report_sha256':sha,'status':'blocked','html_generated':True,'screenshots_generated':False,'widths_tested':[],'reason':'TargetClosedError / Chrome SIGABRT; see launch.log','scope':'Display was not visually checked; not a full PDF comparison.'},ensure_ascii=False,indent=2)+'\n')
print('Restored heading lines:',len(changes),'SHA256:',sha)
