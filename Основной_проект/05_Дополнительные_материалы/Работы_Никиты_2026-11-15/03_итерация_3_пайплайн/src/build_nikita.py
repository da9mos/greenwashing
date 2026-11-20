"""Build Nikita's evidence-linked tables from retained, immutable model answers.

No model/API/network calls. Original claims, company/report registries and llm
answers are read-only. A different --output-root allows independent rebuilds.
"""
from __future__ import annotations
import argparse
import ast
import copy
import csv
import hashlib
import io
import json
import re
import subprocess
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]
DYNAMICS_FIELDS = ['target_id','company_id','claim_id_commitment','esg_block','topic','metric','unit','base_year','base_value','target_value','target_year','value_2023','page_2023','value_2024','page_2024','value_2025','page_2025','restated','status','comment']
TARGET_FIELDS = ['target_id','company_id','claim_id_commitment','esg_block','topic','metric','unit','base_year','base_value','target_value','target_year','direction','report_id','page','quote','source_url','status','comment']
EVIDENCE_FIELDS = ['target_id','company_id','kind','year','report_id','page','value','quote','source_url','quote_check','reported_value_unparsed','comment']
REVIEW_FIELDS = ['company_id','company','reporting_quality','assessment_requested','reports_available','years_available','reports_checked','all_reports_checked','esg_table_two_years','numeric_deadline_goal','target_count','expired_target_count','future_target_count','limitations','evidence_refs']
QUOTA_FIELDS = ['company_id','reporting_quality','weight','available_claims','quota','scope']


def norm(value):
    return ' '.join(str(value or '').split())


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter=';')
        return list(reader), list(reader.fieldnames or [])


def csv_bytes(rows, fields):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, delimiter=';', lineterminator='\n', extrasaction='raise')
    writer.writeheader()
    for row in rows:
        writer.writerow({key: '' if row.get(key) is None else row.get(key, '') for key in fields})
    return stream.getvalue().encode('utf-8-sig')


def number(value):
    if value is None or isinstance(value, bool) or str(value).strip() == '':
        return None
    text = str(value).replace('\u2212', '-').replace('\u00a0', '').replace('\u202f', '').replace(' ', '').replace(',', '.')
    try:
        result = Decimal(text)
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def has_number(value, quote):
    expected = number(value)
    if expected is None:
        return False
    # Preserve punctuation and words for quote validation; this tokenizer only
    # normalizes written numbers, including Russian thousands/decimal marks.
    clean = str(quote).replace('\u00a0', ' ').replace('\u202f', ' ').replace('\u2212', '-')
    if expected == 0 and re.search(r'\b(?:ноль|нул[яюём]|нулев[а-яё]*)\b', clean, flags=re.I):
        return True
    if expected == 2 and re.search(r'\b(?:два|две|двух|двумя)\b', clean, flags=re.I):
        return True
    for match in re.finditer(r'(-?\d+(?:[.,]\d+)?)\s*(тыс\.?|млн\.?|млрд\.?)', clean, flags=re.I):
        scale = Decimal(1000 if match[2].lower().startswith('тыс') else 1000000 if match[2].lower().startswith('млн') else 1000000000)
        if number(match[1]) * scale == expected:
            return True
    tokens = re.findall(r'(?<!\w)-?\d+(?:[ ]\d{3})*(?:[.,]\d+)?', clean)
    return any(number(token) == expected for token in tokens)


def verify_calculation(calculation, expected, quotes):
    """Whitelist arithmetic; every nontrivial operand must be in cited evidence."""
    text = str(calculation or '').split('=', 1)[0].replace('×','*').replace('−','-').replace(',', '.')
    text = ''.join(text.split())
    if not text or len(text)>160 or not re.fullmatch(r'[0-9.()+*/-]+', text):
        return False
    try:
        root = ast.parse(text, mode='eval')
        def calculate(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int,float)):
                value = Decimal(ast.get_source_segment(text,node))
                if value not in {Decimal(1), Decimal(100)} and not has_number(value, quotes):
                    percent = value * 100
                    percent_text = format(percent, 'f').rstrip('0').rstrip('.') if '.' in format(percent,'f') else str(percent)
                    if not (Decimal(0)<value<Decimal(1) and re.search(r'(?<!\d)'+re.escape(percent_text)+r'\s*%', quotes)):
                        raise ValueError('operand lacks evidence')
                return value
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub,ast.UAdd)):
                val=calculate(node.operand)
                return -val if isinstance(node.op,ast.USub)else val
            if isinstance(node, ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub,ast.Mult,ast.Div)):
                a,b=calculate(node.left),calculate(node.right)
                if isinstance(node.op,ast.Add):return a+b
                if isinstance(node.op,ast.Sub):return a-b
                if isinstance(node.op,ast.Mult):return a*b
                return a/b
            raise ValueError('unsupported calculation')
        return calculate(root.body)==number(expected)
    except (ValueError,SyntaxError,InvalidOperation,ZeroDivisionError):
        return False


class EvidenceStore:
    def __init__(self, pages_dir, reports):
        self.pages_dir = Path(pages_dir)
        self.reports = {row['report_id']: row for row in reports}
        self.cache = {}

    def verify(self, evidence, company_id):
        if not isinstance(evidence, dict):
            raise ValueError('evidence must be an object')
        report_id = evidence.get('report_id', '')
        report = self.reports.get(report_id)
        if report is None or report['company_id'] != company_id:
            raise ValueError(f'report/company mismatch: {company_id}, {report_id}')
        try:
            page = int(evidence['page'])
        except (KeyError, ValueError, TypeError):
            raise ValueError(f'invalid page: {report_id}')
        if report_id not in self.cache:
            records = {}
            with (self.pages_dir / (report_id + '.jsonl')).open(encoding='utf-8-sig') as f:
                for line in f:
                    item = json.loads(line)
                    if item.get('report_id') != report_id:
                        raise ValueError(f'page metadata report mismatch: {report_id}')
                    records[int(item['page'])] = item['text']
            self.cache[report_id] = records
        quote = str(evidence.get('quote') or '')
        if len(norm(quote)) < 8:
            raise ValueError(f'empty/too short quote: {report_id}:{page}')
        if page not in self.cache[report_id] or norm(quote) not in norm(self.cache[report_id][page]):
            raise ValueError(f'quote not on stated page: {report_id}:{page}')
        url = evidence.get('source_url') or evidence.get('url')
        drive_id = report.get('drive_id', '')
        canonical_url = f'https://drive.google.com/file/d/{drive_id}/view' if drive_id else ''
        if url and canonical_url and str(url).startswith('https://drive.google.com/') and drive_id not in str(url):
            raise ValueError(f'source URL disagrees with registry: {report_id}')
        return {'report_id': report_id, 'page': page, 'quote': quote,
                'source_url': canonical_url or str(url or ''), 'report_year': int(report['year'])}


def allocate_quotas(capacities, qualities, total=500):
    """Capacity-capped proportional allocation with exact, stable remainders."""
    codes = sorted(capacities)
    if total < len(codes) or total > sum(capacities.values()) or any(capacities[c] < 1 for c in codes):
        raise ValueError('quota is infeasible for company capacities')
    weights = {c: Fraction('0.5' if qualities.get(c) == 'слабая' else '1' if qualities.get(c) == 'обычная' else '0.75') for c in codes}
    quotas = {c: 1 for c in codes}
    remaining = total - len(codes)
    while remaining:
        active = [c for c in codes if quotas[c] < capacities[c]]
        weight_sum = sum(weights[c] for c in active)
        ideals = {c: Fraction(remaining) * weights[c] / weight_sum for c in active}
        awards = {c: min(capacities[c] - quotas[c], ideals[c].numerator // ideals[c].denominator) for c in active}
        for c in active:
            quotas[c] += awards[c]
            remaining -= awards[c]
        if not remaining:
            break
        ranking = sorted((c for c in active if quotas[c] < capacities[c]), key=lambda c: (-(ideals[c] - int(ideals[c])), c))
        if not ranking:
            continue
        for c in ranking:
            if not remaining:
                break
            quotas[c] += 1
            remaining -= 1
    return quotas


def assign_claim_id(company_id, year, existing_ids):
    prefix = f'{company_id}-{year}-'
    suffixes = [int(cid[len(prefix):]) for cid in existing_ids if cid.startswith(prefix) and cid[len(prefix):].isdigit()]
    candidate = max(suffixes, default=0) + 1
    result = prefix + f'{candidate:03d}'
    if result in existing_ids:
        raise ValueError('claim ID collision')
    existing_ids.add(result)
    return result


def derive_status(target, observations, cutoff=2025):
    year = int(target['target_year'])
    if year > cutoff:
        return 'срок не наступил'
    if target.get('comparison_valid') is False:
        return 'нет данных'
    actual = next((number(x.get('value')) for x in observations if int(x['year']) == year and x.get('comparison_valid') is not False), None)
    goal = number(target.get('target_value'))
    if actual is None and target.get('completion_by_deadline') is True:
        for obs in observations:
            if int(obs['year']) < year and obs.get('comparison_valid') is not False and number(obs.get('value')) is not None:
                result = derive_status(dict(target, target_year=int(obs['year']), completion_by_deadline=False), [obs], cutoff)
                if result == 'выполнена':
                    return result
    if actual is None or goal is None:
        return 'нет данных'
    direction = str(target.get('comparison_operator', target.get('target_operator', target.get('operator', target.get('direction', ''))))).lower().strip()
    if direction in {'>', 'more', 'более', 'свыше', 'строго больше'}:
        return 'выполнена' if actual > goal else 'не выполнена'
    if direction in {'<', 'less', 'менее', 'ниже', 'строго меньше'}:
        return 'выполнена' if actual < goal else 'не выполнена'
    if direction in {'down', 'decrease', 'lower', 'снижение', 'меньше', 'не более', '<=', '≤'}:
        return 'выполнена' if actual <= goal else 'не выполнена'
    if direction in {'up', 'increase', 'higher', 'рост', 'больше', 'не менее', '>=', '≥'}:
        return 'выполнена' if actual >= goal else 'не выполнена'
    if direction in {'exact', '=', 'равно'}:
        return 'выполнена' if actual == goal else 'не выполнена'
    return 'нет данных'


def evidence_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def build(pipeline, repo, input_paths):
    pipeline, repo = Path(pipeline), Path(repo)
    companies, _ = read_csv(repo / '01_итерация_1_сбор_данных/выборка_30/companies.csv')
    reports, _ = read_csv(repo / '01_итерация_1_сбор_данных/выборка_30/reports.csv')
    claims, claim_fields = read_csv(pipeline / 'data/out/claims.csv')
    known_companies = {c['company_id']: c for c in companies}
    by_company = defaultdict(list)
    for report in reports:
        by_company[report['company_id']].append(report)
    store = EvidenceStore(pipeline / 'data/pages', reports)
    reviews = []
    model_provenance = {}
    inputs = {}
    input_counts = {}
    for path in sorted(map(Path, input_paths)):
        raw = path.read_bytes()
        payload = json.loads(raw.decode('utf-8-sig'))
        records = payload.get('company_reviews', payload.get('companies', []))
        if not isinstance(records, list):
            raise ValueError(f'company_reviews must be a list: {path}')
        for record in records:
            model_provenance[record['company_id']] = payload.get('model_provenance', 'Codex; exact model not exported')
        reviews.extend(records)
        input_name = str(path.relative_to(pipeline)) if path.is_relative_to(pipeline) else str(path)
        inputs[input_name] = hashlib.sha256(raw).hexdigest()
        input_counts[input_name] = sum(len(record.get('targets', [])) for record in records)
    codes = [x['company_id'] for x in reviews]
    if len(codes) != len(set(codes)) or set(codes) != set(known_companies):
        raise ValueError(f'review coverage mismatch: missing={sorted(set(known_companies)-set(codes))}, duplicated/unknown={sorted(c for c in codes if codes.count(c)>1 or c not in known_companies)}')
    diagnostics, warnings = [], []
    tables = {'targets.csv': [], 'metrics_dynamics.csv': [], 'claims_dynamics_additions.csv': [], 'companies_review.csv': [], 'dynamics_evidence.csv': [], 'future_targets.csv': []}
    ids = {r['claim_id'] for r in claims}
    all_target_ids = set()
    override_path = pipeline/'data/nikita/overrides_v2.json'
    if not override_path.exists():
        override_path = pipeline/'data/nikita/overrides_v1.json'
    overrides = json.loads(override_path.read_text()).get('targets',{}) if override_path.exists() else {}
    for company in sorted(reviews, key=lambda x: x['company_id']):
        code = company['company_id']
        available = {r['report_id'] for r in by_company[code]}
        checked = set(company.get('report_ids_checked', []))
        if checked - available:
            diagnostics.append({'company_id': code, 'error': 'unknown checked report IDs', 'ids': sorted(checked - available)})
        quality = company.get('reporting_quality', {})
        if not isinstance(quality, dict):
            quality = {'classification': quality}
        evidence_refs = []
        quality_good = True
        for aspect in ['esg_table_two_years', 'numeric_deadline_goal']:
            spec = quality.get(aspect, {})
            if not isinstance(spec, dict):
                spec = {'found': spec}
            for ev in evidence_list(spec.get('evidence')):
                try:
                    verified = store.verify(ev, code)
                    evidence_refs.append(f"{verified['report_id']}:{verified['page']}")
                    tables['dynamics_evidence.csv'].append(dict(target_id='', company_id=code, kind=aspect, year='', value='', quote_check='exact_whitespace_normalized', **{k: verified[k] for k in ['report_id','page','quote','source_url']}))
                except (ValueError, OSError, KeyError) as exc:
                    quality_good = False
                    diagnostics.append({'company_id': code, 'aspect': aspect, 'error': str(exc)})
            if spec.get('found') is True and not evidence_list(spec.get('evidence')):
                quality_good = False
                warnings.append({'company_id': code, 'warning': f'{aspect}: positive assessment has no retained quote'})
        requested_quality = quality.get('classification', company.get('weak_reporting', 'неопределена'))
        full_checked = bool(available) and checked == available
        table_found = quality.get('esg_table_two_years', {}).get('found') if isinstance(quality.get('esg_table_two_years'), dict) else None
        goal_found = quality.get('numeric_deadline_goal', {}).get('found') if isinstance(quality.get('numeric_deadline_goal'), dict) else None
        assessment = requested_quality if requested_quality in {'обычная','слабая','неопределена'} else 'неопределена'
        if not quality_good or not full_checked or (assessment == 'обычная' and (table_found is not True or goal_found is not True)):
            assessment = 'неопределена'
        counts = Counter()
        for index, target in enumerate(company.get('targets', []), 1):
            tid = target.get('target_id') or f'T-{code}-{index:03d}'
            if tid in all_target_ids:
                diagnostics.append({'company_id': code, 'target_id': tid, 'error': 'duplicate target_id'})
                continue
            all_target_ids.add(tid)
            try:
                target = copy.deepcopy(target)
                override = overrides.get(tid,{})
                for key,value in override.get('set',{}).items():
                    target[key]=value
                for key in override.get('skip_fields',[]):
                    target.pop(key,None)
                commitment = store.verify(target.get('target_evidence', target.get('commitment')), code)
                if commitment['report_year'] != 2023:
                    raise ValueError('primary commitment must come from a 2023 report')
                target_year = int(target['target_year'])
                if number(target.get('target_value')) is None or target.get('esg_block') not in {'E','S','G'}:
                    raise ValueError('numeric target or ESG block missing/invalid')
                target_proofs = [commitment]
                records = []
                for kind in ['deadline_evidence','source_scope_evidence','supporting_evidence','base_evidence','target_quantity_evidence']:
                    for ev in evidence_list(target.get(kind)):
                        verified = store.verify(ev, code)
                        target_proofs.append(verified)
                        records.append((kind, verified, ev.get('year', ''), ev.get('value', '')))
                all_quotes = ' '.join(x['quote'] for x in target_proofs)
                if not has_number(target['target_value'], all_quotes) and not verify_calculation(target.get('calculation'),target['target_value'],all_quotes):
                    raise ValueError('target value absent from verified evidence or supported arithmetic')
                if not re.search(r'(?<!\d)'+str(target_year)+r'(?!\d)',all_quotes):
                    raise ValueError('target deadline absent from verified evidence')
                if target.get('base_value') not in (None, '') and not has_number(target['base_value'], all_quotes):
                    raise ValueError('base value absent from verified evidence')
                if target.get('base_year') not in (None, '') and not has_number(target['base_year'], all_quotes):
                    raise ValueError('base year absent from verified evidence')
                observations = []
                observed_years = {}
                for obs in target.get('observations', []):
                    verified = store.verify(obs, code)
                    year = int(obs['year'])
                    if year not in {2023,2024,2025} or year > verified['report_year']:
                        raise ValueError(f'observation year/report mismatch: {year}, {verified["report_id"]}')
                    value = obs.get('value')
                    if year in observed_years and number(value) != observed_years[year]:
                        raise ValueError(f'conflicting observations for {year}; explicit restatement selection required')
                    reported = obs.get('reported_value', obs.get('raw_reported_value', value))
                    if value not in (None, '') and not has_number(value, verified['quote']):
                        raise ValueError(f'observation value absent from its quote: {year}')
                    if value not in (None, '') and number(value) is None:
                        raise ValueError(f'invalid observation value: {year}')
                    obs_unit = obs.get('unit')
                    clean_unit = lambda x: re.sub(r'[^\w%/]', '', str(x or '').lower())
                    if value not in (None, '') and obs_unit and clean_unit(obs_unit) != clean_unit(target.get('unit')):
                        raise ValueError(f'observation unit differs from target unit: {year}')
                    observed_years[year] = number(value)
                    verified['_reported_value'] = reported if value in (None, '') else ''
                    verified['_comment'] = str(obs.get('comment','')) + (' | Исходная единица: '+str(obs['raw_unit']) if obs.get('raw_unit') else '') + (' | Уточнение значения: '+str(obs['value_qualifier']) if obs.get('value_qualifier') else '')
                    observations.append(dict(obs, **verified))
                    records.append(('observation' if value not in (None, '') else 'observation_not_comparable', verified, year, value))
                matches = [c for c in claims if c['company_id'] == code and c['report_id'] == commitment['report_id'] and str(c['page']) == str(commitment['page']) and c['type'] == 'обязательство' and (norm(commitment['quote']) in norm(c['text']) or norm(c['text']) in norm(commitment['quote']))]
                explicit_claim = target.get('claim_id_commitment')
                if explicit_claim and explicit_claim not in {x['claim_id'] for x in matches}:
                    raise ValueError('provided claim_id does not match actual commitment quote/report/page')
                claim_id = explicit_claim or (sorted(matches, key=lambda x: x['claim_id'])[0]['claim_id'] if matches else '')
                # Future targets are retained for later work, not risk failures.
                status = derive_status(target, observations)
                comments = [str(target.get('comment') or '')]
                for key in ['comparison_basis','comparison_limitations','limitations','comparison_operator','target_operator','operator','calculation','restated','quantity_conversion','company_self_comparison','completion_by_deadline']:
                    if target.get(key):
                        item = target[key]
                        comments.append(key + ': ' + (item if isinstance(item,str) else json.dumps(item,ensure_ascii=False)))
                if override:
                    comments.append('QC override: '+str(override.get('reason','')))
                combined_comment = ' | '.join(x for x in comments if x)
                if target_year > 2025:
                    row = {key: target.get(key, '') for key in TARGET_FIELDS}
                    row.update(target_id=tid, company_id=code, claim_id_commitment=claim_id, report_id=commitment['report_id'], page=commitment['page'], quote=commitment['quote'], source_url=commitment['source_url'], status=status, comment=combined_comment)
                    tables['future_targets.csv'].append(row)
                    counts['future'] += 1
                else:
                    if not claim_id:
                        year = commitment['report_year']
                        claim_id = assign_claim_id(code, year, ids)
                        added = {key: '' for key in claim_fields}
                        added.update(claim_id=claim_id,company_id=code,year=str(year),report_id=commitment['report_id'],page=commitment['page'],text=commitment['quote'],type='обязательство',esg_block=target['esg_block'],topic=target.get('topic',''),metric=target.get('metric',''),value=target.get('target_value',''),unit=target.get('unit',''),base_year=target.get('base_year',''),target_year=target_year,has_number='да',has_deadline='да',prompt_version='nikita_dynamics/v1',model=model_provenance[code],source_url=commitment['source_url'],quote_check='exact_whitespace_normalized',review_status='source_quote_validated; semantic_assessment_model')
                        tables['claims_dynamics_additions.csv'].append(added)
                    row = {key: target.get(key, '') for key in TARGET_FIELDS}
                    row.update(target_id=tid,company_id=code,claim_id_commitment=claim_id,report_id=commitment['report_id'],page=commitment['page'],quote=commitment['quote'],source_url=commitment['source_url'],status=status,comment=combined_comment)
                    tables['targets.csv'].append(row)
                    dynamic = {key: target.get(key, '') for key in DYNAMICS_FIELDS}
                    dynamic.update(target_id=tid,company_id=code,claim_id_commitment=claim_id,restated=target.get('restated','не проверено'),status=status,comment=combined_comment)
                    for obs in observations:
                        dynamic[f'value_{obs["year"]}'] = (str(obs['value_qualifier'])+' '+str(obs['value'])) if obs.get('value_qualifier') in {'более','менее','не менее','не более','>','<','>=','<='} and obs.get('value') is not None else obs.get('value')
                        dynamic[f'page_{obs["year"]}'] = obs['page']
                    if target.get('status') and target['status'] != status:
                        warnings.append({'company_id':code,'target_id':tid,'warning':'model status not adopted without exact-year comparable data','model_status':target['status'],'computed_status':status})
                    tables['metrics_dynamics.csv'].append(dynamic)
                    counts['expired'] += 1
                records.insert(0, ('commitment',commitment,commitment['report_year'],target['target_value']))
                for kind, verified, year, value in records:
                    tables['dynamics_evidence.csv'].append(dict(target_id=tid,company_id=code,kind=kind,year=year,value=value,quote_check='exact_whitespace_normalized',reported_value_unparsed=verified.get('_reported_value',''),comment=verified.get('_comment',''),**{k:verified[k] for k in ['report_id','page','quote','source_url']}))
                evidence_refs.append(f"{commitment['report_id']}:{commitment['page']}")
                counts['total'] += 1
            except (ValueError, TypeError, KeyError, OSError) as exc:
                diagnostics.append({'company_id':code,'target_id':tid,'error':str(exc)})
        tables['companies_review.csv'].append(dict(company_id=code,company=known_companies[code]['company'],reporting_quality=assessment,assessment_requested=requested_quality,reports_available=len(available),years_available=','.join(sorted({r['year'] for r in by_company[code]})),reports_checked=','.join(sorted(checked)),all_reports_checked='да' if full_checked else 'нет',esg_table_two_years=table_found,numeric_deadline_goal=goal_found,target_count=counts['total'],expired_target_count=counts['expired'],future_target_count=counts['future'],limitations=json.dumps(company.get('limitations',[]),ensure_ascii=False) if not isinstance(company.get('limitations',''),str) else company.get('limitations',''),evidence_refs=' | '.join(sorted(set(evidence_refs)))))
    capacities = Counter(x['company_id'] for x in claims)
    qualities = {x['company_id']:x['reporting_quality'] for x in tables['companies_review.csv']}
    quotas = allocate_quotas(capacities,qualities,500)
    tables['sampling_quotas.csv'] = [dict(company_id=code,reporting_quality=qualities.get(code,'неопределена'),weight='0.5' if qualities.get(code)=='слабая' else '1' if qualities.get(code)=='обычная' else '0.75',available_claims=capacities[code],quota=quotas[code],scope='План выборки из 928 извлечённых заявлений; не итоговые классы истинности') for code in sorted(quotas)]
    fields = {'targets.csv':TARGET_FIELDS,'metrics_dynamics.csv':DYNAMICS_FIELDS,'claims_dynamics_additions.csv':claim_fields,'companies_review.csv':REVIEW_FIELDS,'sampling_quotas.csv':QUOTA_FIELDS,'dynamics_evidence.csv':EVIDENCE_FIELDS,'future_targets.csv':TARGET_FIELDS}
    source_paths = [repo/'01_итерация_1_сбор_данных/выборка_30/companies.csv', repo/'01_итерация_1_сбор_данных/выборка_30/reports.csv', pipeline/'data/out/claims.csv']
    source_paths.extend(pipeline/'data/pages'/f'{r["report_id"]}.jsonl' for r in reports)
    for rel in ['src/build_nikita.py','tests/test_build_nikita.py','data/nikita/overrides_v1.json','data/nikita/overrides_v2.json']:
        if (pipeline/rel).exists():
            source_paths.append(pipeline/rel)
    source_hashes = {str(path.relative_to(repo)): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
    prompt = pipeline/'prompts/nikita_dynamics_v1.md'
    prompt_hash = hashlib.sha256(prompt.read_bytes()).hexdigest() if prompt.exists() else ''
    try:
        base_head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,stderr=subprocess.DEVNULL,text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        base_head = ''
    return tables,fields,{'input_sha256':inputs,'input_counts':input_counts,'source_sha256':source_hashes,'prompt_sha256':prompt_hash,'overrides_file':str(override_path.relative_to(pipeline)) if override_path.exists() else '', 'base_head':base_head,'run_date':'2026-11-15','errors':diagnostics,'warnings':warnings,'scope':'Model-derived semantic assessment; literal quotes validated mechanically. No truth classification, no forced three targets per company.'}


def write_outputs(output_root,tables,fields,validation):
    output_root = Path(output_root)
    diagnostics_path = output_root/'data/nikita/validation.json'
    diagnostics_path.parent.mkdir(parents=True,exist_ok=True)
    if validation['errors']:
        failed_raw=(json.dumps(validation,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')
        failed_id=hashlib.sha256(failed_raw).hexdigest()[:16]
        failed_path=diagnostics_path.with_name(f'validation_errors_{failed_id}.json')
        if not failed_path.exists():
            failed_path.write_bytes(failed_raw)
        diagnostics_path.write_bytes(failed_raw)
        raise ValueError(f'{len(validation["errors"])} evidence errors; retained diagnostic: {failed_path}')
    artifacts = {}
    for name, rows in tables.items():
        directory = 'data/nikita' if name in {'dynamics_evidence.csv','future_targets.csv'} else 'data/out'
        path = output_root/directory/name
        raw = csv_bytes(rows,fields[name])
        if path.exists() and path.read_bytes() != raw:
            raise FileExistsError(f'refusing to replace a different artifact; use a fresh --output-root: {path}')
        artifacts[path]=(raw,len(rows))
    template = output_root/'templates/metrics_dynamics_шаблон.csv'
    artifacts[template]=(csv_bytes([],DYNAMICS_FIELDS),0)
    input_manifest={'source_sha256':validation.get('source_sha256',{}),'retained_answer_sha256':validation.get('input_sha256',{}),'prompt_sha256':validation.get('prompt_sha256',''),'overrides_file':validation.get('overrides_file',''),'base_head':validation.get('base_head','')}
    input_raw=(json.dumps(input_manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')
    artifacts[output_root/'data/nikita/input_manifest.json']=(input_raw,len(input_manifest['source_sha256']))
    manifest_fields=['batch_id','stage','company_id','report_id','input_file','input_sha256','prompt_file','prompt_sha256','model','thread','started_at','finished_at','status','n_items','n_rejected','checked_by','validated_at','output_file','output_sha256']
    manifest_rows=[]
    for name,sha in sorted(validation.get('input_sha256',{}).items()):
        row={key:'' for key in manifest_fields}
        row.update(batch_id='nikita_dynamics_v1_'+Path(name).stem,stage='nikita_dynamics',input_file='data/nikita/input_manifest.json',input_sha256=hashlib.sha256(input_raw).hexdigest(),prompt_file='prompts/nikita_dynamics_v1.md',prompt_sha256=validation.get('prompt_sha256',''),model='Codex (точная версия модели в экспорте не записана)',thread='Codex / '+Path(name).stem,status='validated_quotes_not_truth',n_items=validation.get('input_counts',{}).get(name,''),n_rejected=0,checked_by='build_nikita: literal page quotes + metadata + numeric evidence',validated_at=validation.get('run_date',''),output_file=name,output_sha256=sha)
        manifest_rows.append(row)
    artifacts[output_root/'runs/manifest_parts/nikita_dynamics_v1.csv']=(csv_bytes(manifest_rows,manifest_fields),len(manifest_rows))
    validation['outputs']={str(path.relative_to(output_root)):{'rows':n,'sha256':hashlib.sha256(raw).hexdigest()}for path,(raw,n)in artifacts.items()}
    build_manifest={key:validation[key] for key in ['base_head','run_date','input_sha256','source_sha256','prompt_sha256','overrides_file','outputs','scope'] if key in validation}
    artifacts[output_root/'data/nikita/build_manifest.json']=((json.dumps(build_manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8'),1)
    for path,(raw,_) in artifacts.items():
        if path.exists() and path.read_bytes()!=raw:
            raise FileExistsError(f'refusing to replace a different artifact; use a fresh --output-root: {path}')
    for path,(raw,_) in artifacts.items():
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            path.write_bytes(raw)
    diagnostics_path.write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
    return validation


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pipeline-root',type=Path,default=PIPELINE)
    parser.add_argument('--output-root',type=Path)
    parser.add_argument('--input',action='append',type=Path)
    args=parser.parse_args(argv)
    pipeline=args.pipeline_root.resolve()
    inputs=args.input or [pipeline/'llm/nikita_dynamics/v1/group_A.json',pipeline/'llm/nikita_dynamics/v1/group_B.json']
    for path in inputs:
        if not path.is_file():
            parser.error(f'missing retained answer: {path}')
    tables,fields,validation=build(pipeline,pipeline.parent,inputs)
    result=write_outputs(args.output_root or pipeline,tables,fields,validation)
    print(json.dumps({'counts':{name:len(rows)for name,rows in tables.items()},'errors':len(result['errors']),'warnings':len(result['warnings'])},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
