from pathlib import Path
import sys,json,re,hashlib,shutil,collections,subprocess
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
import pymupdf as f
base=Path(__file__).resolve().parents[1];check=base/'_проверка';s=(base/'report.md').read_text()
s=re.sub(r'\n\n> Служебная пометка о проверке: [^\n]*','',s)
source=json.load(open(base.parent/'source.json'));doc=f.open(source['source_pdf']);sha=hashlib.sha256(Path(source['source_pdf']).read_bytes()).hexdigest()
old=json.load(open(check/'initial/pages.json'));ref=json.load(open(check/'refined_geometry.json'))
flagged=[p['pdf_page'] for p in old['pages'] if p['issues']]
viewed=sorted(set(flagged+[14,30,32,33,34,43,44,53,73,76,89,92,93,112,122,123,124,125,126]))
tables=[p['pdf_page'] for p in old['pages'] if p['tables']]+[31,71]
notes={}
for n in range(1,134):
 if n==1:continue
 if n==46:t='Текст тела и видимых карточек перенесён; две мелкие подписи требуют сверки. Перекрытые части отсутствуют в видимой области самого PDF.'
 elif n in tables:t='Текст и числа перенесены. Полная поячейковая сверка таблиц, их объединений и связей не завершена; статус проверки pending. Исходная страница доступна ниже.'
 elif n in viewed:t='Исходное изображение просмотрено при диагностике; полная построчная сверка страницы не завершена (pending).'
 else:t='Текст перенесён механически; сверка порядка блоков, чисел и связей по оригиналу ещё не выполнена (pending).'
 notes[n]=t
 s=s.replace(f'<a id="pdf-page-{n}"></a>',f'<a id="pdf-page-{n}"></a>\n\n> Служебная пометка о проверке: {t}',1)
# Tables remain readable by horizontal scrolling in HTML-capable Markdown viewers.
s=re.sub(r'<table>(.*?)</table>',r'<div style="max-width:100%; overflow-x:auto;">\n<table style="min-width:720px; border-collapse:collapse;">\1</table>\n</div>',s,flags=re.S)
(base/'report.md').write_text(s)
records=[]
for p in old['pages']:
 n=p['pdf_page'];pg=doc[n-1];row=dict(p)
 row['original_diagnostics']=p['issues'];row['issues']=[]
 row['conversion_status']='converted';row['review_status']='checked' if n==1 else 'pending';row['semantic_source_review_completed']=n==1
 row['source_image_viewed']=n in viewed
 row['verification_scope']='Cover title visually matched to source image' if n==1 else ('Diagnostic image inspection; not full-page textual verification' if n in viewed else 'Mechanical glyph conversion; source-image review pending')
 row['printed_page_designation']=None
 footer=pg.get_text(clip=f.Rect(pg.rect.width*.90,pg.rect.height*.94,pg.rect.width,pg.rect.height)).strip()
 if re.fullmatch(r'\d+',footer):row['printed_page_designation']=footer
 row['content_type']='mixed_native_text_and_images' if pg.get_images() else 'native_text_and_vector'
 row['table_review_completed']=False
 if str(n) in ref:row['geometry_refinement']=ref[str(n)];row['geometry_refinement_review']='partial; all native glyphs retained; full cell-by-cell semantic review pending'
 if n!=1:row['issues'].append(notes[n])
 if n==133:row['issues'].append('PDF destination of two email annotations is unresolved. Visible addresses retained; no destination invented.')
 if n==46:row['conversion_status']='pending';row['issues'].append('Fine-print attributions beneath card quotations remain partially unread; body text transcribed visually.')
 row['ocr_supplement_disposition']='Duplicate/artifact OCR appendix removed after diagnostic inspection; original preserved in initial/report.md' if p.get('ocr_chars') else 'not applicable'
 if n in [6,39,46,86,17]:row['raster_text_action']='Visible raster text / pictogram relationships transcribed from source image; see report and review log.'
 records.append(row)
(check/'pages.json').write_text(json.dumps({'source_sha256':sha,'pages':records},ensure_ascii=False,indent=2)+'\n')
# Structural and asset validation, independent of semantic review.
markers=[int(v) for v in re.findall(r'<!-- pdf_page: (\d+) -->',s)];assert markers==list(range(1,134))
soup=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).enable('table').render(s),'html.parser')
ids={el.get('id') for el in soup.find_all(id=True)}
missing=[]
for im in soup.find_all('img'):
 if not (base/im['src']).is_file():missing.append(im['src'])
broken=[a['href'] for a in soup.find_all('a',href=True) if a['href'].startswith('#') and a['href'][1:] not in ids]
assert not missing and not broken
index=json.load(open(source['index']));asset_mismatches=[]
for p in index['pages']:
 if hashlib.sha256((base/f"assets/page_{p['pdf_page']:04}.png").read_bytes()).hexdigest()!=p['image_sha256']:asset_mismatches.append(p['pdf_page'])
assert not asset_mismatches
validation={'source_sha256':sha,'source_pages':len(doc),'physical_page_markers':len(markers),'markers_in_order':True,'missing_assets':missing,'broken_internal_links':broken,'source_image_hash_mismatches':asset_mismatches,'report_sha256':hashlib.sha256(s.encode()).hexdigest(),'source_images_viewed':viewed,'source_images_viewed_count':len(viewed),'whole_pages_checked':[1],'full_source_review_completed':False,'conversion_pending_pages':[46],'table_count':len(soup.find_all('table')),'scope':'Structure and asset integrity; not semantic accuracy'}
(check/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
# Retain reusable baseline implementation locally, so the refinement script does not depend on a temporary helper.
shutil.copy2('/private/tmp/native_candidate_read.py',check/'native_candidate_baseline.py')
p=check/'refine.py';r=p.read_text().replace("'/private/tmp/native_candidate_read.py'","str(BASE/'_проверка/native_candidate_baseline.py')");p.write_text(r)
print(json.dumps(validation,ensure_ascii=False))
