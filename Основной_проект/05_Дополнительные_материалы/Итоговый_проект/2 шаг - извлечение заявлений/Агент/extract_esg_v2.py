"""Evidence/coverage contract for semantic ESG extraction; never classifies by keywords."""
import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from extract_claims import source, norm, TYPES

VERSION = 'esg-extraction-2.0'
HEADERS = ['№', 'ID', 'Заявление', 'Тип', 'Основная ESG', 'Дополнительные ESG', 'Компания', 'Год', 'Страницы', 'Статус']


def inventory(report):
    sha, pages = source(report)
    blocks = []
    for page, text in pages.items():
        chunks = list(re.finditer(r'\S(?:.*?\S)?(?=\n\s*\n|\Z)', text, re.S))
        for index, match in enumerate(chunks, 1):
            blocks.append({'id': f'p{page:04d}-b{index:04d}', 'page': page,
                           'start': match.start(), 'end': match.end(), 'text': match.group()})
        if not chunks:
            blocks.append({'id': f'p{page:04d}-b0000', 'page': page, 'start': 0, 'end': 0, 'text': ''})
    return sha, blocks


def prepare(report, company, year):
    sha, blocks = inventory(report)
    return {'schema_version': VERSION, 'source_sha256': sha, 'company': company, 'year': year,
            'claims': [], 'coverage': [{'block_id': b['id'], 'status': 'pending', 'reason': 'Не прочитан', 'claim_ids': []} for b in blocks],
            'second_pass': {'status': 'pending', 'reviewer': '', 'notes': ''}}, blocks


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate(report, data):
    sha, blocks = inventory(report)
    by_id = {b['id']: b for b in blocks}
    require(isinstance(data, dict) and data.get('schema_version') == VERSION, 'Неверная версия схемы')
    require(data.get('source_sha256') == sha, 'Хеш исходника не совпадает')
    require(nonempty(data.get('company')) and type(data.get('year')) is int, 'Нужны компания и год')
    claims = data.get('claims')
    require(isinstance(claims, list), 'claims должен быть списком')
    ids, evidence_blocks = set(), {}
    for c in claims:
        require(isinstance(c, dict), 'Заявление должно быть объектом')
        cid = c.get('id')
        require(nonempty(cid) and cid not in ids, 'Неверный или повторный ID заявления')
        ids.add(cid)
        require(c.get('type') in TYPES and nonempty(c.get('type_reason')), f'{cid}: неверный тип или нет основания')
        require(c.get('status') in ('reviewed', 'pending'), f'{cid}: неверный статус')
        primary, secondary = c.get('primary_topic'), c.get('secondary_topics')
        require(primary in ('E', 'S', 'G') or (primary is None and c['status'] == 'pending'), f'{cid}: неверная основная тема')
        require(isinstance(secondary, list) and all(x in ('E', 'S', 'G') for x in secondary), f'{cid}: неверные дополнительные темы')
        require(len(set(secondary)) == len(secondary) and primary not in secondary, f'{cid}: повтор темы')
        require(nonempty(c.get('topic_reason')) and nonempty(c.get('subtopic')), f'{cid}: нет основания/подтемы')
        require(nonempty(c.get('statement')), f'{cid}: пустое заявление')
        require(c.get('source_kind') in ('text', 'table', 'chart'), f'{cid}: неверный источник')
        evidence = c.get('evidence')
        require(isinstance(evidence, list) and evidence, f'{cid}: нет доказательств')
        used = set()
        for e in evidence:
            require(isinstance(e, dict) and e.get('block_id') in by_id, f'{cid}: неизвестный блок')
            b = by_id[e['block_id']]
            require(nonempty(e.get('quote')) and norm(e['quote']) in norm(b['text']), f'{cid}: цитата отсутствует')
            require(e.get('role') in ('statement', 'subject', 'metric', 'value', 'unit', 'period', 'context'), f'{cid}: неверная роль цитаты')
            used.add(b['id'])
        require(type(c.get('quantitative', False)) is bool, f'{cid}: quantitative должен быть boolean')
        if c['source_kind'] in ('text', 'table') and not c.get('quantitative', False):
            require(any(e['role'] == 'statement' for e in evidence), f'{cid}: нет цитаты заявления')
            require(norm(c['statement']) == norm(' '.join(e['quote'] for e in evidence if e['role'] == 'statement')), f'{cid}: текст заявления не совпадает с цитатами')
        else:
            roles = {e['role'] for e in evidence}
            require({'subject', 'metric', 'value', 'unit', 'period'} <= roles, f'{cid}: неполный контекст показателя')
        if c['source_kind'] == 'chart':
            require(c['status'] == 'pending', f'{cid}: график требует отдельной визуальной проверки; MD-валидатор не подтверждает изображение')
        if c['status'] == 'pending':
            require(nonempty(c.get('review_reason')), f'{cid}: нет причины проверки')
        evidence_blocks[cid] = used
    coverage = data.get('coverage')
    require(isinstance(coverage, list), 'Нет реестра охвата')
    covered = set()
    for entry in coverage:
        require(isinstance(entry, dict), 'Неверная запись охвата')
        bid = entry.get('block_id')
        require(bid in by_id and bid not in covered, 'Неизвестный или повторный блок охвата')
        covered.add(bid)
        require(entry.get('status') in ('extracted', 'excluded', 'pending') and nonempty(entry.get('reason')), f'{bid}: неверный статус/причина')
        refs = entry.get('claim_ids')
        require(isinstance(refs, list) and all(isinstance(x, str) and x in ids for x in refs) and len(set(refs)) == len(refs), f'{bid}: неверные ссылки')
        require(all(bid in evidence_blocks[x] for x in refs), f'{bid}: заявление не использует блок')
        require((entry['status'] != 'extracted' or bool(refs)) and (entry['status'] != 'excluded' or not refs), f'{bid}: противоречие статуса и ссылок')
    require(covered == set(by_id), 'Пропущены блоки в реестре охвата')
    for cid, bids in evidence_blocks.items():
        require(all(any(e['block_id'] == bid and cid in e['claim_ids'] for e in coverage) for bid in bids), f'{cid}: нет обратной ссылки в охвате')
    second = data.get('second_pass')
    require(isinstance(second, dict) and second.get('status') in ('pending', 'completed'), 'Неверный второй проход')
    if second['status'] == 'completed':
        require(nonempty(second.get('reviewer')) and nonempty(second.get('notes')), 'Нет свидетельства второго прохода')
    pending = sum(e['status'] == 'pending' for e in coverage)
    return {'schema_version': VERSION, 'claims': len(claims), 'blocks': len(blocks), 'pending_blocks': pending,
            'pending_claims': sum(c['status'] == 'pending' for c in claims),
            'second_pass': second['status'], 'evidence_check': 'quotes matched in MD',
            'semantic_accuracy': 'not measured', 'recall': 'not measured',
            'coverage_scope': 'MD paragraph blocks only; PDF/image completeness not established'}


def export(report, data, directory):
    stats = validate(report, data)
    _, blocks = inventory(report)
    order = {b['id']: i for i, b in enumerate(blocks)}
    pages = {b['id']: b['page'] for b in blocks}
    claims = sorted(data['claims'], key=lambda c: min(order[e['block_id']] for e in c['evidence']))
    rows = [[i, c['id'], c['statement'], c['type'], c['primary_topic'] or 'Не определено', ', '.join(c['secondary_topics']), data['company'], data['year'], ', '.join(map(str, sorted({pages[e['block_id']] for e in c['evidence']}))), c['status']] for i, c in enumerate(claims, 1)]
    out = Path(directory)
    out.mkdir(exist_ok=False, parents=True)
    views = {'registry': rows}
    for topic in ('E', 'S', 'G'):
        views['primary_' + topic] = [row for row in rows if row[4] == topic]
    views['primary_unresolved'] = [row for row in rows if row[4] == 'Не определено']
    for name, selected in views.items():
        with (out / (name + '.csv')).open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, delimiter=';'); writer.writerow(HEADERS); writer.writerows(selected)
        with (out / (name + '.csv')).open(encoding='utf-8-sig', newline='') as f:
            require(list(csv.reader(f, delimiter=';')) == [HEADERS] + [[str(v) for v in r] for r in selected], 'Ошибка перечитывания CSV')
    summary = {'unique_claims': len(claims),
               'primary_counts': {t: sum(c['primary_topic'] == t for c in claims) for t in ('E', 'S', 'G')},
               'primary_unresolved': sum(c['primary_topic'] is None for c in claims),
               'secondary_label_counts': {t: sum(t in c['secondary_topics'] for c in claims) for t in ('E', 'S', 'G')},
               'types': dict(Counter(c['type'] for c in claims)),
               'counting_rule': 'Primary views partition unique claim IDs. Secondary labels overlap and must not be added to unique_claims.'}
    require(sum(summary['primary_counts'].values()) + summary['primary_unresolved'] == len(claims), 'Ошибка суммы тем')
    for name, obj in [('registry.json', data), ('table.json', {'headers': HEADERS, 'rows': rows}), ('validation.json', stats), ('summary.json', summary)]:
        (out / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return stats


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare', 'validate', 'export'])
    p.add_argument('--report', required=True); p.add_argument('--claims'); p.add_argument('--output')
    p.add_argument('--company'); p.add_argument('--year', type=int)
    args = p.parse_args()
    try:
        if args.command == 'prepare':
            require(nonempty(args.company) and args.year is not None and args.output, 'Нужны --company --year --output')
            data, blocks = prepare(args.report, args.company, args.year)
            out = Path(args.output); out.mkdir(exist_ok=False, parents=True)
            for name, obj in [('claims.template.json', data), ('blocks.json', blocks)]:
                (out / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print(json.dumps({'blocks': len(blocks), 'output': str(out)}, ensure_ascii=False)); return 0
        require(args.claims, 'Нужен --claims')
        data = json.loads(Path(args.claims).read_text(encoding='utf-8-sig'))
        result = validate(args.report, data) if args.command == 'validate' else export(args.report, data, args.output)
        print(json.dumps(result, ensure_ascii=False)); return 0
    except (ValueError, TypeError, OSError, KeyError) as exc:
        print(f'ОШИБКА: {exc}'); return 2


if __name__ == '__main__':
    raise SystemExit(main())
