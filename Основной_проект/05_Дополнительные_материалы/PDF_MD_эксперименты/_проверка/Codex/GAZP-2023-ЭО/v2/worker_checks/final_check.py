import json,re,hashlib,sys
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[2];out=root/'result';c=out/'_проверка';s=json.loads((root/'source.json').read_text());reg=json.loads(Path(s['index']).read_text());report=(out/'report.md').read_text();state=json.loads((c/'pages.json').read_text())
markers=[int(n) for n in re.findall(r'<!-- pdf_page: (\d+) -->',report)]
assert markers==list(range(1,85))
assert [p['pdf_page'] for p in state['pages']]==markers
missing=[];bad_hash=[]
for p in reg['pages']:
 asset=out/'assets'/f"page_{p['pdf_page']:04}.png"
 if not asset.exists():missing.append(str(asset))
 elif hashlib.sha256(asset.read_bytes()).hexdigest()!=p['image_sha256']:bad_hash.append(p['pdf_page'])
assert not missing and not bad_hash
soup=BeautifulSoup((c/'preview.html').read_text(),'html.parser')
for im in soup.find_all('img'):assert (c/im['src']).exists()
checked=[p['pdf_page'] for p in state['pages'] if p['review_status']=='checked'];pending=[p['pdf_page'] for p in state['pages'] if p['review_status']=='pending']
for p in state['pages']:
 p['issues']=list(dict.fromkeys(p['issues']))
 if p['pdf_page'] in [10,11,39]:p['issues'].append('Блок-схема: ложные таблицы автоматического извлечения заменены пространственным текстовым представлением и исходным изображением; связи схемы не сверены полностью.')
 if p['review_status']=='pending':p['next_action']='Полное визуальное чтение исходной страницы, сверка порядка блоков, каждой ячейки таблиц, индексов, сносок и графических связей.'
state['render_status']='pending: HTML generated and parsed locally; headless Chrome launch failed (SIGABRT in sandbox); visual rendering not inspected'
(c/'pages.json').write_text(json.dumps(state,ensure_ascii=False,indent=2))
result={'physical_pages':84,'markers_complete_and_ordered':True,'registry_complete':True,'assets_count':84,'image_hashes_match_input_registry':True,'source_sha256_matches_registry':json.loads((c/'source.json').read_text())['sha256']==reg['source_sha256'],'local_references_exist':True,'rendered_html_images':len(soup.find_all('img')),'html_tables':len(soup.find_all('table')),'markdown_tables':3,'checked_pages':checked,'pending_pages':pending,'report_sha256':hashlib.sha256((out/'report.md').read_bytes()).hexdigest(),'visual_render_check':'not completed: local headless Chrome failed to launch; no screenshot produced'}
(c/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
