import sys,json,re,hashlib,html
from pathlib import Path
from urllib.parse import unquote
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
root=Path('result').resolve();ck=root/'_проверка';text=(root/'report.md').read_text();data=json.load(open(ck/'pages.json'))
markers=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',text)));assert markers==list(range(1,130))
assert len(data['pages'])==129
assert not any(r.get('native_lines_not_found') for r in data['pages'])
anchors=set(re.findall(r'id="([^"]+)"',text))
missing=[]
for target in re.findall(r'\]\((?:<([^>]+)>|([^\s)]+))\)',text):
 path=next(x for x in target if x)
 if path.startswith('#'):
  if path[1:] not in anchors:missing.append(path)
 elif not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',path):
  if not (root/unquote(path)).exists():missing.append(path)
assert not missing,missing
s=json.load(open('source.json'));idx=json.load(open(s['index']));checks=[]
for r in idx['pages']:
 n=r['pdf_page'];asset=root/'assets'/f'page_{n:04}.png';checks.append(hashlib.sha256(asset.read_bytes()).hexdigest()==r['image_sha256'])
assert all(checks)
body=MarkdownIt('commonmark',{'html':True}).enable('table').render(text)
body=body.replace('src="assets/','src="../assets/').replace('<table>','<div class="table-scroll"><table>').replace('</table>','</table></div>')
style='body{font:16px/1.5 system-ui,sans-serif;color:#202532;max-width:1250px;margin:40px auto;padding:0 24px}img{max-width:100%;height:auto}table{border-collapse:collapse;min-width:800px;width:100%;font-size:14px}td,th{border:1px solid #bbc2ca;padding:8px;vertical-align:top}th{background:#eef1f8}.table-scroll{overflow-x:auto;margin:24px 0}blockquote{border-left:3px solid #bbb;padding-left:16px;color:#60656b}a{color:#1751bb}details{margin:20px 0}h1,h2{line-height:1.2}'
(ck/'preview.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Отчет об устойчивом развитии 2024</title><style>'+style+'</style><body>'+body+'</body></html>')
summary={'physical_page_markers':len(markers),'sequence_correct':True,'page_registry_count':129,'all_local_links_exist':True,'internal_targets_exist':True,'copied_images_hashes_match':all(checks),'native_line_coverage':'129/129 pages: all complete native lines below established navigation area occur in transcription after normalization; this is not visual verification','html_tables':body.count('<table>'),'review_checked':[p['pdf_page'] for p in data['pages'] if p['review_status']=='checked'],'review_pending':[p['pdf_page'] for p in data['pages'] if p['review_status']=='pending']}
(ck/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False))
