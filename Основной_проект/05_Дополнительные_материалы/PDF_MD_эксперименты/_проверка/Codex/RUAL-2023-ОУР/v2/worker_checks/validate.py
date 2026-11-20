from pathlib import Path
import sys,re,json,hashlib,collections
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1];s=(root/'report.md').read_text();md=MarkdownIt('commonmark',{'html':True});render=md.render(s);soup=BeautifulSoup(render,'html.parser')
markers=[int(v) for v in re.findall(r'<!-- pdf_page: (\d+) -->',s)];assert markers==list(range(1,207))
reg=json.load(open(root/'_проверка/pages.json'));assert [p['pdf_page'] for p in reg['pages']]==markers
ids=[x['id'] for x in soup.select('[id]')];assert len(ids)==len(set(ids))
missing=[]
for el in soup.select('[href], [src]'):
 v=el.get('href',el.get('src',''))
 if v.startswith('#'):
  if v[1:] not in ids:missing.append(v)
 elif '://' not in v and not v.startswith(('mailto:','tel:','data:')):
  if not (root/v).is_file():missing.append(v)
assert not missing,missing
assert '\ufffd' not in s
assert not re.search(r'\d\t\d\t\d',s)
assert 'точность OCR не подтверждена' not in s
style='body{font:18px/1.5 Arial,sans-serif;max-width:1600px;margin:32px auto;padding:0 24px;color:#222}table{border-collapse:collapse;display:block;max-width:100%;overflow-x:auto;margin:20px 0}td,th{border:1px solid #aaa;padding:8px;vertical-align:top;min-width:55px;white-space:normal;overflow-wrap:anywhere}img{max-width:100%;height:auto}h2{font-size:30px}blockquote{background:#f4f4f4;padding:10px}details{margin:30px 0}'
head='<!doctype html><html lang="ru"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src file: data:; style-src \'unsafe-inline\'"><style>'+style+'</style><body>'
(root/'_проверка/report.preview.html').write_text(head+render.replace('src="assets/','src="../assets/')+'</body></html>')
parts=re.split(r'(?=<!-- pdf_page: \d+ -->)',s)
for n in [2,5,51,137,203,205,206]:
 r=md.render(parts[n]);r=r[:r.find('<details>')] if '<details>' in r else r
 (root/f'_проверка/render_{n}.html').write_text(head+r+'</body></html>')
counts=collections.Counter(p['review_status'] for p in reg['pages'])
result={'report_sha256':hashlib.sha256(s.encode()).hexdigest(),'physical_page_markers':len(markers),'page_order_valid':True,'registry_all_pages':True,'assets_referenced':len(soup.select('img')),'assets_missing':missing,'unique_anchors':len(ids),'table_count':len(soup.select('table')),'unicode_replacement_characters':s.count('\ufffd'),'ocr_tsv_metadata_remaining':False,'review_status_counts':dict(counts),'html_render_completed':True,'full_document_visual_render_review':False}
(root/'_проверка/validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
