"""Render one local Markdown bundle; no claim of PDF content verification."""
from pathlib import Path
import argparse,sys,json,hashlib,urllib.parse
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from render_results import CSS

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();source=a.input.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    soup=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).enable('table').render(source.read_text()),'html.parser')
    for el in soup.find_all(['script','iframe','object','embed']):el.decompose()
    for el in soup.find_all(True):
        for attr in list(el.attrs):
            if attr.lower().startswith('on'):del el[attr]
    missing=[]
    for image in soup.find_all('img'):
        target=(source.parent/urllib.parse.unquote(image.get('src',''))).resolve()
        if target.is_file() and target.is_relative_to(source.parent):image['src']=target.as_uri();image['loading']='lazy'
        else:missing.append(image.get('src'))
    for table in list(soup.find_all('table')):
        wrapper=soup.new_tag('div');wrapper['class']='scroll';table.wrap(wrapper)
    html=out/'report.html';html.write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+CSS+'</style>'+str(soup))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000});page.route('http://**/*',lambda r:r.abort());page.route('https://**/*',lambda r:r.abort());page.goto(html.as_uri(),wait_until='domcontentloaded',timeout=120000)
        widths=[]
        for width in [1440,390]:
            page.set_viewport_size({'width':width,'height':1000});page.screenshot(path=str(out/f'width_{width}.png'));widths.append({'width':width,'document_overflow':page.evaluate('document.documentElement.scrollWidth>innerWidth')})
        result={'report_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'anchors':page.locator('[id^="pdf-page-"]').count(),'tables':page.locator('table').count(),'images':page.locator('img').count(),'missing_images':missing,'widths':widths,'scope':'Browser rendering; not full source content review'};browser.close()
    (out/'render_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
    if missing:raise SystemExit(1)
if __name__=='__main__':main()
