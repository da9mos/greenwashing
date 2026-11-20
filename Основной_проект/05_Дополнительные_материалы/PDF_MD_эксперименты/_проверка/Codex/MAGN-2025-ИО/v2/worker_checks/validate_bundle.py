import sys,json,re,hashlib,collections,unicodedata,urllib.parse
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
import fitz
root=Path('result');check=root/'_проверка';text=(root/'report.md').read_text();pages=json.loads((check/'pages.json').read_text())['pages'];source=json.loads(Path('source.json').read_text());doc=fitz.open(check/'font_working.pdf')
markers=[int(x) for x in re.findall(r'<!-- pdf_page: (\d+) -->',text)];assert markers==list(range(1,379))
soup=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).enable('table').render(text),'html.parser');ids=[x['id'] for x in soup.select('[id]')];missing=[];broken=[]
for tag in soup.select('[href], [src]'):
 target=tag.get('href') or tag.get('src')
 if target.startswith('#'):
  if target[1:] not in ids:broken.append(target)
 elif not urllib.parse.urlparse(target).scheme:
  if not (root/urllib.parse.unquote(target)).is_file():missing.append(target)
assert not missing and not broken,(missing,broken)
assetmap=json.loads((check/'native_assets.json').read_text());mismatches=[]
for name,h in assetmap.items():
 if hashlib.sha256((root/'assets'/name).read_bytes()).hexdigest()!=h:mismatches.append(name)
assert not mismatches
for record,page in zip(pages,doc):
 n=record['pdf_page'];record['content_type']='mixed_scanned_body' if n in [278,279,280,281] else 'native_text_and_graphics'
 labels=[]
 for b in page.get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   for s in l['spans']:
    if s['bbox'][0]>.75*page.rect.width and s['bbox'][1]>.95*page.rect.height and s['size']<15 and s['text'].strip():labels.append(s['text'].strip())
 record['printed_page_label_extracted']=' '.join(labels) or None;record['printed_page_label_review_status']='pending' if n!=1 else 'checked';record['source_image']=f'assets/page_{n:04d}.png'
 record['unicode_diagnostic_status']='resolved' if not record['unresolved_unicode'] else 'pending'
 record['cell_ownership_diagnostic_status']='resolved' if not record['ambiguous_cell_assignments'] else 'pending'
 record['render_review_status']='pending';record['render_issue']='Chrome launch denied by execution environment; no screenshots available.'
(check/'pages.json').write_text(json.dumps({'pages':pages},ensure_ascii=False,indent=2))
report_hash=hashlib.sha256((root/'report.md').read_bytes()).hexdigest();source_hash=hashlib.file_digest(Path(source['source_pdf']).open('rb'),'sha256').hexdigest()
validation={'source_sha256':source_hash,'report_sha256':report_hash,'physical_pages':378,'page_markers_exactly_once_in_order':True,'registry_count':len(pages),'all_local_links_exist':True,'internal_targets_exist':True,'verified_source_image_hashes':len(assetmap),'replacement_characters':text.count('�'),'non_whitespace_controls':[(hex(ord(c)),n) for c,n in collections.Counter(text).items() if unicodedata.category(c)=='Cc' and not c.isspace()],'tables':len(soup.select('table')),'empty_table_rows':len([r for r in soup.select('table tr') if not r.select('td,th')]),'conversion_status_counts':dict(collections.Counter(p['conversion_status'] for p in pages)),'review_status_counts':dict(collections.Counter(p['review_status'] for p in pages)),'full_original_review':False,'render_verified':False}
(check/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2))
# Preserve the initial accounting report; it is evidence for the baseline, not for final visual acceptance.
coverage=check/'native_coverage.json';baseline=check/'previous_reports/native_coverage.json'
if not baseline.exists():baseline.write_bytes(coverage.read_bytes())
original=json.loads(baseline.read_text());coverage.write_text(json.dumps({'source_sha256':source_hash,'report_sha256':report_hash,'pages':378,'all_native_glyphs_assigned_once':all(r['all_native_glyphs_assigned_once'] for r in pages),'native_glyphs':sum(r['native_glyphs'] for r in pages),'original_coverage_report':'previous_reports/native_coverage.json','scope':'Native glyph assignment using the supplied shared converter, repaired Unicode maps and supplemented table geometry; cover logo and scanned body text added visually/OCR. Does not establish reading order, cell semantics or full source fidelity.','conversion_status':'converted','review_status':'pending','semantic_source_review_completed':False,'fully_checked_pages':[1],'pending_pages':list(range(2,379)),'render_verified':False},ensure_ascii=False,indent=2))
print(json.dumps(validation,ensure_ascii=False,indent=2))
