"""Prepare blind sentence batches and deterministic production shortlist. No LLM/API.

Existing gold, chunks, and model answers are never rewritten. Production shortlist
is NOT exhaustive; evaluation of sentence decisions is separate from retrieval.
"""
from __future__ import annotations
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from select_gold_fragments import split_sentences, block_scores, INDEX_MARKERS

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'v1'
FUTURE = re.compile(r'планир|планиру|планов|цель|цели|целев|намерен|предстоит|продолжит|будет|будут|стремит|обязуется|к 20[2-5]\d', re.I)
DECL = re.compile(r'приоритет|привержен|ценност|важнейш|нулевой терпим|нулевая терпим|стремит|осозна[её]т|ответственност', re.I)
ACTION = re.compile(r'сниз|сократ|увелич|уменьш|провод|провед|внедр|введ|реализ|реализу|прошл|обуч|разработ|утвержд|осуществ|достиг|обеспеч|поддерж|сертифи|направ|предостав|соблюд|принят|действует|организ|вошл|включен|улучш|контрол|созда|создан|финансир|инвест|постро|выдел|оснащ|модерниз|реконструк|заверш|переработ|установ|установл|запущ|выполн|предотвра|предусмотр|защит', re.I)

def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    content=''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows)
    if path.exists():
        if path.read_text(encoding='utf-8') == content: return
        raise FileExistsError(path)
    path.write_text(content, encoding='utf-8')

def read_records(path):
    # Some upstream JSONL files contain literal newlines inside JSON strings.
    # Decode full JSON objects without dropping any records; leave sources intact.
    text=path.read_text(encoding='utf-8-sig'); decoder=json.JSONDecoder(strict=False); pos=0
    while pos<len(text):
        while pos<len(text) and text[pos].isspace():pos+=1
        if pos==len(text):break
        row,pos=decoder.raw_decode(text,pos)
        yield row

def main():
    output = ROOT/'batches'/'extract'/VERSION
    if (output/'freeze.json').exists():
        raise FileExistsError(output/'freeze.json')
    # No labels loaded: both source files contain only raw sentences and split metadata.
    raw = []
    for name in ('sentences.jsonl', 'sentences_commit.jsonl'):
        raw.extend(json.loads(l) for l in (ROOT/'data/gold_extract'/name).read_text().splitlines() if l.strip())
    keep = ('sentence_id', 'report_id', 'page', 'sentence', 'context')
    raw.sort(key=lambda x: x['sentence_id'])
    for shard in range(3):
        write_jsonl(output/f'eval_{shard+1:02d}.jsonl', [{k:r[k] for k in keep} for r in raw[shard::3]])
    pool = defaultdict(list)
    for path in sorted((ROOT/'data/chunks').glob('*.jsonl')):
        rid = path.stem
        company, year, *_ = rid.split('-')
        for ch in read_records(path):
            sents = split_sentences(ch['text'])
            for i, s in enumerate(sents):
                if not 90 <= len(s) <= 900 or len(INDEX_MARKERS.findall(s)) > 0:
                    continue
                if sum(c.isdigit() for c in s)/len(s) > .07:
                    continue
                scores = block_scores(s)
                if max(scores.values()) < 1:
                    continue
                future, decl, act = bool(FUTURE.search(s)), bool(DECL.search(s)), bool(ACTION.search(s))
                if not (future or decl or act):
                    continue
                block = max(scores, key=scores.get)
                intent = 'future' if future else 'declaration' if decl else 'result'
                score = min(sum(scores.values()), 10) + 2*act + 2*future + decl - max(0,len(s)-500)/300
                # The row remains an exact sentence within the chunk; never fixes source text.
                sid = f"{ch['chunk_id']}_s{i+1:02d}"
                pool[company].append(dict(sentence_id=sid, company_id=company, report_id=rid, year=year,
                    page=ch['page'], chunk_id=ch['chunk_id'], sentence=s,
                    context=' '.join(sents[max(0,i-1):i+2]), candidate_block=block, intent=intent, score=score))
    selected=[]
    for company, rows in sorted(pool.items()):
        rows.sort(key=lambda r:(-r['score'],r['sentence_id']))
        chosen=[]; seen=set(); page_count=Counter()
        def take(cands, n):
            for r in cands:
                key=re.sub(r'\W+','',r['sentence'].lower())
                pk=(r['report_id'],r['page'])
                if key in seen or page_count[pk]>=3:
                    continue
                chosen.append(r);seen.add(key);page_count[pk]+=1
                n-=1
                if n<=0: break
        # First guarantee sources and E/S/G across each year; then rare speech acts.
        for rid in sorted({r['report_id'] for r in rows}):
            for b in 'ESG': take([r for r in rows if r['report_id']==rid and r['candidate_block']==b],2)
        for intent,n in [('future',16),('declaration',10),('result',10)]:
            if len(chosen)<52: take([r for r in rows if r['intent']==intent], min(n,52-len(chosen)))
        if len(chosen)<52: take(rows,52-len(chosen))
        selected.extend(chosen)
    companies=sorted(pool)
    # Same company stays in one batch; rotation balances company sizes.
    for shard in range(3):
        cs=set(companies[shard::3])
        part=[r for r in selected if r['company_id'] in cs]
        write_jsonl(output/f'production_{shard+1:02d}.jsonl', [{k:r[k] for k in (*keep,'company_id','year','chunk_id')} for r in part])
    write_jsonl(output/'production_selection.jsonl',selected)
    meta={'version':VERSION,'eval_sentences':len(raw),'production_candidates':len(selected),
          'companies':len(companies),'selection':'lexicon + speech-act regex; max 52/company; max 3/page; all reports first',
          'codebook_sha256':hashlib.sha256((ROOT/'codebook/Инструкция_по_разметке_v4.md').read_bytes()).hexdigest(),
          'prompt_sha256':hashlib.sha256((ROOT/'prompts/extract_v1.md').read_bytes()).hexdigest(),
          'batches':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.glob('*.jsonl'))}}
    (output/'freeze.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(meta,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
