import sys,json,re,hashlib,collections
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf as f
R=Path('result');A=R/'_проверка';s=json.load(open('source.json'));d=f.open(s['source_pdf']);t=(R/'report.md').read_text();reg=json.loads((A/'pages.json').read_text())
assert re.findall(r'<!-- pdf_page: (\d+) -->',t)==list(map(str,range(1,137)))
assert [p['pdf_page'] for p in reg['pages']]==list(range(1,137))
assert len(re.findall(r'id="pdf-page-\d+"',t))==136
refs=re.findall(r'\]\((assets/[^)]+)\)',t);assert len(refs)==136
for ref in refs:assert (R/ref).is_file(),ref
for n in re.findall(r'\]\(#pdf-page-(\d+)\)',t):assert 1<=int(n)<=136
idx=json.loads(Path(s['index']).read_text())
for p in idx['pages']:
 path=R/'assets'/('page-%03d.png'%p['pdf_page'])
 assert hashlib.sha256(path.read_bytes()).hexdigest()==p['image_sha256']
chunks=re.split(r'<!-- pdf_page: \d+ -->',t)[1:];coverage=[]
def norm(x):return re.sub(r'[^\w]','',x.lower().replace('\u00ad',''))
for i,(p,chunk) in enumerate(zip(d,chunks),1):
 source='\n'.join(''.join(s['text'] for s in l['spans']) for b in p.get_text('dict')['blocks'] for l in b.get('lines',[]) if abs(l['dir'][1])<.1)
 words=re.findall(r'\w{4,}',source.lower().replace('\u00ad',''))
 cand=norm(chunk);missing=[x for x in words if norm(x) not in cand]
 coverage.append(dict(pdf_page=i,source_horizontal_words=len(words),not_found_words=len(missing),examples=list(dict.fromkeys(missing))[:25],note='Поиск подстрок — диагностика пропусков, не доказательство точности.'))
(A/'coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2))
summary={'page_markers':136,'registry_pages':len(reg['pages']),'source_image_hashes_verified':136,'local_assets_verified':len(refs),'missing_local_links':0,'conversion_status':dict(collections.Counter(p['conversion_status'] for p in reg['pages'])),'review_status':dict(collections.Counter(p['review_status'] for p in reg['pages'])),'source_sha256':hashlib.sha256(Path(s['source_pdf']).read_bytes()).hexdigest(),'report_sha256':hashlib.sha256((R/'report.md').read_bytes()).hexdigest(),'ocr_pages':[132,133]}
(A/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2));print('coverage outliers',[(x['pdf_page'],x['not_found_words'],x['examples'][:5]) for x in coverage if x['not_found_words']>8])
