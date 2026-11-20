#!/usr/bin/env python3
"""Portable evidence ledger. No model, API or search is executed by this CLI."""
import argparse
import contextlib
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
from collections import Counter
from datetime import datetime

SCHEMA = 'esg-factcheck-1.0'
VERDICTS = {'true', 'false', 'partial', 'insufficient_evidence', 'not_verifiable', 'not_due'}
AXES = ('entity', 'period', 'boundary', 'metric', 'unit')
HERE = Path(__file__).resolve().parent


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_bytes(data)
    os.replace(temp, path)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def timestamp(value):
    require(nonempty(value), 'timestamp required')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(dt.tzinfo is not None, 'timestamp must include timezone')


@contextlib.contextmanager
def lock(run):
    path = Path(run) / '.lock'
    try:
        path.mkdir()
    except FileExistsError:
        raise ValueError('run locked; concurrent writer or stale .lock; inspect before removing')
    try:
        yield
    finally:
        path.rmdir()


RISK_CATEGORIES = ('rosp_enforcement', 'rost_enforcement', 'court_cases', 'media_incidents')


def prepare(source, run, prompt=None):
    source, run = Path(source), Path(run)
    require(not run.exists(), 'output exists; use next to resume')
    raw = source.read_bytes()
    obj = json.loads(raw.decode('utf-8-sig'))
    rows = obj if isinstance(obj, list) else obj.get('claims', obj.get('rows'))
    require(isinstance(rows, list), 'claims/rows array required')
    extraction_manifest = obj.get('manifest', {}) if isinstance(obj, dict) else {}
    batch_ids = {b['id'] for b in extraction_manifest.get('batches', [])}
    if batch_ids:
        coverage = obj.get('coverage', [])
        coverage_complete = (isinstance(coverage, list) and bool(coverage)
                             and all(e.get('status') in {'extracted', 'excluded'} for e in coverage)
                             and all(c.get('source_status') != 'needs_pdf_review'
                                     and c.get('decision', {}).get('classification_status') != 'pending'
                                     for c in rows))
    else:
        coverage_complete = False
    require(isinstance(rows, list) and (rows or coverage_complete), 'claims required unless full extraction had no claims')
    ledger = []
    for i, row in enumerate(rows):
        require(isinstance(row, dict), 'claim must be object')
        quote = row.get('quote', row.get('statement'))
        require(nonempty(quote), f'row {i}: quote/statement required')
        ledger.append({'id': f'C{i+1:06}', 'source_id': row.get('id', row.get('claim_id')),
                       'input_index': i, 'quote': quote, 'original': row})
    prompt = Path(prompt) if prompt else HERE / 'FACT_CHECK_AGENT.md'
    prompt_bytes = prompt.read_bytes()
    plan = {'schema_version': SCHEMA, 'source_sha256': digest(raw), 'claims': ledger,
            'report_id': extraction_manifest.get('report_id'), 'md_sha256': extraction_manifest.get('source_sha256'),
            'extraction_coverage_complete': coverage_complete,
            'search_directions': ['support', 'contradiction'],
            'required_risk_categories': list(RISK_CATEGORIES),
            'instruction': 'Researcher must specify atomic aspects, entity/period/boundary, then run both search directions. This is a queue, not completed research.'}
    files = {'input.json': raw, 'plan.json': encoded(plan), 'prompt.md': prompt_bytes}
    run.mkdir(parents=True)
    for name, data in files.items():
        atomic(run / name, data)
    manifest = {'schema_version': SCHEMA, 'files': {n: digest(b) for n, b in files.items()},
                'claims_count': len(ledger)}
    atomic(run / 'manifest.json', encoded(manifest))
    atomic(run / 'manifest.sha256', digest(encoded(manifest)).encode())
    (run / 'results').mkdir()
    return manifest


def load(run):
    run = Path(run)
    raw = (run / 'manifest.json').read_bytes()
    require(digest(raw) == (run / 'manifest.sha256').read_text(), 'manifest changed')
    m = json.loads(raw)
    require(m['schema_version'] == SCHEMA, 'schema mismatch')
    for name, expected in m['files'].items():
        require(digest((run / name).read_bytes()) == expected, f'changed snapshot: {name}')
    return read(run / 'plan.json')


def validate(packet, plan):
    require(isinstance(packet, dict), 'packet object required')
    require(packet.get('schema_version') == SCHEMA, 'schema mismatch')
    require(packet.get('source_sha256') == plan['source_sha256'], 'wrong input hash')
    claim = next((c for c in plan['claims'] if c['id'] == packet.get('claim_id')), None)
    require(claim is not None, 'unknown claim ID')
    require(packet.get('quote') == claim['quote'], 'claim quote changed')
    require(nonempty(packet.get('reviewer')), 'reviewer required')
    timestamp(packet.get('checked_at'))
    require(type(packet.get('revision')) is int and packet['revision'] >= 1, 'revision integer >=1 required')
    state = packet.get('research_status')
    require(state in {'complete', 'partial', 'blocked'}, 'invalid research status')
    require(nonempty(packet.get('reason')), 'reason required')
    target = packet.get('target', {})
    for name in ('proposition', 'entity', 'period', 'boundary', 'assessment_object'):
        require(nonempty(target.get(name)), f'target.{name} required (use explicit unknown)')
    require(target['assessment_object'] in {'reported_fact', 'promise_made', 'promise_fulfillment', 'principle'}, 'invalid assessment_object')
    sources = packet.get('sources', [])
    searches = packet.get('searches', [])
    evidence = packet.get('evidence', [])
    require(all(isinstance(x, list) for x in (sources, searches, evidence)), 'sources/searches/evidence arrays required')
    def index(items, label):
        require(all(isinstance(x, dict) and nonempty(x.get('id')) for x in items), f'{label}: IDs required')
        d = {x['id']: x for x in items}
        require(len(d) == len(items), f'duplicate {label} ID')
        return d
    sm = index(sources, 'source'); qm = index(searches, 'search'); em = index(evidence, 'evidence')
    for s in sources:
        for k in ('url', 'publisher', 'origin_group', 'origin_basis', 'event_period', 'locator', 'content', 'tool_ref'):
            require(nonempty(s.get(k)), f'source.{k} required')
        require(s['url'].startswith(('https://', 'http://')), 'source URL must be http(s)')
        timestamp(s.get('retrieved_at'))
        require('publication_date' in s, 'publication_date required; null only with explanation')
        if s['publication_date'] is None:
            require(nonempty(s.get('publication_date_note')), 'unknown publication date must be explained')
        else:
            datetime.fromisoformat(s['publication_date'])
        require(s.get('access') in {'full_text', 'excerpt', 'snippet'}, 'invalid access')
        require(s.get('independence') in {'independent', 'issuer', 'issuer_republication', 'unknown'}, 'invalid independence')
        require(s.get('content_sha256') == digest(s['content'].encode()), 'source content hash mismatch')
    for q in searches:
        for k in ('query', 'tool', 'tool_ref', 'outcome_note'):
            require(nonempty(q.get(k)), f'search.{k} required')
        timestamp(q.get('searched_at'))
        require(q.get('direction') in {'support', 'contradiction'}, 'invalid search direction')
        require(q.get('status') in {'completed', 'blocked'}, 'invalid search status')
        require(isinstance(q.get('source_ids'), list), 'search source_ids required')
        require(set(q['source_ids']) <= sm.keys(), 'unknown search source')
        require(q['status'] != 'blocked' or not q['source_ids'], 'blocked search cannot return sources')
    require(all(any(s['id'] in q['source_ids'] for q in searches) for s in sources), 'source has no search provenance')
    directions = {q['direction'] for q in searches if q['status'] == 'completed'}
    if state == 'complete':
        require(directions == {'support', 'contradiction'}, 'completed research requires both directions')
    required = plan.get('required_risk_categories', [])
    if required or 'risk_checks' in packet:
        expected = set(required or RISK_CATEGORIES)
        checks = packet.get('risk_checks')
        require(isinstance(checks, list) and all(isinstance(c, dict) for c in checks),
                'risk_checks required: Rosprirodnadzor, Rostechnadzor, courts and media incidents')
        require(len(checks) == len(expected) and {c.get('category') for c in checks} == expected,
                'each required risk category must be checked exactly once')
        for check in checks:
            for key in ('finding', 'entity_scope', 'period_scope'):
                require(nonempty(check.get(key)), f'risk check {key} required')
            indexes = check.get('search_indexes')
            require(isinstance(indexes, list) and (indexes or state != 'complete')
                    and all(type(i) is int and 0 <= i < len(searches) for i in indexes)
                    and len(indexes) == len(set(indexes)), 'risk check needs real search indexes')
            queries = [searches[i] for i in indexes]
            require(all(q.get('category') == check['category'] for q in queries),
                    'risk check search category mismatch')
            if state == 'complete':
                require(any(q['status'] == 'completed' for q in queries),
                        'completed research requires a completed search for each risk category')
    for e in evidence:
        require(e.get('source_id') in sm, 'unknown evidence source')
        require(nonempty(e.get('quote')) and e['quote'] in sm[e['source_id']]['content'], 'evidence quote not exact in snapshot')
        require(e.get('relation') in {'supports', 'contradicts', 'context'}, 'invalid relation')
        require(nonempty(e.get('reason')), 'evidence interpretation required')
        align = e.get('alignment', {})
        for axis in AXES:
            a = align.get(axis, {})
            require(a.get('status') in {'matched', 'not_applicable', 'mismatch', 'unknown'} and nonempty(a.get('reason')), f'alignment {axis} missing')
    def usable(eid, relation):
        e = em[eid]; s = sm[e['source_id']]
        return (e['relation'] == relation and s['access'] != 'snippet' and s['independence'] == 'independent'
                and all(e['alignment'][a]['status'] in {'matched', 'not_applicable'} for a in AXES))
    aspects = packet.get('aspects', [])
    require(isinstance(aspects, list) and aspects, 'atomic aspects required')
    index(aspects, 'aspect')
    for a in aspects:
        require(nonempty(a.get('proposition')) and nonempty(a.get('reason')), 'aspect proposition/reason required')
        require(a.get('status') in {'supported', 'contradicted', 'unresolved'}, 'invalid aspect status')
        ids = a.get('evidence_ids')
        require(isinstance(ids, list) and len(ids) == len(set(ids)) and set(ids) <= em.keys(), 'invalid evidence links')
        if a['status'] != 'unresolved':
            rel = 'supports' if a['status'] == 'supported' else 'contradicts'
            require(any(usable(eid, rel) for eid in ids), 'decisive aspect needs independent, non-snippet, aligned evidence')
            opposite = 'contradicts' if rel == 'supports' else 'supports'
            # Preserve all relevant evidence. Contradictions cannot disappear through selective aspect links.
            conflicts = [eid for eid in ids if usable(eid, opposite)]
            if conflicts:
                require(nonempty(a.get('conflict_resolution')), 'conflicting evidence requires adjudication rationale')
    used = {eid for a in aspects for eid in a['evidence_ids']}
    require(set(em) <= used, 'all evidence must be accounted for in aspects')
    verdict = packet.get('verdict')
    require(verdict in VERDICTS, 'invalid verdict')
    statuses = {a['status'] for a in aspects}
    if verdict in {'true', 'false', 'partial'}:
        require(state == 'complete', 'decisive verdict requires completed research')
        sr = packet.get('source_review', {})
        require(sr.get('status') == 'verified' and nonempty(sr.get('method')) and nonempty(sr.get('locator')), 'original claim source must be reviewed before decisive verdict')
        require(packet.get('aspect_coverage_confirmed') is True and nonempty(packet.get('aspect_coverage_reason')), 'reviewer must confirm atomic aspect coverage')
        require('unknown' not in {target['entity'].lower(), target['period'].lower(), target['boundary'].lower()}, 'unknown target scope prevents decisive verdict')
        require(statuses == {'supported'} if verdict == 'true' else statuses == {'contradicted'} if verdict == 'false' else statuses == {'supported', 'contradicted'}, 'verdict inconsistent with aspect outcomes')
    if verdict == 'insufficient_evidence':
        require(state == 'complete' and 'unresolved' in statuses, 'insufficient means both directions searched and unresolved aspects')
    if state in {'blocked', 'partial'}:
        require(verdict == 'not_verifiable', 'unfinished research uses not_verifiable plus explicit research_status')
    if verdict == 'not_due':
        require(state == 'complete' and target['assessment_object'] == 'promise_fulfillment', 'not_due only for researched fulfillment target')
        due = datetime.fromisoformat(target.get('due_date', ''))
        require(due.date() > datetime.fromisoformat(packet['checked_at'].replace('Z', '+00:00')).date(), 'deadline has passed')
        require(nonempty(target.get('deadline_basis')), 'deadline basis required')
    if target['assessment_object'] == 'promise_fulfillment' and verdict in {'true', 'false', 'partial'}:
        require(nonempty(target.get('due_date')) and nonempty(target.get('deadline_basis')), 'fulfillment deadline required')
        due = datetime.fromisoformat(target['due_date']).date()
        require(due <= datetime.fromisoformat(packet['checked_at'].replace('Z', '+00:00')).date(), 'promise not yet due; no failure verdict')
    return packet


def results(run, plan):
    latest = {}
    for path in sorted((Path(run) / 'results').glob('*.json')):
        raw = path.read_bytes()
        require(digest(raw) == path.with_suffix('.sha256').read_text(), f'changed checkpoint {path.name}')
        p = validate(json.loads(raw), plan)
        expected = f"{p['claim_id']}.r{p['revision']:06}.json"
        require(path.name == expected, 'checkpoint filename mismatch')
        latest.setdefault(p['claim_id'], []).append(p)
    out = {}
    for cid, history in latest.items():
        history.sort(key=lambda p: p['revision'])
        require([p['revision'] for p in history] == list(range(1, len(history)+1)), 'revision gap or duplicate')
        out[cid] = history[-1]
    return out


def ingest(run, response):
    with lock(run):
        plan = load(run); old = results(run, plan)
        packet = validate(read(response), plan)
        cid = packet['claim_id']
        require(packet['revision'] == old.get(cid, {}).get('revision', 0) + 1, 'revision must increment; checkpoints cannot overwrite')
        path = Path(run) / 'results' / f"{cid}.r{packet['revision']:06}.json"
        raw = encoded(packet)
        atomic(path.with_suffix('.sha256'), digest(raw).encode())
        atomic(path, raw)
        return {'accepted': cid, 'revision': packet['revision']}


def queue(run):
    plan = load(run); done = results(run, plan)
    return [{'claim_id': c['id'], 'quote': c['quote'], 'original': c['original'],
             'research_status': done.get(c['id'], {}).get('research_status', 'not_researched'),
             'next_revision': done.get(c['id'], {}).get('revision', 0)+1}
            for c in plan['claims'] if done.get(c['id'], {}).get('research_status') != 'complete']


def export(run, output, allow_partial=False):
    with lock(run):
        plan = load(run); done = results(run, plan)
        pending = [c['id'] for c in plan['claims'] if done.get(c['id'], {}).get('research_status') != 'complete']
        require(not pending or allow_partial, 'unresearched/unfinished rows; use --allow-partial for explicit draft')
        target = Path(str(output) + ('_draft' if pending else ''))
        require(not target.exists(), 'export output exists')
        rows = [{**c, 'assessment': done.get(c['id']),
                 'research_status': done.get(c['id'], {}).get('research_status', 'not_researched')}
                for c in plan['claims']]
        summary = {'schema_version': SCHEMA, 'status': 'partial' if pending else 'research_complete',
                   'total': len(rows), 'unfinished': len(pending),
                   'report_id': plan.get('report_id'), 'md_sha256': plan.get('md_sha256'),
                   'extraction_coverage_complete': plan.get('extraction_coverage_complete', False),
                   'verdict_counts': dict(Counter(r['assessment']['verdict'] if r['assessment'] else 'not_researched' for r in rows)),
                   'limitation': 'Structural/provenance checks only. Reviewer judgments of independence, alignment, aspect completeness and truth are not mechanically proven. Research completion is not factual certainty or proof of greenwashing.'}
        target.mkdir(parents=True)
        atomic(target / 'claims.json', encoded({'claims': rows}))
        atomic(target / 'summary.json', encoded(summary))
        with (target / 'claims.csv').open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f, delimiter=';'); w.writerow(['id','source_id','page','type','block','quote','research_status','verdict','reason'])
            for r in rows:
                a = r['assessment'] or {}; o = r['original']
                w.writerow([r['id'],r['source_id'],o.get('page',o.get('pdf_page','')),o.get('type',o.get('claim_type','')),o.get('block',''),r['quote'],r['research_status'],a.get('verdict','not_researched'),a.get('reason','Поиск ещё не выполнен')])
        return {'output': str(target), **summary}


def main():
    ap = argparse.ArgumentParser(description=__doc__); sub = ap.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('source'); p.add_argument('run'); p.add_argument('--prompt')
    for name in ('next','check'):
        p = sub.add_parser(name); p.add_argument('run')
    p = sub.add_parser('ingest'); p.add_argument('run'); p.add_argument('response')
    p = sub.add_parser('export'); p.add_argument('run'); p.add_argument('output'); p.add_argument('--allow-partial',action='store_true')
    args = ap.parse_args()
    try:
        if args.command == 'prepare': result = prepare(args.source,args.run,args.prompt)
        elif args.command == 'next': result = queue(args.run)
        elif args.command == 'check':
            plan = load(args.run); result = {'valid_checkpoints':len(results(args.run,plan)), 'total':len(plan['claims'])}
        elif args.command == 'ingest': result = ingest(args.run,args.response)
        else: result = export(args.run,args.output,args.allow_partial)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError, KeyError, TypeError, OSError) as e:
        print(f'ERROR: {e}',file=sys.stderr); return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
