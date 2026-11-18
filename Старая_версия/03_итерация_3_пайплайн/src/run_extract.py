"""Rebuild extraction artifacts from frozen inputs and saved model answers.

python src/run_extract.py --output-root data/rebuilt_extract/run_01
No model/API calls. The destination must not exist. Does not change gold or sources.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from extract_integrity import verify

ROOT=Path(__file__).resolve().parents[1]
# Извлечение v1 заморожено на текстах v2 и исходном эталоне: пересборка всегда берёт их,
# какая бы версия текстов ни была действующей (src/text_versions.py).
GOLD_V1=ROOT/'data/out/gold_extract.csv'
def _rounded(x):
 if isinstance(x,float):return round(x,10)
 if isinstance(x,dict):return {k:_rounded(v) for k,v in x.items()}
 if isinstance(x,list):return [_rounded(v) for v in x]
 return x
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--output-root',type=Path,required=True)
 p.add_argument('--version',default='v1')
 a=p.parse_args();out=a.output_root
 verify(a.version)
 expected=json.loads((ROOT/'runs'/f'extract_{a.version}_artifacts.json').read_text(encoding='utf-8'))
 for name,h in expected['canonical_files'].items():
  if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h:raise ValueError(f'Canonical artifact changed: {name}')
 if not out.is_absolute():out=ROOT/out
 if out.exists():raise FileExistsError(out)
 pred=ROOT/'llm/extract'/a.version
 batch=ROOT/'batches/extract'/a.version
 freeze=json.loads((batch/'freeze.json').read_text())
 for name,h in freeze['batches'].items():
  if hashlib.sha256((batch/name).read_bytes()).hexdigest()!=h:raise ValueError(f'Changed batch {name}')
 inputs=set();rows=[]
 for i in range(1,4):
  name=f'eval_{i:02d}.jsonl'
  inp=[json.loads(l) for l in (batch/name).read_text().splitlines() if l.strip()]
  ans=[json.loads(l) for l in (pred/name).read_text().splitlines() if l.strip()]
  if len(ans)!=len(inp) or {r['sentence_id'] for r in inp}!={r['sentence_id'] for r in ans}:raise ValueError(f'Incomplete {name}')
  for r in ans:
   if r['sentence_id'] in inputs:raise ValueError('Duplicate eval ID')
   inputs.add(r['sentence_id']);rows.append(r)
 out.mkdir(parents=True)
 allpred=out/'eval_predictions.jsonl'
 allpred.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in sorted(rows,key=lambda r:r['sentence_id'])),encoding='utf-8')
 subprocess.run([sys.executable,str(ROOT/'src/evaluate_extract.py'),'--predictions',str(allpred),'--output-dir',str(out/'evaluation'),'--gold',str(GOLD_V1)],check=True)
 policy=[]
 for r in sorted(rows,key=lambda r:r['sentence_id']):
  r=dict(r)
  if r.get('confidence')=='низкая':
   r.update(is_claim='нет',type='',esg_block='',topic='',has_number='',has_deadline='',second_type='',flag='',reason='Производственная политика: низкая уверенность направляется на проверку')
  policy.append(r)
 policy_file=out/'policy_input_v1.jsonl'
 policy_file.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in policy),encoding='utf-8')
 subprocess.run([sys.executable,str(ROOT/'src/evaluate_extract.py'),'--predictions',str(policy_file),'--output-dir',str(out/'policy_evaluation'),'--gold',str(GOLD_V1)],check=True)
 subprocess.run([sys.executable,str(ROOT/'src/evaluate_extract.py'),'--predictions',str(ROOT/'llm/baseline_extract/v1/predictions.jsonl'),'--output-dir',str(out/'baseline_evaluation'),'--gold',str(GOLD_V1)],check=True)
 repeated=[json.loads(l) for l in (pred/'repeat_30.jsonl').read_text().splitlines() if l.strip()]
 original={r['sentence_id']:r for r in rows}
 fields=['is_claim','type','esg_block','topic','has_number','has_deadline']
 agreement={'n':len(repeated),'sample_seed':20261115,
  'scope':'independent second stream on 30 randomly selected eval_01 sentences; not a new model/version study',
  'agreement':{k:{'same':sum(r[k]==original[r['sentence_id']][k] for r in repeated),'n':len(repeated)} for k in fields},
  'disagreements':[{'sentence_id':r['sentence_id'],'fields':[k for k in fields if r[k]!=original[r['sentence_id']][k]]} for r in repeated if any(r[k]!=original[r['sentence_id']][k] for k in fields)],
  'hashes':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [batch/'repeat_30.jsonl',pred/'repeat_30.jsonl']}}
 (out/'repeat_v1.json').write_text(json.dumps(agreement,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 subprocess.run([sys.executable,str(ROOT/'src/build_extract.py'),'--version',a.version,'--output-dir',str(out/'production')],check=True)
 for name,h in expected['production_files'].items():
  if hashlib.sha256((out/'production'/name).read_bytes()).hexdigest()!=h:raise ValueError(f'Rebuild differs: {name}')
 for generated,canonical in [('evaluation','v1'),('policy_evaluation','policy_v1'),('baseline_evaluation','baseline_v1')]:
  groups=json.loads((out/generated/'metrics.json').read_text())['groups']
  reference=json.loads((ROOT/'data/extract_evaluation'/canonical/'metrics.json').read_text())['groups']
  # 16.11.2026: сравнение с округлением до 10 знаков. На другом компьютере (другая версия Python
  # или процессор) последняя цифра дроби может отличаться: 0,7674461365876654 и …653 — это одно число.
  if _rounded(groups)!=_rounded(reference):raise ValueError(f'Metrics differ: {generated}')
 if hashlib.sha256((out/'repeat_v1.json').read_bytes()).hexdigest()!=expected['repeat_sha256']:raise ValueError('Repeat agreement differs')
 print('Canonical CSV/quality hashes, metric groups and repeat agreement match exactly')
 print(f'Rebuilt: {out}')
if __name__=='__main__':main()
