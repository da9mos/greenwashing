"""Validate immutable semantic answers and rebuild claims.csv without a model.

Never treats missing answers as negatives. Quotes are checked against sentence,
chunk AND page using whitespace normalization only. No fuzzy matching.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from prepare_extract import read_records
from extract_integrity import verify

ROOT=Path(__file__).resolve().parents[1]
from text_versions import FROZEN_EXTRACT_V1, VERSIONS, chunks_dir, pages_dir
CHUNKS=PAGES=None  # задаются в main() по --text-version
TOPICS={
 'E':{'вода','воздух','отходы','климат','биоразнообразие','земля','энергия','другое'},
 'S':{'безопасность труда','персонал и оплата','обучение','права человека','местные сообщества','клиенты и качество','другое'},
 'G':{'совет директоров и акционеры','этика и антикоррупция','раскрытие и заверение','управление рисками','поставщики','другое'}}
FIELDS='claim_id company_id year report_id page text type esg_block topic metric value unit base_year target_year has_number has_deadline prompt_version model sentence_id chunk_id second_type flag confidence source_url quote_check review_status'.split()
def norm(s): return re.sub(r'\s+',' ',s).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pdf_extra_sample(accepted,sample):
 import random
 text_only={'MVDK-2023-ГО','MVDK-2025-ГО'}
 n=sum(r['report_id'] in text_only for r in sample)
 used={r['claim_id'] for r in sample}
 eligible=[r for r in accepted if r['report_id'] not in text_only and r['claim_id'] not in used]
 return random.Random(20261116).sample(eligible,n)
def write_csv(p,rows,fields):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,delimiter=';');w.writeheader();w.writerows(rows)

def validate(p):
 sid=p.get('sentence_id','?')
 required={'sentence_id','is_claim','type','esg_block','topic','has_number','has_deadline'}
 if not required<=p.keys():raise ValueError(f'Missing fields: {sid}')
 if p['is_claim'] not in ('да','нет'):raise ValueError(f'is_claim: {sid}')
 if p['is_claim']=='нет':
  if any(p[k] for k in ('type','esg_block','topic','has_number','has_deadline')):raise ValueError(f'negative has labels: {sid}')
  return
 if p['type'] not in ('обязательство','результат','декларация'):raise ValueError(f'type: {sid}')
 if p['esg_block'] not in TOPICS or p['topic'] not in TOPICS[p['esg_block']]:raise ValueError(f'topic/block: {sid}')
 if p['has_number'] not in ('да','нет'):raise ValueError(f'has_number: {sid}')
 if p['has_deadline'] not in (('да','нет') if p['type']=='обязательство' else ('',)):raise ValueError(f'has_deadline: {sid}')
 if p.get('second_type','') not in ('','обязательство','результат','декларация'):raise ValueError(f'second_type: {sid}')
 if p.get('confidence','') not in ('высокая','средняя','низкая'):raise ValueError(f'confidence: {sid}')

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--version',default='v1');ap.add_argument('--output-dir',type=Path)
 # extract v1 заморожен на текстах v2 (хэши в source_hashes); новые версии извлечения — на v4
 ap.add_argument('--text-version',choices=VERSIONS,default=None)
 args=ap.parse_args();v=args.version
 global CHUNKS,PAGES
 tv=args.text_version or (FROZEN_EXTRACT_V1 if v=='v1' else None)
 if v=='v1' and tv!=FROZEN_EXTRACT_V1:raise SystemExit('extract v1 собран на текстах v2 и заморожен')
 CHUNKS,PAGES=chunks_dir(tv),pages_dir(tv)
 verify(v)
 batchdir=ROOT/'batches/extract'/v;predir=ROOT/'llm/extract'/v
 out=args.output_dir or ROOT/'data/extract'/v
 if out.exists():raise FileExistsError(out)
 frozen=json.loads((batchdir/'freeze.json').read_text())
 for name,h in frozen['batches'].items():
  if sha(batchdir/name)!=h:raise ValueError(f'Batch changed: {name}')
 if sha(ROOT/f'prompts/extract_{v}.md')!=frozen['prompt_sha256']:raise ValueError('Prompt changed')
 if sha(ROOT/'codebook/Инструкция_по_разметке_v4.md')!=frozen['codebook_sha256']:raise ValueError('Codebook changed')
 inputs=[];predictions=[];manifest=[];now=datetime.now(timezone.utc).isoformat()
 for f in sorted(batchdir.glob('production_0*.jsonl')):
  inp=list(read_records(f));pf=predir/f.name;pred=list(read_records(pf))
  if len({p['sentence_id'] for p in pred})!=len(pred):raise ValueError(f'Duplicate: {pf}')
  if {r['sentence_id'] for r in inp}!={p['sentence_id'] for p in pred}:raise ValueError(f'ID coverage: {pf}')
  for p in pred:validate(p)
  inputs+=inp;predictions+=pred
  manifest.append(dict(batch_id=f'extract_{v}_{f.stem}',stage='extract',company_id='',report_id='',
   input_file=str(f.relative_to(ROOT)),input_sha256=sha(f),prompt_file=f'prompts/extract_{v}.md',
   prompt_sha256=frozen['prompt_sha256'],model='Codex (точная версия модели в экспорте не записана)',
   thread=f'Codex / {f.stem}',started_at='',finished_at='',validated_at=now,status='validated',n_items=len(inp),
   n_rejected=sum(p['is_claim']=='нет' for p in pred),checked_by='build_extract.py',
   output_file=str(pf.relative_to(ROOT)),output_sha256=sha(pf)))
 byid={p['sentence_id']:p for p in predictions}
 if len(byid)!=len(predictions):raise ValueError('Cross-batch duplicate')
 chunks={};pages={}
 for rid in sorted({r['report_id'] for r in inputs}):
  chunks[rid]={r['chunk_id']:r for r in read_records(CHUNKS/f'{rid}.jsonl')}
  page_rows=list(read_records(PAGES/f'{rid}.jsonl'))
  pages[rid]={int(r['page']):r for r in page_rows}
  if len(pages[rid])!=len(page_rows):raise ValueError(f'Duplicate pages: {rid}')
 reports={r['report_id']:r for r in csv.DictReader((ROOT.parent/'01_итерация_1_сбор_данных/выборка_30/reports.csv').open(encoding='utf-8-sig'),delimiter=';')}
 accepted=[];excluded=[];seen=set();duplicates=[];review=[]
 for inp in sorted(inputs,key=lambda x:x['sentence_id']):
  p=byid[inp['sentence_id']]
  if p['is_claim']=='нет':
   excluded.append(dict(sentence_id=inp['sentence_id'],report_id=inp['report_id'],page=inp['page'],sentence=inp['sentence'],reason=p.get('reason','')));continue
  text=p.get('quote',inp['sentence']);q=norm(text)
  rid=inp['report_id'];ch=chunks[rid][inp['chunk_id']];pg=pages[rid][int(inp['page'])]
  if not q or q not in norm(inp['sentence']) or q not in norm(ch['text']) or q not in norm(pg['text']):
   raise ValueError(f'Quote not in sentence/chunk/page: {inp["sentence_id"]}')
  if int(ch['page'])!=int(inp['page']):raise ValueError(f'Page mismatch: {inp["sentence_id"]}')
  key=(inp['company_id'],inp['year'],q.casefold())
  if key in seen:
   duplicates.append(dict(sentence_id=inp['sentence_id'],report_id=rid,page=inp['page'],text=text));continue
  seen.add(key)
  # Numeric value/target inference requires a separate extraction pass. Empty is honest.
  row={k:'' for k in FIELDS}
  row.update({k:inp[k] for k in ('company_id','year','report_id','page','sentence_id','chunk_id')})
  row.update({k:p.get(k,'') for k in ('type','esg_block','topic','has_number','has_deadline','second_type','flag','confidence')})
  row.update(text=text,prompt_version=f'extract_{v}',model=manifest[0]['model'],
   source_url=f"https://drive.google.com/file/d/{reports[rid]['drive_id']}/view",quote_check='exact_whitespace_normalized',
   review_status='нужна проверка' if p.get('confidence')=='низкая' else 'проверено по тексту страницы')
  if p.get('confidence')=='низкая':review.append(row)
  else:accepted.append(row)
 counts=Counter()
 for r in accepted:
  k=(r['company_id'],r['year']);counts[k]+=1;r['claim_id']=f'{k[0]}-{k[1]}-{counts[k]:03d}'
 quality={'n_inputs':len(inputs),'n_claims':len(accepted),'n_negative':len(excluded),'n_duplicates':len(duplicates),
  'companies':len({r['company_id'] for r in accepted}),'reports':len({r['report_id'] for r in accepted}),
  'by_type':dict(Counter(r['type'] for r in accepted)),'by_block':dict(Counter(r['esg_block'] for r in accepted)),
  'by_year':dict(Counter(r['year'] for r in accepted)),'low_confidence':len(review),
  'exact_quotes':len(accepted),'fuzzy_quotes':0,'scope':'selected candidates, not exhaustive full-corpus extraction',
  'numeric_fields':'metric/value/unit/base_year/target_year left empty; not inferred',
  'companies_detail':{c:{'n':sum(r['company_id']==c for r in accepted),
   'reports':sorted({r['report_id'] for r in accepted if r['company_id']==c}),
   'blocks':sorted({r['esg_block'] for r in accepted if r['company_id']==c}),
   'years':sorted({r['year'] for r in accepted if r['company_id']==c})} for c in sorted({r['company_id'] for r in inputs})},
  'source_hashes':{str(p.relative_to(ROOT)):sha(p) for rid in sorted(chunks) for p in (PAGES/f'{rid}.jsonl',CHUNKS/f'{rid}.jsonl')}}
 quality['acceptance']={
  'at_least_500_claims':len(accepted)>=500,
  'all_30_companies':quality['companies']==30,
  'at_least_2_reports_per_company':all(len(x['reports'])>=2 for x in quality['companies_detail'].values()),
  'all_3_blocks_per_company':all(set(x['blocks'])==set('ESG') for x in quality['companies_detail'].values()),
  'no_unmatched_quotes':True}
 quality['acceptance']['passed']=all(quality['acceptance'].values())
 write_csv(out/'claims.csv',accepted,FIELDS)
 write_csv(out/'claims_review.csv',review,FIELDS)
 write_csv(out/'excluded.csv',excluded,['sentence_id','report_id','page','sentence','reason'])
 write_csv(out/'duplicates.csv',duplicates,['sentence_id','report_id','page','text'])
 write_csv(out/'manifest.csv',manifest,list(manifest[0]))
 write_csv(out/'coverage.csv',[dict(company_id=c,n_claims=x['n'],n_reports=len(x['reports']),
  blocks=','.join(x['blocks']),years=','.join(map(str,x['years']))) for c,x in quality['companies_detail'].items()],
  ['company_id','n_claims','n_reports','blocks','years'])
 (out/'quality.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2)+'\n')
 # Deterministic human review list: 20 pilot NORN + 10 sample spread across companies.
 import random
 pilot=[r for r in accepted if r['company_id']=='NORN'][:20]
 sample=random.Random(20261115).sample(accepted,min(10,len(accepted)))
 write_csv(out/'review_sample.csv',[dict(**r,review_group=g,pdf_checked='',review_note='') for g,rs in [('pilot_NORN',pilot),('random_10',sample)] for r in rs],FIELDS+['review_group','pdf_checked','review_note'])
 write_csv(out/'review_pdf_extra.csv',[dict(**r,review_group='random_pdf_replacement',pdf_checked='',review_note='Дополнительная случайная PDF-строка вместо текстового источника; исходная выборка сохранена') for r in pdf_extra_sample(accepted,sample)],FIELDS+['review_group','pdf_checked','review_note'])
 print(json.dumps({k:quality[k] for k in ('n_claims','n_negative','companies','reports','by_type','by_block','low_confidence')},ensure_ascii=False))
 if not quality['acceptance']['passed']:
  raise SystemExit(f"Acceptance failed; diagnostics saved: {quality['acceptance']}")

if __name__=='__main__':main()
