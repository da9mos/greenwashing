"""Recover a real partial result after the adapter's duplicate-ingest failure; never change the ledger."""
from pathlib import Path
import importlib.util,json,shutil,time,hashlib
PROJECT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('corpus',PROJECT/'06_Прогон_корпуса/run_corpus.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
root=Path.home()/'.local/state/sber-esg-worker/research_runs/GAZP-2023-ОУР/79b50fd8685634b0044bd64c8012293327a019297d1bacbf1c10e2e796a7a358'
report=next(r for r in c.registry() if r['report_id']=='GAZP-2023-ОУР')
claim=c.worker.base.read(root/'input-claim.json')['claims'][0]
_,current=c.inspect_report(report)
assert claim in current['claims']
assert c.worker.base.read(root/'report.json')['packaged_md_sha256']==report['packaged_md_sha256']
plan=c.worker.factcheck.load(root/'run')
packet=c.worker.factcheck.results(root/'run',plan)['C000001']
c.worker.factcheck.validate(packet,plan)
assert packet['revision']==1 and packet['research_status']=='partial' and packet['verdict']=='not_verifiable'
assert c.worker.base.read(root/'response.json')==packet
journal=next(root.glob('attempts/r000001-*/native_events.jsonl'))
events=[]
for line in journal.read_text().splitlines():
 try: events.append(json.loads(line))
 except json.JSONDecodeError: pass
searches=[e for e in events if isinstance(e,dict) and e.get('type')=='item.completed' and isinstance(e.get('item'),dict) and e['item'].get('type') in ('web_search','web_search_call')]
assert searches
path=c.research_path(report,claim)
proof=PROJECT/'08_Аудит_агентов_2026-11-20/03_Фактчекинг/live_adapter_recovery'
proof.mkdir(exist_ok=True)
shutil.copy2(path,proof/'previous_failed_envelope.json')
c.atomic(proof/'accepted_real_packet.json',packet)
result={'report_id':report['report_id'],'claim_id':claim['id'],'status':'partial','packet':packet,'research_run':str(root/'run'),'display':{'searched':True,'status':'Поиск требует продолжения','reason':packet['reason'],'links':[s['url'] for s in packet['sources']]}}
record={'report_id':report['report_id'],'claim_id':claim['id'],'source_sha256':report['packaged_md_sha256'],'updated_at':c.now(),'result':result,'retry_after_epoch':time.time()+3600,'recovery':{'reason':'Exact accepted revision recovered after outer adapter attempted duplicate ingest; no new model or search run','native_web_search_events':len(searches),'journal_sha256':hashlib.sha256(journal.read_bytes()).hexdigest(),'journal_path':str(journal),'checkpoint_changed':False}}
c.atomic(path,record);c.atomic(proof/'recovery.json',record)
print(json.dumps({'status':result['status'],'native_web_search_events':len(searches),'checkpoint_changed':False},ensure_ascii=False))
