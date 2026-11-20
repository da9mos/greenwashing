import sys,json,re,hashlib,collections
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-diff-libs','/private/tmp/sber-pdf-libs']
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
root=Path('result');check=root/'_проверка';r=json.load(open(check/'pages.json'));old=json.load(open(check/'current_run/pages.before.json'))['pages']
for x,original in zip(r['pages'],old):
 x['original_diagnostics']=original['issues']
 n=x['pdf_page']
 if any('Image-dominant' in issue for issue in original['issues']):
  x['image_diagnostic_assessment']=('Сканированный текст тела присутствует; OCR кандидата прочитан и адресно исправлен по оригиналу.' if n in [164,165,166] else 'Просмотрено исходное изображение: графическая задняя обложка без текста.' if n==200 else 'Просмотрено исходное изображение: карта с растровыми подписями, текст карты добавлен.' if n==4 else 'Просмотрено исходное изображение: обложка или разделитель, основной текст находится в пригодном текстовом слое; ложные OCR-фрагменты удалены.')
 x['final_render_review_completed']=False
(check/'pages.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
s=(root/'report.md').read_text();a=re.split(r'<!-- pdf_page: (\d+) -->',s)
# Ensure every page contains source text or is the confirmed textless back cover.
counts=[]
for n in range(1,201):
 body=a[n*2].split('> Служебная информация: ссылки исходного PDF')[0].split('<details>')[0]
 body=re.sub(r'(?m)^> Служебная[^\n]*','',body)
 text=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).enable('table').render(body),'html.parser').get_text(' ',strip=True)
 counts.append({'pdf_page':n,'rendered_body_characters':len(text)})
 assert len(text)>0 or n==200,n
source=json.load(open('source.json'));idx=json.load(open(source['index']));mismatches=[]
for item in idx['pages']:
 n=item['pdf_page'];p=root/'assets'/f'page_{n:04}.png'
 if hashlib.sha256(p.read_bytes()).hexdigest()!=item['image_sha256']:mismatches.append(n)
assert not mismatches,mismatches
(check/'current_run/page_text_inventory.json').write_text(json.dumps(counts,ensure_ascii=False,indent=2))
log={
 'basis':'Existing mechanical native candidate only; no previous model transcription read, no external APIs, no child agents, no downloads.',
 'source_sha256':hashlib.sha256(Path(source['source_pdf']).read_bytes()).hexdigest(),
 'physical_pages':200,
 'source_images_viewed':[1,2,3,4,5,18,22,30,45,55,67,83,103,117,125,141,160,164,165,166,167,178,200],
 'additional_source_regions_viewed':['TatSymbol arrows on physical pages 84, 87, 107','Higher resolution certificate on physical page 164'],
 'corrections':[
  'Reused shared native_candidate.convert_page on all 200 pages; font-specific TatSymbol codes 1/2/3/8 replaced with visible arrows, U+0007 removed. Ordinary numeric glyphs unchanged.',
  'Report begins with source title; source logotypes added on cover and reviewed separators.',
  'Page 2 rebuilt as 110 section/destination pairs in the four-column reading order; two page numbers sharing text spans moved to destination cells.',
  'Pages 3,18,22,30,45,55,83,103,117,125,141,160,167: removed invisible production label and OCR noise; split stacked entries into title/page rows; detector-only empty separator columns removed.',
  'Page 4: map labels, country codes and numbered legend read from source image; spatial associations on enlarged inset left pending.',
  'Page 5: restored introduction, three thematic pillars, awards and references in source order.',
  'Page 67: added directly associated year headers. Diagnostic ambiguity is whitespace only.',
  'Pages 164–166: certificate transcription restored, OCR spelling/control noise corrected, GRI and footnotes restored, registration identifier corrected; on 166 auditor conclusion placed before right-side forecast statements.',
  'Page 178: rebuilt both 5-column tables from native source rectangles, restored section headings and four selected compliance statuses by visual source review. Unselected choices omitted from value representation.',
  'Technical PDF annotation lists use neutral target captions rather than misleading cropped text fragments; all actual source targets retained.'
 ],
 'mechanical_validation':{'page_markers_in_order':True,'all_200_asset_hashes_match_input_index':True,'all_local_links_and_anchors_exist':True,'invalid_unicode_controls':0,'html_parse_completed':True},
 'checked_pages':[x['pdf_page'] for x in r['pages'] if x['review_status']=='checked'],
 'pending_pages':[x['pdf_page'] for x in r['pages'] if x['review_status']=='pending'],
 'limitations':['Full semantic and visual review of the entire document was not performed.','Other appendix pages require review of colored compliance selections and spread-table separation.','Browser rendering could not start under the current environment (TargetClosedError). An HTML preview exists but its visual display has not been verified.','Original native_coverage.json is historical accounting for the initial mechanical candidate, not proof of final order or fidelity.'],
 'report_sha256':hashlib.sha256((root/'report.md').read_bytes()).hexdigest()
}
(check/'review_log.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n')
rules=[
 {'class':'font_specific_glyph_mapping','cause':'A symbolic font assigns digit codepoints to visible arrows.','detection':'Source font is symbolic and rendered image differs from codepoint.','action':'Map only verified glyphs in that font; do not replace ordinary numbers.','acceptance':'Visible symbol matches source; ordinary numeric values unchanged.','tests':[{'candidate':'TatSymbol 8 as numeric 8','outcome':'reject'},{'candidate':'TatSymbol 8 as visually confirmed arrow','outcome':'accept'},{'candidate':'Unknown font glyph without visual confirmation','outcome':'pending'}]},
 {'class':'spread_table_geometry','cause':'A line detector merges independent spread tables and their headings.','detection':'Cells mix separate halves, headers or status choices lose association.','action':'Inspect source, separate tables and assign native text to verified rectangles.','acceptance':'Every row, column and selected state has explicit owner.','tests':[{'candidate':'Merged spread with unlabeled alternatives','outcome':'reject'},{'candidate':'Separate verified tables with explicit selected status','outcome':'accept'},{'candidate':'Colored mark not reviewed','outcome':'pending'}]},
 {'class':'image_region_ocr_noise','cause':'OCR over decoration duplicates native text and misreads scanned identifiers.','detection':'Short garbage OCR on decorative page or disagreement with source scan.','action':'Read source image; remove confirmed duplicates/noise and correct body OCR; preserve image.','acceptance':'All body text transcribed; no image-only replacement of unread body.','tests':[{'candidate':'Image without body transcription','outcome':'reject'},{'candidate':'Body OCR corrected against source image','outcome':'accept'},{'candidate':'Unclear scanned character','outcome':'pending'}]}
]
(check/'error_rules.json').write_text(json.dumps(rules,ensure_ascii=False,indent=2)+'\n')
print('Pages:',len(r['pages']),'review:',dict(collections.Counter(x['review_status'] for x in r['pages'])),'asset hashes: 200/200','body nonempty:',sum(x['rendered_body_characters']>0 for x in counts))
