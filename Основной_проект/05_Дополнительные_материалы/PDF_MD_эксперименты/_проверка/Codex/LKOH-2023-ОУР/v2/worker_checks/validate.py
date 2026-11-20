import json,re,hashlib
from pathlib import Path
from markdown_it import MarkdownIt
out=Path('result');md=(out/'report.md').read_text();p=json.load(open(out/'_проверка/pages.json'))
marks=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',md)));assert marks==list(range(1,116))
assert len(p['pages'])==115
local=re.findall(r'\]\((assets/[^)]+)\)',md);assert len(local)==115
assert all((out/x).is_file() for x in local)
anchors=set(re.findall(r'id="([^"]+)"',md));targets=re.findall(r'\]\(#([^)]*)\)',md);assert all(t in anchors for t in targets)
assert all((out/'_проверка/pages'/f'{i:04}.md').stat().st_size>50 for i in range(1,116))
body=MarkdownIt('commonmark',{'html':True}).enable('table').render(md)
html='<!doctype html><html lang="ru"><meta charset="utf-8"><title>ЛУКОЙЛ — конвертация</title><style>body{font:17px/1.5 sans-serif;max-width:1200px;margin:35px auto;padding:20px}pre{overflow-x:auto;background:#f5f5f5;padding:16px;font:13px/1.5 monospace}img{max-width:100%;height:auto}table{border-collapse:collapse;display:block;overflow-x:auto}td,th{padding:5px;border:1px solid #ccc}</style><body>'+body+'</body></html>'
# HTML stays beside report so relative asset paths work.
(out/'_проверка/rendered.html').write_text(html.replace('src="assets/','src="../assets/'))
res={'physical_page_markers':len(marks),'page_registry_entries':len(p['pages']),'existing_source_images':len(local),'resolved_internal_links':len(targets),'report_sha256':hashlib.sha256(md.encode()).hexdigest(),'converted_pages':115,'checked_pages':[1],'review_pending_pages':114,'html_rendered':True,'visual_render_check':'pending'}
(out/'_проверка/validation.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(json.dumps(res,ensure_ascii=False,indent=2))
