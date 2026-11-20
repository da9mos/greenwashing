import sys,re,json,html
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
r=Path('result');md=(r/'report.md').read_text();pages=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',md)));assert pages==list(range(1,136))
registry=json.load(open(r/'_проверка/pages.json'));assert len(registry['pages'])==135
for p in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',md):assert (r/p).is_file(),p
for n in re.findall(r'\]\(#pdf-page-(\d+)\)',md):assert f'id="pdf-page-{n}"' in md
body=MarkdownIt('commonmark',{'html':True}).enable('table').render(md)
page='<!doctype html><html lang="ru"><meta charset="utf-8"><title>Устойчивое лидерство</title><style>body{font:17px/1.5 sans-serif;max-width:1250px;margin:auto;padding:30px}img{max-width:100%}table{display:block;overflow:auto;border-collapse:collapse}td,th{border:1px solid #aaa;padding:5px}blockquote{background:#fff7d1;padding:10px}a{overflow-wrap:anywhere}</style>'+body+'</html>'
(r/'_проверка/preview.html').write_text(page)
soup=BeautifulSoup(page,'html.parser');summary={'physical_page_markers':len(pages),'source_images':len(list((r/'assets').glob('*.png'))),'tables_rendered':len(soup.find_all('table')),'report_chars':len(md),'local_image_links_valid':True,'internal_page_targets_valid':True,'rendered_html':'preview.html','visual_render_review':False,'conversion_status_counts':dict(__import__('collections').Counter(p['conversion_status'] for p in registry['pages'])),'review_status_counts':dict(__import__('collections').Counter(p['review_status'] for p in registry['pages']))}
(r/'_проверка/validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(summary)
