import sys,json,re,hashlib
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1];s=(root/'report.md').read_text();source=json.load(open(root.parent/'source.json'));pdf=Path(source['source_pdf'])
nums=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',s)))
render=MarkdownIt('commonmark',{'html':True}).enable('table').render(s)
soup=BeautifulSoup(render,'html.parser');ids={x.get('id') for x in soup.find_all(id=True)}
missing=[]
for im in soup.find_all('img'):
 if not (root/im['src']).is_file():missing.append(im['src'])
bad=[a['href'] for a in soup.find_all('a',href=True) if a['href'].startswith('#') and a['href'][1:] not in ids]
# A browser preview of the saved Markdown, rendered with HTML tables enabled.
preview='<!doctype html><meta charset="utf-8"><style>body{font:16px sans-serif;max-width:1100px;margin:32px auto}table{border-collapse:collapse;display:block;overflow:auto}td,th{border:1px solid #aaa;padding:5px;min-width:55px}img{max-width:100%}p{line-height:1.4}</style>'+render
(root/'_проверка/rendered.html').write_text(preview.replace('src="assets/','src="../assets/'))
res={'source_pdf':str(pdf),'source_sha256':hashlib.file_digest(pdf.open('rb'),'sha256').hexdigest(),'physical_pages':295,'page_markers_exact_sequence':nums==list(range(1,296)),'missing_images':missing,'broken_internal_links':bad,'markdown_rendered':True,'rendered_tables':len(soup.find_all('table')),'image_references':len(soup.find_all('img')),'report_sha256':hashlib.sha256(s.encode()).hexdigest(),'remaining_private_use_symbols':sorted(set(c for c in s if 0xe000<=ord(c)<=0xf8ff))}
assert res['page_markers_exact_sequence'] and not missing and not bad
(root/'_проверка/validation.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(json.dumps(res,ensure_ascii=False,indent=2))
