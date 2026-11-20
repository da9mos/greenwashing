"""Prepare source-grounded numerical review dossier; raw/model artifacts untouched."""
from pathlib import Path
import sys,json,hashlib,collections,re,os
for lib in ['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']:sys.path.insert(0,lib)
import pymupdf as fitz
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'_проверка/Аудит_DeepSeek_2026-11-16/Числовая_сверка_Codex'
sys.path.insert(0,str(BASE/'tools'))
from compare_results import decimal_span_reference,decimal_key,DECIMAL,compare_decimals_to_spans,numeric_text

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def local(p):
 s=p.stat()
 if s.st_size and (not s.st_blocks or getattr(s,'st_flags',0)&0x40000000):raise ValueError('Cloud-only file not read: '+str(p))
def main():
 OUT.mkdir(exist_ok=True);audit_path=BASE/'_проверка/Аудит_DeepSeek_2026-11-16/audit_before_footnote_fix.json';audit_path=audit_path if audit_path.is_file() else BASE/'_проверка/Аудит_DeepSeek_2026-11-16/audit.json';audit=json.loads(audit_path.read_text());items=[x for x in audit['pages'] if any(f['kind']=='decimal_span_suspect' for f in x['flags'])]
 items.append({'report_id':'GAZP-2023-ОУР','pdf_page':57,'control':True})
 docs={};records=[];font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',17)
 for item in items:
  rid=item['report_id'];n=item['pdf_page'];source=BASE/'_источники'/(rid+'.pdf');local(source)
  if rid not in docs:docs[rid]=fitz.open(source)
  page=docs[rid][n-1];folder=OUT/rid/f'page_{n:04d}';folder.mkdir(parents=True,exist_ok=True)
  pix=page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False);image_path=folder/'source.png';pix.save(image_path)
  raw_path=BASE/'_проверка/DeepSeek'/rid/'v3'/f'page_{n:04d}.json';raw=json.loads(raw_path.read_text());md=raw['response']['markdown'];reference=decimal_span_reference(page.get_text('dict'));cmp=compare_decimals_to_spans(md,reference)
  evidence=reference['evidence']+reference['excluded_superscript_decimal_spans'];keys=set(cmp['pdf_only'])|set(cmp['markdown_only']);selected=[e for e in evidence if e['token'] in keys];rectangles=[]
  for e in selected:
   r=fitz.Rect(e['bbox']);r=fitz.Rect(max(0,r.x0-35),max(0,r.y0-22),min(page.rect.width,r.x1+35),min(page.rect.height,r.y1+22));
   if not any(r.intersects(q) and (r|q).get_area()<r.get_area()+q.get_area()+2000 for q in rectangles):rectangles.append(r)
  if item.get('control'):
   for term in ['1,963','0,173','76,6']:
    for r in page.search_for(term):rectangles.append(fitz.Rect(max(0,r.x0-50),max(0,r.y0-35),min(page.rect.width,r.x1+50),min(page.rect.height,r.y1+35)))
  crops=[]
  for i,r in enumerate(rectangles):
   p=folder/f'crop_{i:02d}.png';page.get_pixmap(matrix=fitz.Matrix(3,3),clip=r,alpha=False).save(p);crops.append({'path':str(p.relative_to(OUT)),'sha256':sha(p),'bbox':list(r)})
  norm=decimal_key(page.get_text());source_text=page.get_text();extra_context=[]
  for token in cmp['markdown_only']:
   matching=[e for e in evidence if e['token']==token]
   extra_context.append({'token':token,'source_matching_spans':matching,'source_search_rects':[list(r) for r in page.search_for(token.replace('.',','))]})
  records.append({'report_id':rid,'pdf_page':n,'control':bool(item.get('control')),'source_pdf':str(source),'source_pdf_sha256':sha(source),'raw_answer_path':str(raw_path),'raw_answer_sha256':sha(raw_path),'source_image':{'path':str(image_path.relative_to(OUT)),'sha256':sha(image_path)},'crops':crops,'comparison':cmp,'source_matching_extras':extra_context,'source_text':source_text,'markdown':md,'reference':reference,'model_issues':raw['response'].get('issues',[])})
 for start in range(0,len(records),4):
  subset=records[start:start+4];panels=[]
  for r in subset:
   im=Image.open(OUT/r['source_image']['path']).convert('RGB');im.thumbnail((900,950));panel=Image.new('RGB',(920,1080),'white');dr=ImageDraw.Draw(panel);dr.text((10,5),r['report_id']+' PDF '+str(r['pdf_page']),font=font,fill='black');
   dr.text((10,30),'PDF '+str(r['comparison']['pdf_only'])[:100],font=font,fill='black');dr.text((10,55),'MD '+str(r['comparison']['markdown_only'])[:100],font=font,fill='black');panel.paste(im,(10,95));panels.append(panel)
  sheet=Image.new('RGB',(1840,2160),'#dddddd')
  for j,p in enumerate(panels):sheet.paste(p,((j%2)*920,(j//2)*1080))
  sheet.save(OUT/f'overview_{start//4:02d}.jpg',quality=90)
 (OUT/'dossier.json').write_text(json.dumps({'scope':'75 suspect pages plus control57; source evidence prepared, not a checked claim','pages':records},ensure_ascii=False,indent=2)+'\n')
 print('Prepared',len(records),'pages;',sum(len(r['crops']) for r in records),'source crops;',len(range(0,len(records),4)),'overview sheets')
 for d in docs.values():d.close()
if __name__=='__main__':main()

# This dossier generator intentionally never assigns a review verdict.
# Human/Codex decisions are saved separately with their exact evidence scope.
