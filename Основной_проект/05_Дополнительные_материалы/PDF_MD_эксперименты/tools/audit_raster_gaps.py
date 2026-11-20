"""Isolated source audit and unchecked local OCR supplements; never changes native MD."""
from __future__ import annotations
import argparse, concurrent.futures, csv, datetime, hashlib, json, multiprocessing, os
from pathlib import Path
import time, traceback
BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'_проверка/raster_gap_supplements'
SOURCE_MANIFEST=BASE/'_проверка/sources_manifest.json'
IMPLEMENTATION_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
FROZEN_NATIVE_SHA='e84e269a6ef3840e4ba2b48efa9cb7fb5c56c4046b7fc4e476eb5d47edb351e4'
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.'+str(os.getpid())+'.tmp');t.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');t.replace(p)
def read(p):return json.loads(Path(p).read_text())
def union_area(rects):
 if not rects:return 0.
 xs=sorted(set(x for r in rects for x in(r[0],r[2])));total=0.
 for x0,x1 in zip(xs,xs[1:]):
  intervals=sorted((r[1],r[3])for r in rects if r[0]<x1 and r[2]>x0)
  ysum=0.;end=None
  for y0,y1 in intervals:
   if end is None or y0>end:ysum+=y1-y0;end=y1
   elif y1>end:ysum+=y1-end;end=y1
  total+=(x1-x0)*ysum
 return total

def candidate_bind(rid,source_sha):
 root=BASE/'_проверка/native_candidates'/rid;coverage=root/'_проверка/native_coverage.json';receipt=root/'_проверка/source_input.json'
 if not(root/'report.md').is_file()or not coverage.exists()or not receipt.exists():return None
 c=read(coverage);s=read(receipt)
 if c.get('source_sha256')!=source_sha or s.get('source_sha256')!=source_sha:raise ValueError('Native candidate source SHA mismatch')
 if s.get('implementation_sha256')!=FROZEN_NATIVE_SHA:raise ValueError('Native helper version differs from frozen expected SHA')
 return {'candidate_report_sha256':sha(root/'report.md'),'candidate_implementation_sha256':s['implementation_sha256']}

def detect_report(source):
 import native_candidate as native
 fitz=native.fitz;rid=source['report_id'];path=BASE/'_источники'/(rid+'.pdf')
 if sha(path)!=source['sha256']:raise ValueError('Source PDF SHA differs from manifest')
 root=OUT/rid;p=root/'pages.json';previous=read(p)if p.exists()else None
 if previous and previous.get('source_pdf_sha256')==source['sha256']and previous.get('audit_implementation_sha256')==IMPLEMENTATION_SHA:return previous
 native_records={};np=BASE/'_проверка/native_candidates'/rid/'_проверка/pages.json'
 if np.exists():
  try:
   z=read(np);native_records={r['pdf_page']:r for r in(z if isinstance(z,list)else z['pages'])}
  except (ValueError,KeyError):pass
 records=[];scanned=0
 with fitz.open(path)as doc:
  for page_no,page in enumerate(doc,1):
   scanned+=1;bounds=page.rect*page.derotation_matrix;area=bounds.get_area();images=[]
   for im in page.get_image_info():
    rect=fitz.Rect(im['bbox'])&bounds
    if rect.is_empty or rect.get_area()<area*.05 or im['width']<200 or im['height']<100:continue
    images.append((im,rect))
   if not images:continue
   flags=fitz.TEXTFLAGS_RAWDICT&~fitz.TEXT_PRESERVE_IMAGES
   glyphs=[((c['bbox'][0]+c['bbox'][2])/2,(c['bbox'][1]+c['bbox'][3])/2)for b in page.get_text('rawdict',flags=flags)['blocks']for l in b.get('lines',[])for s in l['spans']for c in s.get('chars',[])if c['c'].strip()]
   low=[]
   for im,rect in images:
    n=sum(rect.x0<=x<=rect.x1 and rect.y0<=y<=rect.y1 for x,y in glyphs)
    if n<30:low.append({'bbox':list(rect),'visible_area_ratio':rect.get_area()/area,'native_glyph_centers':n,'pixels':[im['width'],im['height']]})
   combined=union_area([r['bbox']for r in low])/area
   if not low or not(any(r['visible_area_ratio']>=.15 for r in low)or combined>=.2):continue
   old=native_records.get(page_no,{})
   already=bool(old.get('ocr_chars',0)>0 and not old.get('ocr_error'))
   records.append({'pdf_page':page_no,'rotation':page.rotation,'page_native_nonspace_glyphs':len(glyphs),'regions':low,'combined_low_native_area_ratio':combined,'existing_native_ocr_chars':old.get('ocr_chars',0),'ocr_state':'already_ocr_present'if already else'detected','ocr_verified':False,'review_status':'pending'})
 result={'report_id':rid,'source_pdf_sha256':source['sha256'],'source_pdf_path':str(path.relative_to(BASE)),'candidate_report_sha256':None,'candidate_implementation_sha256':None,'audit_implementation_sha256':IMPLEMENTATION_SHA,'pdf_pages':scanned,'detected_at':utc(),'rules':{'minimum_visible_area_ratio':.05,'minimum_pixels':[200,100],'low_native_glyph_centers_exclusive_upper':30,'single_image_trigger_area':.15,'union_trigger_area':.2},'pages':records,'state':'detection_complete','scope':'Raster regions with little native text; photographs can be false positives, OCR is not source-verified.'}
 bound=candidate_bind(rid,source['sha256'])
 if bound:result.update(bound)
 put(p,result);return result

def choose_image(rid,n,page,root,source_sha):
 prepared=BASE/'_проверка/входы'/rid;index=prepared/'pages.json'
 if index.exists():
  z=read(index)
  for item in z.get('pages',[])if z.get('source_sha256')==source_sha else []:
   if item['pdf_page']==n:
    f=BASE/item['image']
    if f.is_file()and sha(f)==item['image_sha256']:return f
 native=BASE/'_проверка/native_candidates'/rid;f=native/'assets'/f'page_{n:04d}.png';receipt=native/'_проверка/native_assets.json'
 if f.exists()and receipt.exists()and read(receipt).get(f.name)==sha(f):return f
 f=root/'images'/f'page_{n:04d}.png';f.parent.mkdir(exist_ok=True)
 scale=min(3.,3200/max(page.rect.width,page.rect.height));page.get_pixmap(matrix=__import__('pymupdf').Matrix(scale,scale),alpha=False).save(f)
 return f

def ocr_report(rid):
 os.environ['OMP_THREAD_LIMIT']='1'
 import native_candidate as native
 if native.IMPLEMENTATION_SHA!=FROZEN_NATIVE_SHA:raise ValueError('Frozen native helper changed; refusing OCR dependency drift')
 root=OUT/rid;p=root/'pages.json';data=read(p);source=BASE/data['source_pdf_path']
 if sha(source)!=data['source_pdf_sha256']:raise ValueError('Source changed before OCR')
 binding=candidate_bind(rid,data['source_pdf_sha256'])
 if not binding:data.update(state='awaiting_native_candidate',updated_at=utc());put(p,data);return data
 data.update(binding)
 current_registry=BASE/'_проверка/native_candidates'/rid/'_проверка/pages.json'
 fresh=read(current_registry)if current_registry.exists()else{}
 fresh_records={r['pdf_page']:r for r in(fresh if isinstance(fresh,list)else fresh.get('pages',[]))}
 with native.fitz.open(source)as doc:
  for item in data['pages']:
   old=fresh_records.get(item['pdf_page'],{})
   if old.get('ocr_chars',0)>0 and not old.get('ocr_error')and item['ocr_state']in('detected','already_ocr_present'):
    item.update(ocr_state='already_ocr_present',existing_native_ocr_chars=old['ocr_chars'])
   if item['ocr_state']=='already_ocr_present':continue
   text_path=root/f'page_{item["pdf_page"]:04d}.txt'
   if item['ocr_state']=='supplement_ready'and text_path.exists()and sha(text_path)==item.get('supplement_sha256'):
    if sha(BASE/item['image_path'])==item.get('image_sha256'):continue
   page=doc[item['pdf_page']-1];image=choose_image(rid,item['pdf_page'],page,root,data['source_pdf_sha256'])
   text,info=native.raster_text(page,image)
   text_path.write_text(text)
   item.update(image_path=str(image.relative_to(BASE)),image_sha256=sha(image),supplement_path=str(text_path.relative_to(BASE)),supplement_sha256=sha(text_path),ocr_info=info,ocr_state='ocr_error'if info.get('ocr_error')else'supplement_ready'if text.strip()else'no_ocr_text',ocr_verified=False,review_status='pending',processed_at=utc())
   put(p,data)
 data.update(state='ocr_complete',updated_at=utc());put(p,data);return data

def index_snapshot(reports,phase,errors=None):
 records=[]
 for rid in reports:
  p=OUT/rid/'pages.json'
  if not p.exists():continue
  d=read(p);records.append({'report_id':rid,'state':d['state'],'pdf_pages':d['pdf_pages'],'candidate_pages':len(d['pages']),'already_ocr_pages':sum(x['ocr_state']=='already_ocr_present'for x in d['pages']),'supplement_pages':sum(x['ocr_state']=='supplement_ready'for x in d['pages']),'supplement_chars':sum(x.get('ocr_info',{}).get('ocr_chars',0)for x in d['pages']),'pending_ocr_pages':sum(x['ocr_state']in('detected','ocr_error')for x in d['pages'])})
 v={'pid':os.getpid(),'updated_at':utc(),'phase':phase,'requested_reports':len(reports),'reports_scanned':len(records),'physical_pages_scanned':sum(r['pdf_pages']for r in records),'candidate_pages':sum(r['candidate_pages']for r in records),'already_ocr_pages':sum(r['already_ocr_pages']for r in records),'supplement_pages':sum(r['supplement_pages']for r in records),'supplement_chars':sum(r['supplement_chars']for r in records),'audit_implementation_sha256':IMPLEMENTATION_SHA,'native_helper_expected_sha256':FROZEN_NATIVE_SHA,'reports':records,'errors':errors or[],'source_review_completed':False,'corpus_mutated':False}
 put(OUT/'index.json',v);return v

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['detect','ocr','both'],default='both');ap.add_argument('--reports',nargs='*');ap.add_argument('--workers',type=int,default=4);args=ap.parse_args()
 rows=read(SOURCE_MANIFEST)['reports'];rows=[r for r in rows if not args.reports or r['report_id']in args.reports];reports=[r['report_id']for r in rows];errors=[]
 OUT.mkdir(parents=True,exist_ok=True);context=multiprocessing.get_context('spawn');started=time.time()
 if args.stage in('detect','both'):
  with concurrent.futures.ProcessPoolExecutor(max_workers=min(4,args.workers),mp_context=context)as pool:
   jobs={pool.submit(detect_report,r):r['report_id']for r in rows}
   for f in concurrent.futures.as_completed(jobs):
    rid=jobs[f]
    try:d=f.result();print('DETECT',rid,len(d['pages']),flush=True)
    except Exception as e:errors.append({'report_id':rid,'phase':'detect','error':str(e),'traceback':traceback.format_exc()});print('ERROR',rid,str(e),flush=True)
    index_snapshot(reports,'detecting',errors)
  v=index_snapshot(reports,'detection_complete',errors);print('DETECTION SUMMARY',json.dumps({k:v[k]for k in['reports_scanned','physical_pages_scanned','candidate_pages','already_ocr_pages']},ensure_ascii=False),flush=True)
 if args.stage in('ocr','both'):
  waiting=[rid for rid in reports if(OUT/rid/'pages.json').exists()]
  while waiting:
   round_wait=[]
   with concurrent.futures.ProcessPoolExecutor(max_workers=min(4,args.workers),mp_context=context)as pool:
    jobs={pool.submit(ocr_report,rid):rid for rid in waiting}
    for f in concurrent.futures.as_completed(jobs):
     rid=jobs[f]
     try:
      d=f.result();print('OCR',rid,d['state'],sum(x['ocr_state']=='supplement_ready'for x in d['pages']),flush=True)
      if d['state']=='awaiting_native_candidate':round_wait.append(rid)
     except Exception as e:errors.append({'report_id':rid,'phase':'ocr','error':str(e),'traceback':traceback.format_exc()});print('ERROR',rid,str(e),flush=True)
     index_snapshot(reports,'ocr_running',errors)
   if not round_wait:break
   if time.time()-started>7200:errors.append({'phase':'ocr','error':'Native candidates not ready within two hours','reports':round_wait});break
   time.sleep(15);waiting=round_wait
 index_snapshot(reports,'finished_with_errors'if errors else'finished',errors)
if __name__=='__main__':main()
