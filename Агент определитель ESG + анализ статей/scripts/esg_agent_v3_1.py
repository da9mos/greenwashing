"""Decision-trace profile 3.1 over the unchanged v3 extraction contract.

Rule citations document a model's declared decision; they do not prove semantic correctness.
"""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
import esg_agent_v3 as base

ROOT = base.ROOT
PROFILE = '3.1'
TRACE_FIELDS = ['inclusion_rule', 'classification_rule', 'subject', 'proposition',
                'esg_object', 'classification_status', 'source_refs', 'secondary_blocks', 'ambiguity_note']


def load_policy(path):
    policy = base.read(path)
    base.require(isinstance(policy, dict) and policy.get('version') == PROFILE, 'Неверная версия decision policy')
    for key in ('sources', 'inclusion_rules', 'classification_rules', 'exclusion_rules'):
        base.require(isinstance(policy.get(key), dict) and policy[key], f'Нет {key} в policy')
        base.require(all(base.text(k) and isinstance(v, dict) for k, v in policy[key].items()), f'Неверный справочник {key}')
    for key, rule in policy['classification_rules'].items():
        refs = rule.get('source_refs')
        base.require(rule.get('block') in base.TOPICS, f'{key}: неверный block')
        base.require(isinstance(refs, list) and refs and all(isinstance(r, str) and r in policy['sources'] for r in refs), f'{key}: неверные ссылки policy')
    return policy


def prepare(source, output, report_id, prompt=ROOT/'agent/esg_agent_v3_1.md',
            taxonomy=ROOT/'agent/taxonomy_v3_1.csv',
            decision_rules=ROOT/'agent/decision_rules_v3_1.json', pages_per_batch=4):
    path = Path(decision_rules).resolve()
    load_policy(path)  # Fail before creating the workspace if policy is absent/malformed.
    digest = base.sha(path)
    manifest = base.prepare(source, output, report_id, prompt, taxonomy, pages_per_batch)
    manifest.update(decision_profile_version=PROFILE, decision_rules_path=str(path), decision_rules_sha256=digest)
    base.write(Path(output)/'manifest.json', manifest)
    (Path(output)/'manifest.sha256').write_text(base.sha(Path(output)/'manifest.json'), encoding='ascii')
    return manifest


def policy_for(work):
    manifest, _ = base.workspace(work)
    base.require(manifest.get('decision_profile_version') == PROFILE, 'Workspace не подготовлен профилем 3.1')
    path = manifest.get('decision_rules_path')
    base.require(isinstance(path, str) and base.sha(path) == manifest.get('decision_rules_sha256'), 'Decision policy изменена')
    return load_policy(path)


def check(work, response):
    policy = policy_for(work)
    data, stats = base.check(work, response)
    pending = 0
    for claim in data['claims']:
        cid = claim['id']
        decision = claim.get('decision')
        base.require(isinstance(decision, dict), f'{cid}: нет decision')
        inclusion = decision.get('inclusion_rule')
        classification = decision.get('classification_rule')
        base.require(isinstance(inclusion, str) and inclusion in policy['inclusion_rules'], f'{cid}: неизвестное inclusion_rule')
        base.require(isinstance(classification, str) and classification in policy['classification_rules'], f'{cid}: неизвестное classification_rule')
        rule = policy['classification_rules'][classification]
        base.require(rule['block'] == claim['block'], f'{cid}: правило относится к другому ESG-блоку')
        for field in ('subject', 'proposition', 'esg_object'):
            base.require(base.text(decision.get(field)), f'{cid}: пустое {field}')
        refs = decision.get('source_refs')
        base.require(isinstance(refs, list) and all(isinstance(r, str) and r in policy['sources'] for r in refs), f'{cid}: неизвестный source_ref')
        base.require(len(refs) == len(set(refs)) and set(rule['source_refs']) <= set(refs), f'{cid}: отсутствуют ссылки правила или есть повторы')
        secondary = decision.get('secondary_blocks')
        base.require(isinstance(secondary, list) and all(isinstance(b, str) and b in base.TOPICS for b in secondary), f'{cid}: неверные secondary_blocks')
        base.require(len(secondary) == len(set(secondary)) and claim['block'] not in secondary, f'{cid}: повтор основной/дополнительной темы')
        base.require(claim['block2'] == (secondary[0] if secondary else ''), f'{cid}: block2 не соответствует secondary_blocks')
        status = decision.get('classification_status')
        base.require(status in ('resolved', 'pending'), f'{cid}: неверный classification_status')
        base.require(isinstance(decision.get('ambiguity_note'), str), f'{cid}: ambiguity_note должен быть строкой')
        if status == 'pending':
            base.require(base.text(decision['ambiguity_note']), f'{cid}: у pending нет объяснения')
            pending += 1
    for entry in data['coverage']:
        if entry['status'] == 'excluded':
            rule = entry.get('exclusion_rule')
            base.require(isinstance(rule, str) and rule in policy['exclusion_rules'], f"{entry['block_id']}: нет допустимого exclusion_rule")
    stats.update(pending_classifications=pending, decision_profile_version=PROFILE,
                 decision_trace='Declared model reasoning and rule references; not independently verified semantic correctness.')
    return data, stats


def export(work, responses, output, allow_partial=False):
    responses = list(responses)
    pending = 0
    for response in responses:
        _, stats = check(work, response)
        pending += stats['pending_classifications']
    base.require(not pending or allow_partial, 'Есть pending classification; нужен --allow-partial')
    out, summary = base.export(work, responses, output, allow_partial=allow_partial)
    data = base.read(out/'claims.json')
    decisions = {claim['id']: claim['decision'] for claim in data['claims']}
    # Expand only this newly-created export, preserving all original columns and evidence JSON.
    for name in ('claims.csv', 'E.csv', 'S.csv', 'G.csv'):
        with (out/name).open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f, delimiter=';')
            fields = list(reader.fieldnames)
            rows = list(reader)
        for row in rows:
            decision = decisions[row['id']]
            row.update({field: ','.join(decision[field]) if field in ('source_refs', 'secondary_blocks') else decision[field] for field in TRACE_FIELDS})
        base.csv_write(out/name, rows, fields + TRACE_FIELDS)
    # Keep exclusion provenance readable without requiring JSON inspection.
    with (out/'coverage.csv').open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter=';'); fields = list(reader.fieldnames); rows = list(reader)
    exclusions = {entry['block_id']: entry.get('exclusion_rule', '') for entry in data['coverage']}
    for row in rows:
        row['exclusion_rule'] = exclusions[row['block_id']]
    base.csv_write(out/'coverage.csv', rows, fields + ['exclusion_rule'])
    summary['legacy_block2_counts'] = summary['secondary_counts']
    summary['secondary_counts'] = {topic: sum(topic in claim['decision']['secondary_blocks'] for claim in data['claims']) for topic in base.TOPICS}
    summary.update(decision_profile_version=PROFILE, pending_classifications=pending,
                   decision_trace='Declared model reasoning and rule references; not independently verified semantic correctness.')
    base.write(out/'summary.json', summary)
    return out, summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('prepare'); a.add_argument('source'); a.add_argument('--out', required=True); a.add_argument('--report-id', required=True)
    a.add_argument('--prompt', default=ROOT/'agent/esg_agent_v3_1.md'); a.add_argument('--taxonomy', default=ROOT/'agent/taxonomy_v3_1.csv')
    a.add_argument('--decision-rules', default=ROOT/'agent/decision_rules_v3_1.json'); a.add_argument('--pages-per-batch', type=int, default=4)
    a = sub.add_parser('check'); a.add_argument('--work', required=True); a.add_argument('response')
    a = sub.add_parser('export'); a.add_argument('--work', required=True); a.add_argument('--responses', nargs='+', required=True); a.add_argument('--out', required=True); a.add_argument('--allow-partial', action='store_true')
    args = p.parse_args()
    try:
        if args.command == 'prepare':
            result = prepare(args.source, args.out, args.report_id, args.prompt, args.taxonomy, args.decision_rules, args.pages_per_batch)
        elif args.command == 'check':
            _, result = check(args.work, args.response)
        else:
            out, result = export(args.work, args.responses, args.out, args.allow_partial); result['output'] = str(out)
        print(base.json.dumps(result, ensure_ascii=False)); return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f'ОШИБКА: {exc}'); return 2


if __name__ == '__main__':
    raise SystemExit(main())
