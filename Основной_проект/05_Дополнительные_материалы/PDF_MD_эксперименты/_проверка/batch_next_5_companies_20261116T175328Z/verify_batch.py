from pathlib import Path
import sys,json,hashlib,datetime
AUDIT=Path(__file__).resolve().parent
BASE=AUDIT.parents[1]
sys.path.insert(0,str(BASE/'tools'))
import run_models as rm
rids=json.loads((AUDIT/'launch.json').read_text())['reports'];records={}
for rid in rids:
 row=next(r for r in rm.ROWS if r['report_id']==rid)
 folder=rm.report_dir('Codex',row)
 if not (folder/'report.md').is_file():records[rid]={'state':'waiting'};continue
 check=BASE/'_проверка/Codex'/rid/'v2'
 receipt=json.loads((check/'receipt.json').read_text())
 index=json.loads((BASE/'_проверка/входы'/rid/'pages.json').read_text())
 gate=rm.validate_bundle(folder,index)
 states=rm.worker_page_states(check/'worker_checks/pages.json',len(index['pages']))
 current=rm.sha(folder/'report.md');source=rm.sha(BASE/index['source'])
 errors=list(gate['errors'])
 if current!=receipt.get('report_sha256'):errors.append('receipt_md_hash_mismatch')
 if source!=receipt.get('source_sha256') or source!=index['source_sha256']:errors.append('source_identity_mismatch')
 if receipt.get('instruction_sha256')!=rm.INSTRUCTION_SHA:errors.append('instruction_identity_mismatch')
 if rm.sha(check/'prompt.txt')!=receipt.get('prompt_sha256'):errors.append('prompt_identity_mismatch')
 records[rid]={'state':'structurally_valid' if gate['assembled'] and not errors else 'error','errors':errors,'pages':len(index['pages']),'page_markers':len(gate['markers']),'report_sha256':current,'transcription_complete':states['transcription_complete'],'pending_pages':states['pending_pages'],'full_source_review':'not_confirmed'}
summary={'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reports':records,'structurally_valid':sum(x['state']=='structurally_valid' for x in records.values()),'waiting':sum(x['state']=='waiting' for x in records.values()),'errors':sum(x['state']=='error' for x in records.values()),'scope':'Independent structural revalidation, source/prompt/MD identity; not full semantic PDF review'}
(AUDIT/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='reports'},ensure_ascii=False))
if summary['errors']:raise SystemExit(1)
