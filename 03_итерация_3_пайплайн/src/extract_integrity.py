"""Freeze and verify extraction inputs. Never overwrite a prior freeze."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def sha(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(version='v1'):
 path=ROOT/'runs'/f'extract_{version}_freeze.json'
 frozen=json.loads(path.read_text(encoding='utf-8'))
 for name,expected in frozen['files'].items():
  source=ROOT/name
  if not source.is_file() or sha(source)!=expected:
   raise ValueError(f'Frozen source/answer changed or missing: {name}')
 return frozen

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--version',default='v1');ap.add_argument('--freeze',action='store_true')
 a=ap.parse_args();v=a.version
 if not a.freeze:
  d=verify(v);print(f"Verified {len(d['files'])} frozen inputs");return
 out=ROOT/'runs'/f'extract_{v}_freeze.json'
 if out.exists():raise FileExistsError(out)
 from text_versions import CURRENT, FROZEN_EXTRACT_V1, chunks_dir, pages_dir
 tv=FROZEN_EXTRACT_V1 if v=='v1' else CURRENT
 paths=list(pages_dir(tv).glob('*.jsonl'))+list(chunks_dir(tv).glob('*.jsonl'))
 paths+=list((ROOT/'batches/extract'/v).glob('*'))
 paths+=[ROOT/'llm/extract'/v/f'{kind}_{i:02d}.jsonl' for kind in ('eval','production') for i in range(1,4)]
 paths+=[ROOT/'llm/extract'/v/'repeat_30.jsonl',ROOT/'llm/baseline_extract/v1/predictions.jsonl',
  ROOT/'data/out/gold_extract.csv',ROOT/f'prompts/extract_{v}.md',ROOT/'codebook/Инструкция_по_разметке_v4.md',
  ROOT.parent/'01_итерация_1_сбор_данных/выборка_30/reports.csv',ROOT.parent/'01_итерация_1_сбор_данных/выборка_30/companies.csv']
 files={str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else '../'+str(p.relative_to(ROOT.parent)):sha(p) for p in sorted(paths)}
 data={'version':v,'frozen_at_utc':datetime.now(timezone.utc).isoformat(),
  'scope':'delivery input freeze after semantic responses; prompt and eval responses were frozen separately before scoring',
  'files':files}
 with out.open('x',encoding='utf-8') as f:f.write(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 verify(v);print(f'Frozen {len(files)} input files: {out}')

if __name__=='__main__':main()
