"""Resume independent Codex corpus jobs; adopt live workers without duplicating them.
No DeepSeek responses, client instances, credentials or model APIs are used.
"""
from __future__ import annotations
import argparse, concurrent.futures, datetime, fcntl, hashlib, json, os
from pathlib import Path
import re, shutil, subprocess, threading, time, traceback, sys
import run_models as rm
BASE=rm.BASE
CONTROL=BASE/'_проверка/codex_controller.json'
PRINT_LOCK=threading.Lock()

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def say(*args):
 with PRINT_LOCK:print(utc(),*args,flush=True)
def read(path):return json.loads(Path(path).read_text())
def process_state(pid,work):
 p=subprocess.run(['ps','-p',str(pid),'-o','stat=,command='],capture_output=True,text=True)
 text=p.stdout.strip()
 if not text:return 'finished'
 if text.split()[0].startswith('Z'):return 'finished'
 if 'codex' not in text or str(work) not in text:return 'pid_reused_or_unconfirmed'
 return 'running'
def terminal_event(path):
 terminal=None
 if not path.exists():return terminal
 with path.open()as f:
  for line in f:
   try:event=json.loads(line)
   except (ValueError,TypeError):continue
   if event.get('type')in ('turn.completed','turn.failed','thread.completed','thread.failed'):
    terminal={'type':event['type']}
    if event.get('error'):terminal['error']=str(event['error'])[:1000]
 return terminal
def locations(row):
 rid=row['report_id'];receipt=BASE/'_проверка/Codex'/rid/rm.RUN_VERSION/'receipt.json'
 work=Path('/private/tmp/sber-codex-transcription')/rm.RUN_VERSION/rid
 return receipt,work,rm.report_dir('Codex',row)
def copy_result(result,folder,checks):
 if not(result/'report.md').is_file():return False
 # Only publish this worker's expected result, without following arbitrary symlinks.
 for p in result.rglob('*'):
  if p.is_symlink():raise ValueError('Worker result contains symlink: '+str(p))
 folder.mkdir(parents=True,exist_ok=True)
 shutil.copy2(result/'report.md',folder/'report.md')
 if(result/'assets').is_dir():shutil.copytree(result/'assets',folder/'assets',dirs_exist_ok=True)
 if(result/'_проверка').is_dir():shutil.copytree(result/'_проверка',checks,dirs_exist_ok=True)
 return True
def assessed(row,index,receipt):
 receipt_path,work,folder=locations(row)
 gate=rm.validate_bundle(folder,index)
 states=rm.worker_page_states(receipt_path.parent/'worker_checks/pages.json',len(index['pages']))
 completion_known=(receipt.get('returncode')==0 if receipt.get('returncode_known',not receipt.get('adopted',False))else (receipt.get('terminal_event')or{}).get('type')in ('turn.completed','thread.completed'))
 identity=receipt.get('instruction_sha256')==rm.INSTRUCTION_SHA and receipt.get('source_sha256')==index['source_sha256']
 prompt_file=receipt_path.parent/'prompt.txt'
 prompt_ok=prompt_file.is_file()and receipt.get('prompt_sha256')==rm.sha(prompt_file)
 published_current=receipt.get('copied_worker_result',False)if receipt.get('adopted')else(receipt.get('assembled',False)and receipt.get('returncode')==0)
 assembled=bool(gate['assembled'])and bool(published_current)
 complete=assembled and bool(states['transcription_complete'])and completion_known and identity and prompt_ok
 receipt.update(assembled=assembled,complete=complete,transcription_complete=states['transcription_complete'],pending_pages=states['pending_pages'],bundle_errors=gate['errors'],pages_expected=len(index['pages']),page_markers_found=len(gate['markers']),review_status='converted'if complete else'pending',report_sha256=rm.sha(folder/'report.md')if(folder/'report.md').exists()else None,controller_assessed_at=utc(),identity_valid=identity,prompt_identity_valid=prompt_ok)
 if states.get('error'):receipt['worker_registry_error']=states['error']
 return receipt

def run_one(row,mark):
 rid=row['report_id'];receipt_path,work,folder=locations(row)
 mark(rid,'preparing_inputs')
 # The native PDF engine is not thread-safe; controller threads only run subprocesses.
 prepared=subprocess.run([sys.executable,str(BASE/'tools/prepare_index_isolated.py'),rid],capture_output=True,text=True)
 if prepared.returncode:raise RuntimeError('Isolated input preparation failed: '+prepared.stderr[-1500:])
 index=read(BASE/'_проверка/входы'/rid/'pages.json')
 running_file=receipt_path.parent/'running.json';events=receipt_path.parent/'events.jsonl'
 running=read(running_file)if running_file.exists()else None
 old=read(receipt_path)if receipt_path.exists()else None
 live_existing=bool(running and process_state(running['pid'],work)=='running')
 if not live_existing and old and old.get('source_sha256')==index['source_sha256']and old.get('instruction_sha256')==rm.INSTRUCTION_SHA and(folder/'report.md').exists():
  result=assessed(row,index,old);rm.put_json(receipt_path,result)
  mark(rid,'reused_assembled'if result['assembled']else'reused_pending',result)
  return result
 if running:
  if Path(running.get('work','')).resolve()!=work.resolve():raise ValueError('Existing running work path does not match expected worker')
  state=process_state(running['pid'],work)
  if state=='pid_reused_or_unconfirmed':raise ValueError('Existing PID belongs to another command; no restart/publication attempted')
  mark(rid,'adopting_running'if state=='running'else'adopting_finished',{'pid':running['pid'],'work':str(work)})
  while state=='running':
   done=terminal_event(events)
   if done:break
   time.sleep(5)
   state=process_state(running['pid'],work)
   if state=='pid_reused_or_unconfirmed':raise ValueError('PID identity changed during adoption')
  done=terminal_event(events)
  prompt=receipt_path.parent/'prompt.txt';agent=work/'AGENT.md';identity_errors=[]
  if not prompt.is_file():identity_errors.append('missing_existing_prompt')
  if not agent.is_file()or rm.sha(agent)!=rm.INSTRUCTION_SHA:identity_errors.append('existing_agent_hash_mismatch')
  copied=copy_result(work/'result',folder,receipt_path.parent/'worker_checks')
  result={'engine':'Codex CLI independent local-tools worker','version':rm.RUN_VERSION,'adopted':True,'adopted_pid':running['pid'],'adopted_at':utc(),'returncode':None,'returncode_known':False,'terminal_event':done,'copied_worker_result':copied,'instruction_sha256':rm.sha(agent)if agent.exists()else None,'expected_instruction_sha256':rm.INSTRUCTION_SHA,'source_sha256':index['source_sha256'],'prompt_sha256':rm.sha(prompt)if prompt.exists()else None,'identity_errors':identity_errors,'runtime_model_note':'Model identity is not inferred from PID or successful artifacts; see events.jsonl/runtime evidence.'}
  result=assessed(row,index,result)
  if identity_errors:result.update(complete=False,review_status='pending')
  rm.put_json(receipt_path,result)
  mark(rid,'adopted_assembled'if result['assembled']else'adopted_pending',result)
  say('ADOPTED',rid,'assembled',result['assembled'],'complete',result['complete'],'returncode',None)
  return result
 # No pre-existing worker: the original independent Codex implementation starts it.
 mark(rid,'launching_new_worker')
 result=rm.run_codex(row,index)
 result.setdefault('returncode_known',True);result.setdefault('adopted',False)
 result=assessed(row,index,result);rm.put_json(receipt_path,result)
 mark(rid,'assembled'if result['assembled']else'pending',result)
 say('FINISHED',rid,'assembled',result['assembled'],'complete',result['complete'])
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--reports',nargs='*');ap.add_argument('--workers',type=int,default=2);a=ap.parse_args()
 if not 1 <= a.workers <= 3:ap.error('Use one to three independent worker slots')
 lock_path=BASE/'_проверка/codex_controller.lock';lock_path.parent.mkdir(parents=True,exist_ok=True)
 lock=lock_path.open('a+')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise SystemExit('Another independent Codex controller is already running')
 unknown=set(a.reports or[])-{r['report_id']for r in rm.ROWS}
 if unknown:ap.error('Unknown report IDs: '+str(sorted(unknown)))
 rows=[r for r in rm.ROWS if not a.reports or r['report_id']in a.reports]
 # Existing live/finished-but-unpublished workers occupy the first slots.
 def priority(row):
  receipt,work,_=locations(row);running=receipt.parent/'running.json'
  data=read(running)if running.exists()else None
  live=bool(data and process_state(data['pid'],work)=='running')
  return (0 if live else 1 if running.exists()and not receipt.exists()else 2,rm.ROWS.index(row))
 rows.sort(key=priority)
 controller_sha=rm.sha(__file__)
 started=utc();states={r['report_id']:{'state':'queued'}for r in rows};state_lock=threading.RLock()
 def snapshot(overall='running'):
  counts={s:sum(x['state']==s for x in states.values())for s in sorted({x['state']for x in states.values()})}
  rm.put_json(CONTROL,{'pid':os.getpid(),'started_at':started,'updated_at':utc(),'finished_at':utc()if overall!='running'else None,'overall_status':overall,'version':rm.RUN_VERSION,'worker_slots':a.workers,'registered_reports':len(rm.ROWS),'scheduled_reports':len(rows),'instruction_sha256':rm.INSTRUCTION_SHA,'counts':counts,'reports':states,'quality_scope':'Structural assembly and worker conversion states; no claim of full source fidelity or checked review.','controller_file_sha256':controller_sha})
 def mark(rid,state,result=None):
  with state_lock:
   states[rid]={'state':state,'updated_at':utc()}
   if result is not None:
    states[rid]['result']={k:v for k,v in result.items()if k in ('assembled','complete','review_status','pending_pages','bundle_errors','returncode','returncode_known','adopted','pid','work','identity_valid','prompt_identity_valid')}
   snapshot()
 snapshot();say('START',os.getpid(),'reports',len(rows),'slots',a.workers)
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers)as pool:
  jobs={pool.submit(run_one,r,mark):r for r in rows}
  for f in concurrent.futures.as_completed(jobs):
   row=jobs[f];rid=row['report_id']
   try:f.result()
   except Exception as e:
    with state_lock:states[rid]={'state':'error','updated_at':utc(),'error':str(e)[:1200],'traceback':traceback.format_exc()};snapshot()
    say('ERROR',rid,type(e).__name__,str(e)[:200])
 with state_lock:
  ready=sum(x.get('result',{}).get('complete',False)for x in states.values())
  snapshot('finished'if ready==len(rows)else'finished_with_pending')
 say('END','complete',ready,'scheduled',len(rows))
if __name__=='__main__':main()
