"""Recover registered reports only. Never invoke model APIs or old downloader outputs."""
import argparse, concurrent.futures, csv, datetime, hashlib, io, json, re, threading, time, urllib.error, urllib.request, zipfile
from pathlib import Path
import fitz
BASE=Path(__file__).resolve().parents[1]
VAULT=BASE.parents[2]
OLD=VAULT/'11_Проект_Сбер/3_итерация/greenwashing'
REG=OLD/'01_итерация_1_сбор_данных/выборка_30/reports.csv'
LOG=OLD/'03_итерация_3_пайплайн/data/reports/download_log.csv'
OUT=BASE/'_источники'; QA=BASE/'_проверка'
LOCK=threading.Lock()
def readcsv(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f,delimiter=';'))
def fetch(url):
 request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; report-source-recovery/1.0)'})
 for attempt in range(2):
  try:
   with urllib.request.urlopen(request,timeout=90) as r:return r.read(),r.geturl(),r.headers.get('Content-Type','')
  except urllib.error.HTTPError as e:
   if e.code in [401,403,404,410,429] or attempt:raise
  except Exception:
   if attempt:raise
  time.sleep(1)
def pdf_info(data,row,old):
 if not data[:1024].lstrip().startswith(b'%PDF'):raise ValueError('Not PDF; no CAPTCHA bypass attempted')
 with fitz.open(stream=data,filetype='pdf') as doc:
  if doc.needs_pass:raise ValueError('PDF encrypted')
  if not len(doc):raise ValueError('PDF has no pages')
  text='\n'.join(doc[i].get_text()for i in range(min(8,len(doc))))
  first='\n'.join(doc[i].get_text()for i in range(min(3,len(doc))))
  result={'pages':len(doc),'pdf_valid':True,'title_excerpt':first[:4500],'title_metadata':doc.metadata.get('title',''),'expected_year_in_first8':row['year']in text,'registered_type':row['report_type'],'title_type_signals':[t for t in ['устойчив','социальн','экологич','годов','интегрирован']if t in first.lower()]}
 sha=hashlib.sha256(data).hexdigest();expected=old.get('sha256','')if old.get('status')=='ok'else''
 result.update(bytes=len(data),sha256=sha,expected_sha256=expected,sha_matches_previous=(sha==expected)if expected else None)
 if expected and sha!=expected:raise ValueError('SHA mismatch against historical successful download: '+sha)
 return result
def save_json(p,v):
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
def write_manifest(results,rows):
 ordered=[results.get(r['report_id'],dict(report_id=r['report_id'],state='pending'))for r in rows]
 counts={s:sum(x['state']==s for x in ordered)for s in sorted(set(x['state']for x in ordered))}
 v={'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'registered_reports':len(rows),'companies':len(set(r['company_id']for r in rows)),'counts':counts,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat()if counts.get('pending',0)==0 else None,'registry_path':str(REG),'registry_sha256':hashlib.sha256(REG.read_bytes()).hexdigest(),'previous_log_path':str(LOG),'reports':ordered,'limitations':['Title/year/type checks are text signals, not visual review of every cover.','Historical successful SHA unavailable for rows where prior acquisition failed.','No model API requests; no CAPTCHA bypass.']}
 save_json(QA/'sources_manifest.json',v)
 fields=['report_id','state','path','pages','bytes','sha256','sha_matches_previous','expected_year_in_first8','registered_type','source_url','note']
 with (QA/'sources.csv').open('w',encoding='utf-8-sig',newline='')as f:
  w=csv.DictWriter(f,fieldnames=fields,delimiter=';',extrasaction='ignore');w.writeheader();w.writerows(ordered)
def recover(row,old,prior=None):
 rid=row['report_id'];p=OUT/(rid+'.pdf');rec=dict(row);rec.update(state='failed',path=str(p),attempts=[])
 try:
  if p.exists():
   rec.update(prior or {})
   info=pdf_info(p.read_bytes(),row,old);rec.update(info,state='ready',source_url=(prior or {}).get('source_url')or old.get('source_url',''),note='Existing local target verified; source provenance retained');return rec
  did=row['drive_id'];st=row['status'];candidates=[]
  if st=='pdf':candidates=[f'https://drive.usercontent.google.com/download?id={did}&export=download&confirm=t']
  elif st.startswith('ссылка'):
   try:
    text,_,_=fetch(f'https://docs.google.com/document/d/{did}/export?format=txt')
    rec['pointer_excerpt']=text.decode('utf-8-sig','replace')[:5000]
    candidates=[u.rstrip('.,;')for u in re.findall(r'https?://[^\s<>"\')\]]+',rec['pointer_excerpt'])if '.pdf' in u.lower()]
   except Exception as e:rec['attempts'].append({'url':f'https://docs.google.com/document/d/{did}/export?format=txt','error':str(e)[:400]})
   fallback_file=QA/'sources_fallbacks.json'
   fallback=json.loads(fallback_file.read_text()).get(rid,[])if fallback_file.exists()else[]
   rec['approved_official_fallbacks']=fallback
   candidates.extend(x['url']for x in fallback)
   if not candidates:raise ValueError('Registered pointer inaccessible or has no PDF; no confirmed official fallback')
  elif st.startswith('архив'):
   url=f'https://drive.usercontent.google.com/download?id={did}&export=download&confirm=t';data,_,_=fetch(url)
   with zipfile.ZipFile(io.BytesIO(data))as z:
    members=[]
    for name in z.namelist():
     if name.lower().endswith('.pdf'):
      b=z.read(name);sha=hashlib.sha256(b).hexdigest();members.append({'name':name,'bytes':len(b),'sha256':sha})
      if sha==old.get('sha256'):
       info=pdf_info(b,row,old);p.write_bytes(b);rec.update(info,state='ready',source_url=url,note='Archive PDF selected by historical SHA, not largest filename',archive_member=name,archive_members=members);return rec
   rec['archive_members']=members;raise ValueError('No archive PDF matches historical successful SHA')
  else:raise ValueError('Unknown registry status')
  for url in candidates:
   try:
    data,final,ctype=fetch(url)
    if data[:4]==b'PK\x03\x04':
     found=[];members=[]
     with zipfile.ZipFile(io.BytesIO(data))as archive:
      for member in archive.infolist():
       if member.is_dir()or not member.filename.lower().endswith('.pdf'):continue
       if member.file_size>300_000_000:raise ValueError('Archive PDF exceeds bounded extraction size')
       candidate=archive.read(member);sha=hashlib.sha256(candidate).hexdigest();members.append({'name':member.filename,'sha256':sha,'bytes':len(candidate)})
       if old.get('sha256'):
        if sha==old['sha256']:found.append((candidate,member.filename))
       else:
        with fitz.open(stream=candidate,filetype='pdf')as doc:
         title=' '.join(doc[i].get_text()for i in range(min(8,len(doc)))).lower()
        if row['year']in title and 'мосводоканал'in title:found.append((candidate,member.filename))
     if len(found)!=1:raise ValueError('Official archive must contain exactly one source-identified PDF: '+str(members))
     data,member_name=found[0];rec.update(archive_members=members,archive_member=member_name)
    info=pdf_info(data,row,old)
    if not old.get('sha256'):
     with fitz.open(stream=data,filetype='pdf')as doc:title=' '.join(doc[i].get_text()for i in range(min(8,len(doc)))).lower()
     if row['year']not in title or ('MVDK'in rid and 'мосводоканал'not in title):raise ValueError('New source without historical SHA lacks company/year title evidence')
    tmp=p.with_suffix('.pdf.part');tmp.write_bytes(data);tmp.replace(p)
    rec.update(info,state='ready',source_url=url,note='Registered source recovered',content_type=ctype);return rec
   except Exception as e:rec['attempts'].append({'url':url,'error':str(e)[:400]})
  raise ValueError('Registered source attempts failed')
 except Exception as e:rec['note']=str(e)[:600];return rec

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=5);ap.add_argument('--only',nargs='*');args=ap.parse_args()
 OUT.mkdir(parents=True,exist_ok=True);QA.mkdir(parents=True,exist_ok=True);rows=readcsv(REG);old={r['report_id']:r for r in readcsv(LOG)}
 assert len(rows)==92 and len(set(r['report_id']for r in rows))==92
 results={}
 if (QA/'sources_manifest.json').exists():results={r['report_id']:r for r in json.loads((QA/'sources_manifest.json').read_text())['reports']}
 tasks=[r for r in rows if not args.only or r['report_id']in args.only]
 prior_results=dict(results)
 for r in tasks:results[r['report_id']]=dict(results.get(r['report_id'],{}),report_id=r['report_id'],state='pending')
 write_manifest(results,rows)
 with concurrent.futures.ThreadPoolExecutor(max_workers=min(max(args.workers,1),6))as pool:
  fs={pool.submit(recover,r,old.get(r['report_id'],{}),prior_results.get(r['report_id'])):r for r in tasks}
  for f in concurrent.futures.as_completed(fs):
   result=f.result();results[result['report_id']]=result;write_manifest(results,rows);print(result['report_id'],result['state'],result.get('pages',''),result.get('note',''),flush=True)
 print(json.dumps({'counts':json.loads((QA/'sources_manifest.json').read_text())['counts'],'manifest':str(QA/'sources_manifest.json')},ensure_ascii=False))
if __name__=='__main__':main()
