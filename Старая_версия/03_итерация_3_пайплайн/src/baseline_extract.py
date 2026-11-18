"""Fixed lexical baseline, explicitly NOT a model answer. No gold labels used."""
import argparse
import json
import re
from pathlib import Path
from select_gold_fragments import block_scores
from prepare_extract import read_records,FUTURE,DECL,ACTION

ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 rows=[]
 for f in sorted((ROOT/'batches/extract/v1').glob('eval_*.jsonl')):
  for r in read_records(f):
   s=r['sentence'];scores=block_scores(s)
   yes=max(scores.values())>0 and bool(FUTURE.search(s) or DECL.search(s) or ACTION.search(s))
   typ=('обязательство' if FUTURE.search(s) else 'декларация' if DECL.search(s) else 'результат') if yes else ''
   number=bool(re.search(r'\d+(?:[,.]\d+)?\s*(?:%|тыс|млн|млрд|человек|сотрудник|работник|тонн)',s,re.I))
   deadline=bool(re.search(r'(?:к|до|в)\s+20[2-5]\d\s*(?:году|года|г\.)',s,re.I))
   rows.append(dict(sentence_id=r['sentence_id'],is_claim='да' if yes else 'нет',type=typ,
     esg_block=max(scores,key=scores.get) if yes else '',topic='другое' if yes else '',
     has_number=('да' if number else 'нет') if yes else '',
     has_deadline=('да' if deadline else 'нет') if typ=='обязательство' else ''))
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('x',encoding='utf-8') as f:
  for r in sorted(rows,key=lambda x:x['sentence_id']):f.write(json.dumps(r,ensure_ascii=False)+'\n')
 print(f'{len(rows)} lexical decisions; no LLM')
if __name__=='__main__':main()
