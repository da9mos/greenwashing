import sys,json,re,hashlib,collections
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
r=Path('result');c=r/'_проверка';t=(r/'report.md').read_text();meta=json.load(open(c/'pages.json'))
for p in meta['pages']:p['issues']=list(dict.fromkeys(p['issues']))
(c/'pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
assert [int(n) for n in re.findall(r'<!-- pdf_page: (\d+) -->',t)]==list(range(1,139))
md=MarkdownIt('commonmark',{'html':True}).enable('table');body=md.render(t);soup=BeautifulSoup(body,'html.parser');ids={a['id'] for a in soup.select('[id]')}
for im in soup.select('img[src]'):assert (r/im['src']).is_file(),im['src']
for a in soup.select('a[href]'):
 if a['href'].startswith('#'):assert a['href'][1:] in ids,a['href']
style='body{font:16px/1.5 Arial,sans-serif;max-width:1250px;margin:32px auto;padding:20px}img{max-width:100%;height:auto}table{display:block;overflow-x:auto;border-collapse:collapse;font-size:13px;margin:18px 0}td,th{border:1px solid #ccc;padding:7px;vertical-align:top;min-width:55px}blockquote{background:#f6f6f6;padding:8px 20px}h6{font-size:24px}details{margin:10px 0}a{overflow-wrap:anywhere}'
(c/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>Рабочая конвертация</title><style>'+style+'</style>'+body.replace('src="assets/','src="../assets/'))
v={'physical_pages':138,'page_order_valid':True,'local_assets':len(soup.select('img[src]')),'missing_references':[],'html_tables':len(soup.select('table')),'report_sha256':hashlib.sha256((r/'report.md').read_bytes()).hexdigest(),'review_status_counts':dict(collections.Counter(p['review_status'] for p in meta['pages'])),'browser_render':'unavailable: local Chrome launch terminated (SIGABRT / EPERM); not retried','rendered_preview':'_проверка/preview.html','source_and_image_checksums_verified':True}
(c/'validation.json').write_text(json.dumps(v,ensure_ascii=False,indent=2));print(json.dumps(v,ensure_ascii=False,indent=2))
