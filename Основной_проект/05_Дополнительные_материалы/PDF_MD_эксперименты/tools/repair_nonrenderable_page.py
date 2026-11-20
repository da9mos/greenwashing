"""Represent a proved non-Unicode source glyph by its source crop, not guessed text."""
from pathlib import Path
import copy,hashlib,json,re,shutil
import native_candidate as native
BASE=Path(__file__).resolve().parents[1]
RID='GAZP-2024-ОУР';NUMBER=2;SENTINEL='␀'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def main():
    batchpath=BASE/'_проверка/native_candidate_batch.json';batch=load(batchpath)
    if batch['reports_finished']!=batch['reports_requested']:raise ValueError('Wait for frozen producer to finish')
    folder=BASE/'_проверка/native_candidates'/RID;checks=folder/'_проверка';report=folder/'report.md';source=BASE/'_источники'/f'{RID}.pdf'
    receipt=checks/'nonrenderable_glyph_repair.json'
    if receipt.exists() and load(receipt).get('report_after_sha256')==sha(report):print('Repair already applied');return
    before=sha(report);data=load(checks/'pages.json');old=data['pages'][NUMBER-1];assets=load(checks/'native_assets.json')
    with native.fitz.open(source) as doc:
        page=doc[NUMBER-1];raw=page.get_text('rawdict');allchars=[];bad=[]
        for block in raw['blocks']:
            for line in block.get('lines',[]):
                for span in line['spans']:
                    for char in span['chars']:
                        if SENTINEL in char['c']:raise ValueError('Sentinel exists in source')
                        if char['c']=='\x00':bad.append({'glyph_id':len(allchars),'font':span['font'],'bbox':list(char['bbox']),'origin':list(char['origin']),'old_codepoint':'U+0000'})
                        allchars.append(char['c'])
        if len(bad)!=1 or bad[0]['font']!='icons_font_gaz_csr2024':raise ValueError('Unexpected source glyph; no automatic repair')
        glyph=bad[0];box=native.fitz.Rect(glyph['bbox']);asset=f'source_glyph_pdf{NUMBER:04d}_{glyph["glyph_id"]}.png'
        page.get_pixmap(matrix=native.fitz.Matrix(6,6),clip=box+(-1,-1,1,1),alpha=False).save(folder/'assets'/asset)
        class Proxy:
            def __getattr__(self,name):return getattr(page,name)
            def get_text(self,*args,**kwargs):
                result=copy.deepcopy(page.get_text(*args,**kwargs))
                if args and args[0]=='rawdict':
                    for b in result['blocks']:
                        for l in b.get('lines',[]):
                            for s in l['spans']:
                                for c in s['chars']:
                                    if c['c']=='\x00':c['c']=SENTINEL
                return result
        body,info=native.convert_page(Proxy())
        if body.count(SENTINEL)!=1:raise ValueError('Sentinel ownership mismatch')
        body=body.replace(SENTINEL,f'<img src="assets/{asset}" alt="" width="16" height="16"/>')
        links,unresolved=native.source_links(page,doc.resolve_names(),len(doc));body+=links
        original_count=native.Counter(c for x in allchars for c in x if not c.isspace());expected=original_count.copy();expected['\x00']-=1;expected+=native.Counter()
        actual=native.Counter(c for c in native.BeautifulSoup(native.MarkdownIt('commonmark',{'html':True}).render(body.split('> Служебная информация: ссылки исходного PDF')[0]),'html.parser').get_text() if not c.isspace())
        if expected!=actual:raise ValueError('Other native characters changed')
        projection={**glyph,'representation':'source_image','asset':asset,'asset_sha256':sha(folder/'assets'/asset),'source_sha256':sha(source),'exact_unicode_known':False,'source_crop_bbox':list(box+(-1,-1,1,1)),'reason':'Source icon font has NUL in rawdict and .notdef/gid0 in texttrace; icon preserved from original image without guessed Unicode'}
        info['rendered_native_character_inventory_matches']=False
        info['rendered_native_character_inventory_matches_after_explicit_projection']=True
        info['native_graphic_glyph_projections']=[projection]
        record={'pdf_page':NUMBER,'conversion_status':'converted','review_status':'pending','semantic_source_review_completed':False,'verification_scope':'All native glyph IDs once; one nonrenderable source glyph represented by a source crop; remaining visible character inventory exact','issues':['Nonrenderable source glyph preserved as source image; exact Unicode unknown.'],**info}
        if unresolved:record['unresolved_source_links']=unresolved
        replacement=f'<!-- pdf_page: {NUMBER} -->\n<a id="pdf-page-{NUMBER}"></a>\n\n{body}\n\n<details>\n<summary>Источник: PDF-страница {NUMBER}</summary>\n\n![Полная исходная страница {NUMBER}](assets/page_{NUMBER:04d}.png)\n\n</details>'
    md=report.read_text();pattern=rf'<!-- pdf_page: {NUMBER} -->.*?(?=\n*<!-- pdf_page: {NUMBER+1} -->)';matches=list(re.finditer(pattern,md,re.S))
    if len(matches)!=1:raise ValueError('Page not unique')
    history=checks/'repair_history'/before;history.mkdir(parents=True,exist_ok=True)
    for path in [report,checks/'pages.json',checks/'native_coverage.json',checks/'native_assets.json']:shutil.copy2(path,history/path.name)
    new=md[:matches[0].start()]+replacement+'\n\n'+md[matches[0].end():];report.write_text(new)
    data['pages'][NUMBER-1]=record;native.write_json(checks/'pages.json',data)
    assets[asset]=projection['asset_sha256'];native.write_json(checks/'native_assets.json',assets)
    coverage=load(checks/'native_coverage.json');coverage.update(report_sha256=sha(report),all_native_glyphs_assigned_once=all(x['all_native_glyphs_assigned_once']for x in data['pages']),pending_pages=[x['pdf_page']for x in data['pages']if x.get('issues')],explicit_graphic_glyph_projections=1,scope='All native glyph IDs assigned once; one source glyph represented as an image; semantic source review not complete')
    native.write_json(checks/'native_coverage.json',coverage)
    proof={'report_id':RID,'pdf_page':NUMBER,'source_sha256':sha(source),'base_implementation_sha256':native.IMPLEMENTATION_SHA,'repair_implementation_sha256':sha(__file__),'report_before_sha256':before,'report_after_sha256':sha(report),'projections':[projection],'other_native_characters_unchanged':True,'page_glyph_count_unchanged':len(allchars)==record['native_glyphs'],'semantic_source_review_completed':False}
    native.write_json(receipt,proof);batch['reports'][RID].update(coverage);native.write_json(batchpath,batch);print(json.dumps(proof,ensure_ascii=False))
if __name__=='__main__':main()
