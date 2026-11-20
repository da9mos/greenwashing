"""Offline rendering of saved primary MD; no claim of full source visual review."""
from pathlib import Path
import hashlib, json, sys, re, urllib.parse
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
from playwright.sync_api import sync_playwright
from render_results import CSS
BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'_проверка/Просмотр_корпуса'
def main():
    OUT.mkdir(parents=True,exist_ok=True);records=[]
    valid=json.loads((BASE/'_проверка/native_corpus_validation.json').read_text())['reports']
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
        for source in sorted((BASE/'Все_отчёты_MD').glob('*/*/report.md')):
            rid=source.parent.name;digest=hashlib.sha256(source.read_bytes()).hexdigest()
            if valid.get(rid,{}).get('state')!='published' or valid[rid].get('final_md_sha256')!=digest:continue
            folder=OUT/rid;folder.mkdir(exist_ok=True);receipt=folder/'render_check.json'
            if receipt.exists():
                old=json.loads(receipt.read_text())
                if old.get('report_sha256')==digest:records.append(old);continue
            soup=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).enable('table').render(source.read_text()),'html.parser')
            for node in soup.find_all(['script','iframe','object','embed']):node.decompose()
            for node in soup.find_all(True):
                for attr in list(node.attrs):
                    if attr.lower().startswith('on'):del node[attr]
            for image in soup.find_all('img'):
                target=(source.parent/urllib.parse.unquote(image.get('src',''))).resolve()
                if target.is_file() and target.is_relative_to(source.parent.resolve()):image['src']=target.as_uri();image['loading']='lazy'
                else:raise ValueError(f'Unresolved local image {rid}: {image.get("src")}')
            for table in list(soup.find_all('table')):
                wrap=soup.new_tag('div');wrap['class']='scroll';table.wrap(wrap)
            html='<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+CSS+'details img{display:block}body{box-sizing:border-box;width:100%}</style>'+str(soup)
            (folder/'report.html').write_text(html)
            page=browser.new_page(viewport={'width':1440,'height':1000});page.route('http://**/*',lambda r:r.abort());page.route('https://**/*',lambda r:r.abort())
            page.goto((folder/'report.html').as_uri(),wait_until='domcontentloaded',timeout=120000)
            widths=[]
            for width in (1440,390):
                page.set_viewport_size({'width':width,'height':1000});overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
                page.screenshot(path=str(folder/f'width_{width}.png'))
                widths.append({'width':width,'document_overflow':overflow})
            record={'report_id':rid,'report_sha256':digest,'page_anchors':page.locator('[id^="pdf-page-"]').count(),'expected_pages':valid[rid]['pages'],'tables_rendered':page.locator('table').count(),'image_references':page.locator('img').count(),'widths':widths,'scope':'Complete saved MD parsed and browser-rendered; two viewport layouts tested. This does not verify every source object or reading order.'}
            if record['page_anchors']!=record['expected_pages']:raise ValueError(f'Anchor count {rid}')
            receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');records.append(record);page.close()
            print('RENDER',rid,len(records),flush=True)
            (OUT/'render_summary.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
        browser.close()
    (OUT/'render_summary.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    print('Rendered',len(records),'reports',sum(r['page_anchors'] for r in records),'pages; overflow',sum(w['document_overflow'] for r in records for w in r['widths']))
if __name__=='__main__':main()
