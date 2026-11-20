import sys,re,json,html
from pathlib import Path
import pymupdf
sys.path.insert(0,'/private/tmp/sber-diff-libs');from bs4 import BeautifulSoup
S=json.load(open('source.json'));D=pymupdf.open(S['source_pdf']);P=Path('result/report.md');report=P.read_text();count=0
normalize=lambda t:''.join(t.split()).replace('\x07','').replace('\uf02d','Оглавление').replace('\uf0e4','↗').replace('\uf0e6','↘')
parts=[]
for n,section in re.findall(r'<!-- pdf_page: (\d+) -->(.*?)(?=<!-- pdf_page:|\Z)',report,re.S):
 source={}
 for b in D[int(n)-1].get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   text=''.join(sp['text'] for sp in l['spans']);sizes=[sp['size'] for sp in l['spans'] if sp['text'].strip()]
   if sizes:source[normalize(text)]=min(sizes)
 def tag(m):
  global count
  pieces=re.split(r'<br\s*/?>',m[1]);texts=[BeautifulSoup(v,'html.parser').get_text() for v in pieces];sizes=[source.get(normalize(t),0) for t in texts if t.strip()]
  text=' '.join(texts)
  if sizes and min(sizes)>=11.8 and sum(c.isalpha() for c in text)>=5 and len(text)<350:
   count+=1;level=2 if max(sizes)>=16 else 3;return f'<h{level}>'+m[1]+f'</h{level}>'
  return m[0]
 section=re.sub(r'<p>(.*?)</p>',tag,section,flags=re.S);parts.append(f'<!-- pdf_page: {n} -->'+section)
P.write_text(report.split('<!-- pdf_page:',1)[0]+''.join(parts))
p=Path('result/_проверка/changes.json');d=json.loads(p.read_text());d['global_changes'].append(f'Preserved {count} source large-font text blocks as HTML h2/h3 headings; native text unchanged.');p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print('headings',count)
