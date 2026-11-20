from pathlib import Path
import re,json,hashlib
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
out=Path('result');c=out/'_проверка';md=(out/'report.md').read_text();data=json.load(open(c/'pages.json'))
nums=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',md)));assert nums==list(range(1,115))
anchors=set(re.findall(r'id="([^"]+)"',md));targets=re.findall(r'\]\(#([^)]*)\)',md);assert all(t in anchors for t in targets)
images=re.findall(r'!\[[^]]*\]\(([^)]+)\)',md);assert len(images)==114
assert all((out/i).is_file() for i in images)
assert all(p['conversion_status']=='converted' for p in data['pages'])
assert not re.search(r'ZZTABLE|TABLE\d+ZZ',md)
parser=MarkdownIt('commonmark',{'html':True}).enable('table')
body=parser.render(md).replace('src="assets/','src="../assets/')
style='body{font:16px/1.5 system-ui;max-width:1250px;margin:35px auto;padding:20px;color:#222}img{max-width:100%;height:auto}table{display:block;max-width:100%;overflow-x:auto;border-collapse:collapse;margin:24px 0}td,th{border:1px solid #aaa;padding:7px;min-width:65px;vertical-align:top}blockquote{background:#f2f3f5;padding:10px;color:#555}details{margin:20px 0}a{color:#155ca0}'
(c/'report.preview.html').write_text('<!doctype html><meta charset="utf-8"><style>'+style+'</style>'+body)
shots=[]
# Browser launch was attempted; macOS sandbox denied MachPortRendezvousServer.
result={'physical_pages':len(nums),'page_order':'passed','local_images':len(images),'all_images_exist':True,'internal_targets':len(targets),'all_internal_targets_exist':True,'html_tables':len(BeautifulSoup(body,'html.parser').find_all('table')),'render_screenshots':shots,'visual_render_status':'blocked: Chromium bootstrap_check_in Permission denied (1100)','report_sha256':hashlib.sha256(md.encode()).hexdigest(),'limitation':'Markdown преобразован в HTML и разобран парсером; визуальное отображение не проверено. Проверка структуры и ссылок не подтверждает точность транскрипции.'}
(c/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(result)
