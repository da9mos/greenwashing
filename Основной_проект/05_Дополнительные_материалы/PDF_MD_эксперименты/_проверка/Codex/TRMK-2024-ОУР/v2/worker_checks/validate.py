from pathlib import Path
import sys,re,json,hashlib,collections,unicodedata
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
R=Path('result'); C=R/'_проверка'; S=json.load(open('source.json'))
base=(C/'baseline/report.md').read_text(); report=(R/'report.md').read_text()
sections=lambda s:dict((int(n),t) for n,t in re.findall(r'<!-- pdf_page: (\d+) -->(.*?)(?=<!-- pdf_page:|\Z)',s,re.S))
b=sections(base);f=sections(report);assert list(f)==list(range(1,129))
def text_inventory(t):
 tags=re.findall(r'<p>.*?</p>|<h[23]>.*?</h[23]>|<table>.*?</table>',t,re.S)
 text=BeautifulSoup(''.join(tags),'html.parser').get_text().replace('\uf02d','Оглавление').replace('\uf0e4','↗').replace('\uf0e6','↘').replace('\x07','')
 return collections.Counter(c for c in text if not c.isspace())
inventory=[];table_records=[]
for n,t in f.items():
 original=b[n];end=len(original)
 for token in ['> Служебная пометка:', '> Служебная информация:', '<details>']:
  if token in original:end=min(end,original.index(token))
 expected=text_inventory(original[:end]);actual=text_inventory(t)
 assert expected==actual,(n,expected-actual,actual-expected)
 inventory.append({'pdf_page':n,'native_inventory_after_documented_unicode_normalization_matches':True,'scope':'Character inventory only; not reading order or table associations'})
 for ti,tab in enumerate(BeautifulSoup(t,'html.parser').find_all('table'),1):
  table_records.append({'pdf_page':n,'table':ti,'rows':len(tab.find_all('tr')),'merged_cells':sum(int(c.get('colspan',1))>1 for c in tab.find_all('td')),'empty_cells':sum(not c.get_text(strip=True) for c in tab.find_all('td')),'review_status':'geometry_checked_content_pending' if n in [8,31,35,117,120] else 'pending'})
refs=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',report);missing=[p for p in refs if not (R/p).is_file()];assert not missing
ids=set(re.findall(r'id="([^"]+)"',report));targets=re.findall(r'href="#([^"]+)"',report);assert set(targets)<=ids
source_hash=hashlib.sha256(Path(S['source_pdf']).read_bytes()).hexdigest()
coverage=json.load(open(C/'native_coverage.json'))
assert source_hash==coverage['source_sha256']
index=json.load(open(S['index']));image_checks=[]
for item in index['pages']:
 n=item['pdf_page']; path=R/f'assets/page_{n:04}.png';digest=hashlib.sha256(path.read_bytes()).hexdigest();assert digest==item['image_sha256'];image_checks.append({'pdf_page':n,'source_image_hash_matches':True})
(C/'final_integrity.json').write_text(json.dumps({'source_sha256':source_hash,'report_sha256':hashlib.sha256((R/'report.md').read_bytes()).hexdigest(),'physical_pages':128,'page_markers_in_order_unique':True,'local_image_references':len(refs),'missing_local_images':missing,'internal_links':len(targets),'missing_internal_targets':[],'native_text_inventory':inventory,'source_images':image_checks,'scope':'Structural and character checks; does not establish source fidelity'},ensure_ascii=False,indent=2)+'\n')
(C/'table_diagnostics.json').write_text(json.dumps(table_records,ensure_ascii=False,indent=2)+'\n')
# Regenerate the renderer HTML with the same Markdown parser and CSS. Chrome launch is separately recorded as failed.
sys.path.insert(0,str(Path(S['index']).parents[3]/'tools'))
from render_results import CSS
soup=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).enable('table').render(report),'html.parser')
for image in soup.find_all('img'):image['src']=(R/image['src']).resolve().as_uri();image['loading']='lazy'
for table in list(soup.find_all('table')):
 wrapper=soup.new_tag('div');wrapper['class']='scroll';table.wrap(wrapper)
(C/'render/report.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+CSS+'</style>'+str(soup))
(C/'render/render_check.json').write_text(json.dumps({'report_sha256':hashlib.sha256((R/'report.md').read_bytes()).hexdigest(),'html_generated':True,'browser_render_status':'blocked','error':'Chrome terminated at launch with SIGABRT in current execution environment (Playwright TargetClosedError).','screenshots_created':False,'widths_reviewed':[],'scope':'HTML generation succeeded; visual rendering at 1440/390 not verified'},ensure_ascii=False,indent=2)+'\n')
if not (C/'baseline/native_coverage.json').exists():(C/'baseline/native_coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n')
coverage['baseline_report_sha256']=coverage.pop('report_sha256',coverage.get('baseline_report_sha256'))
coverage.update(final_report_sha256=hashlib.sha256((R/'report.md').read_bytes()).hexdigest(),final_native_inventory_after_documented_normalization_matches=True,scope='Original native coverage applies to baseline; final inventory is verified separately in final_integrity.json. No full semantic review claimed.',pending_pages=[n for n in range(1,129) if n not in [1,2,4,5,128]])
(C/'native_coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'pages':len(f),'tables':len(table_records),'assets':len(refs),'source_sha256':source_hash,'native_inventory_all_pages':True,'links_valid':True},ensure_ascii=False))
