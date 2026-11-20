import sys,json,re,hashlib,collections,html
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf as fitz
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[3];out=root/'result';review=out/'_проверка/review'
s=(out/'report.md').read_text()
s=re.sub(r'<!-- pdf_page: 12 -->.*?(?=<!-- pdf_page: 13 -->)',lambda _: (review/'page12_corrected.md').read_text(),s,flags=re.S)
# Keep substantial unresolved structures visible alongside the source image.
for n in [2,*range(142,154)]:
 start=s.index(f'<!-- pdf_page: {n} -->');end=s.find('<!-- pdf_page:',start+10);end=len(s) if end<0 else end
 t=s[start:end]
 note='> Служебная пометка: порядок чтения и связи ячеек этой механически извлечённой таблицы требуют полной сверки; источник сохранён ниже. Состояния флажков перенесены по векторным отметкам PDF.\n\n' if n>=142 else '> Служебная пометка: две самостоятельные колонки содержания сохранены в общей таблице; полная сверка связей многострочных ячеек не завершена.\n\n'
 t=t.replace('<details>',note+'<details>');s=s[:start]+t+s[end:]
(out/'report.md').write_text(s)
source=json.loads((root/'source.json').read_text());doc=fitz.open(source['source_pdf'])
registry=json.loads((out/'_проверка/pages.json').read_text());original=json.loads((out/'_проверка/pages.json').read_text());(review/'baseline_pages.json').write_text(json.dumps(original,ensure_ascii=False,indent=2))
corrections=json.loads((review/'corrections.json').read_text());corrections.append({'pdf_page':12,'type':'table_reconstruction','basis':'Full source image page_0012.png: restore logo labels, independent ratings, date headers and competition row associations; ambiguous glyph is a boundary space, not a value.'});(review/'corrections.json').write_text(json.dumps(corrections,ensure_ascii=False,indent=2))
checked={1,7,8,12,121,141,172};diagnostic_pages=[p['pdf_page'] for p in registry['pages'] if p['issues']]
for entry in registry['pages']:
 n=entry['pdf_page'];p=doc[n-1]
 entry['baseline_issues']=entry['issues'];entry['conversion_status']='converted';entry['review_status']='checked' if n in checked else 'pending';entry['semantic_source_review_completed']=n in checked
 entry['verification_scope']='Full source image and text reviewed' if n in checked else ('Diagnostic glyph regions reviewed; full page semantic review pending' if n in diagnostic_pages else 'Mechanical native conversion; full source review pending')
 entry['issues']=[] if n in checked else ['Полная сверка страницы, порядка чтения и связей по оригиналу не завершена.']
 if n==139:entry['issues'].append('Пять повреждённых маркеров списка видны повреждёнными и в PDF; форма не восстановлена, пометка включена в report.md.')
 if 142<=n<=153:entry['issues'].append('Состояния 237 графических флажков по приложению добавлены по векторной геометрии; структура общей таблицы может перемежать строки левой и правой страниц разворота. Требуется полная сверка ячеек.')
 if n==2:entry['issues'].append('Две независимые колонки содержания представлены в общей таблице; многострочные ячейки требуют сверки.')
 if n in diagnostic_pages:entry['diagnostic_review']={'status':'reviewed_regions','evidence':'review/unicode_00.png … unicode_12.png; full images for covers, OCR pages and page 12','scope':'Unicode/control-character regions only, except fully checked pages'}
 entry['corrections']=[x['type'] for x in corrections if x['pdf_page']==n]
 # Printed page labels are extracted only from explicit margin text; no offset inference.
 labels=[]
 for b in p.get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   txt=''.join(sp['text'] for sp in l['spans']).strip()
   if re.fullmatch(r'\d{1,3}',txt) and l['bbox'][1]<55:labels.append({'text':txt,'bbox':list(l['bbox'])})
 entry['printed_page_labels']=labels;entry['content_type']='decorative_cover' if n in (1,172) else ('native_text_tables_graphics' if entry['tables'] else 'native_text_graphics')
 if n in (7,8,121):entry['ocr_spurious_fragments_removed']=True;entry['ocr_verified']=True
 if n==12:entry['ambiguous_cell_assignments_resolved']='Boundary whitespace; values and full table rebuilt from original image.'
registry['review_summary']={'pages':172,'converted':172,'checked_pages':sorted(checked),'pending_pages':[n for n in range(1,173) if n not in checked],'full_document_review_completed':False,'diagnostic_pages_reviewed_by_region':diagnostic_pages}
(out/'_проверка/pages.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n')
# Render the exact saved Markdown to portable local HTML for visual inspection.
render=MarkdownIt('commonmark',{'html':True}).enable('table').render(s)
page='<!doctype html><meta charset="utf-8"><title>Проверка Markdown</title><style>body{font:16px Arial;max-width:1500px;margin:24px}p{margin:5px 0}table{border-collapse:collapse;display:block;overflow:auto;max-width:100%;margin:20px 0}td,th{border:1px solid #aaa;padding:5px;min-width:60px}img{max-width:100%}details{margin-bottom:30px}sup,sub{font-size:.75em}</style>'+render
# HTML lives under review; make its image URLs resolve to actual assets.
page=page.replace('src="assets/','src="../../assets/')
(review/'rendered.html').write_text(page)
markers=[int(x) for x in re.findall(r'<!-- pdf_page: (\d+) -->',s)];assert markers==list(range(1,173))
soup=BeautifulSoup(render,'html.parser');ids={x.get('id') for x in soup.find_all(id=True)};broken=[]
for tag in soup.find_all(['a','img']):
 url=tag.get('href',tag.get('src',''))
 if url.startswith('#') and url[1:] not in ids:broken.append(url)
 elif url.startswith('assets/') and not (out/url).exists():broken.append(url)
assert not broken,broken
# Check numbers retained on every page except the independently rebuilt page 12
# and removed OCR fragments; compare author body only, excluding link captions.
def bodies(text):
 answer={}
 for m in re.finditer(r'<!-- pdf_page: (\d+) -->(.*?)(?=<!-- pdf_page:|\Z)',text,re.S):
  t=re.split(r'> Служебная пометка:|> Служебная информация:|<details>',m[2])[0];answer[int(m[1])]=BeautifulSoup(t,'html.parser').get_text()
 return answer
old=bodies((review/'baseline.md').read_text());new=bodies(s);numeric=[]
for n in range(1,173):
 if n==12:continue
 a=collections.Counter(re.findall(r'\d+',old[n]));b=collections.Counter(re.findall(r'\d+',new[n]));
 if a!=b:numeric.append({'page':n,'removed':dict(a-b),'added':dict(b-a)})
validation={'physical_page_markers':len(markers),'page_markers_unique_ordered':True,'assets_referenced':len(soup.find_all('img')),'broken_local_links':broken,'report_sha256':hashlib.sha256((out/'report.md').read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(Path(source['source_pdf']).read_bytes()).hexdigest(),'numeric_inventory_differences_excluding_rebuilt_page12':numeric,'rendered_to_html':True,'visual_render_review':'pending','coverage_note':'native_coverage.json describes baseline, not corrected report; its hash is retained as provenance, not final validation.'}
(review/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2));print(json.dumps(validation,ensure_ascii=False))
