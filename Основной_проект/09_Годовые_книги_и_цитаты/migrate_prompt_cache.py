"""Preserve the old prompt and revalidate legacy responses without claiming a model rerun."""
from pathlib import Path
import importlib.util,json,hashlib
PROJECT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('annual_controller',PROJECT/'06_Прогон_корпуса/run_corpus.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
old=PROJECT/'09_Годовые_книги_и_цитаты/03_Правила_цитирования/previous_prompt/esg_agent_v3_1.md'
oldsha=c.worker.base.sha(old);newsha=c.worker.base.sha(c.worker.AGENT/'agent/esg_agent_v3_1.md')
frozen=c.STATE/'frozen_prompts'/(oldsha+'.md');frozen.parent.mkdir(exist_ok=True)
if not frozen.exists(): frozen.write_bytes(old.read_bytes())
assert c.worker.base.sha(frozen)==oldsha
prior_path=PROJECT/'09_Годовые_книги_и_цитаты/prompt_cache_migration.json'
prior=json.loads(prior_path.read_text()) if prior_path.exists() else {}
record={'old_prompt_sha256':oldsha,'new_prompt_sha256':newsha,'model_rerun':False,'legacy_display_prepared':False,'manifest_relocations':prior.get('manifest_relocations',[]),'responses':[]}
for work in c.STATE.glob('*-'+oldsha[:10]+'/prepared'):
 p=work/'manifest.json';m=c.worker.base.read(p)
 if m['prompt_sha256']!=oldsha: continue
 if m['prompt_path']!=str(frozen):
  record['manifest_relocations'].append({'path':str(p),'before':m})
  m['prompt_path']=str(frozen);c.worker.base.write(p,m);(work/'manifest.sha256').write_text(c.worker.base.sha(p))
for report in c.registry():
 src=c.STATE/f"{report['report_id']}-{report['packaged_md_sha256'][:10]}-{oldsha[:10]}"
 if not (src/'prepared').exists(): continue
 dst=c.cache_for(report);work=dst/'prepared'
 if not work.exists(): c.worker.profile.prepare(PROJECT/report['repository_path'],work,report['report_id'])
 for path in sorted((src/'accepted').glob('*.json')):
  entry={'report_id':report['report_id'],'parent_response':str(path),'parent_sha256':c.worker.base.sha(path)}
  try:
   data,_=c.worker.profile.check(src/'prepared',path)
   # Source text, batch context, taxonomy and decision rules must be identical.
   sm=c.worker.base.read(src/'prepared/manifest.json');dm=c.worker.base.read(work/'manifest.json')
   assert all(sm[k]==dm[k] for k in ('source_sha256','blocks_sha256','pages_sha256','taxonomy_sha256','decision_rules_sha256'))
   sb=next(b for b in sm['batches'] if b['id']==data['batch_id']);db=next(b for b in dm['batches'] if b['id']==data['batch_id'])
   original_batch=c.worker.base.read(src/'prepared'/sb['file']);current_batch=c.worker.base.read(work/db['file'])
   assert {k:v for k,v in original_batch.items() if k!='prompt_sha256'}=={k:v for k,v in current_batch.items() if k!='prompt_sha256'}, 'Batch content differs beyond prompt identity'
   target=dst/'accepted'/path.name;target.parent.mkdir(exist_ok=True)
   data['presentation_policy_migration']={'parent_response_sha256':entry['parent_sha256'],'extraction_prompt_sha256':oldsha,'workspace_prompt_sha256':newsha,'model_rerun':False,'note':'Legacy analytical response; a display quote was not newly prepared.'}
   if not target.exists(): c.worker.base.write(target,data)
   _,stats=c.worker.profile.check(work,target)
   entry.update(status='legacy_revalidated',target=str(target),target_sha256=c.worker.base.sha(target),claims=len(data['claims']),presentation_ready_claims=stats['presentation_ready_claims'])
  except (ValueError,KeyError,TypeError,OSError,AssertionError) as exc:
   entry.update(status='not_promoted',reason=str(exc))
  record['responses'].append(entry)
out=PROJECT/'09_Годовые_книги_и_цитаты/prompt_cache_migration.json'
c.atomic(out,record)
print(json.dumps({'manifest_relocations':len(record['manifest_relocations']),'responses':len(record['responses']),'migrated':sum(x['status']=='legacy_revalidated' for x in record['responses']),'not_promoted':sum(x['status']=='not_promoted' for x in record['responses'])},ensure_ascii=False))
