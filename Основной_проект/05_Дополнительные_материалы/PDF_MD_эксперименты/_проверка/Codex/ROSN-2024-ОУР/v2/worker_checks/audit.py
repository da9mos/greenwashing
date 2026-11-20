import sys,json,re,collections
sys.path.insert(0,'/private/tmp/sber-pdf-libs');import pymupdf
from pathlib import Path
s=json.load(open('source.json')); d=pymupdf.open(s['source_pdf']);out=[]
def tokens(t):
 t=t.lower().replace('\u00ad\n','').replace('\u00ad','');return collections.Counter(re.findall(r'[а-яёa-z0-9]',t))
for i,p in enumerate(d):
 f=Path(f'result/_проверка/pages/{i+1:04}.md')
 if not f.exists():continue
 raw=p.get_text(clip=pymupdf.Rect(0,70,p.rect.width,805)) if p.rect.width>900 and len(p.get_text())>100 else p.get_text()
 a=tokens(raw);b=tokens(f.read_text());miss=a-b
 out.append({'page':i+1,'source_tokens':sum(a.values()),'missing_tokens':sum(miss.values()),'missing':dict(miss)})
Path('result/_проверка/coverage.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print([(r['page'],r['source_tokens'],r['missing_tokens']) for r in out if r['missing_tokens']>25])
