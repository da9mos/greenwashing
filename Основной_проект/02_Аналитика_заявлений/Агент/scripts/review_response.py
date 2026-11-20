"""Reconcile explicit structural gaps without promoting a model claim to verified."""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import re

import esg_agent_v3 as base
import esg_agent_v3_1 as profile

VISUAL = re.compile(r'!\[|<img\b|Визуальный материал:|визуальный элемент оригинала', re.I)
FIELDS = {'metric': 'metric', 'value': 'value', 'unit': 'unit', 'period': 'period', 'entity_scope': 'subject'}


def review(work, response):
    # Display quotes are validated by profile.check below. Never construct them
    # from statement fragments or expand them heuristically; legacy stays unready.
    data = base.read(response)
    manifest, _ = base.workspace(work)
    entry = next((item for item in manifest['batches'] if item['id'] == data['batch_id']), None)
    if entry is None:
        raise ValueError('Unknown batch ID')
    batch = base.read(work / entry['file'])
    blocks = {block['id']: block['text'] for block in batch['blocks']}
    missing = Counter()
    references = defaultdict(list)
    for claim in data['claims']:
        for block_id in dict.fromkeys(item['block_id'] for item in claim['evidence']):
            references[block_id].append(claim['id'])
        if claim.get('quantitative') is not True:
            continue
        for field, role in FIELDS.items():
            value = claim.get(field)
            if isinstance(value, str) and value and not any(
                ev['role'] == role and base.evidence_supports(field, value, ev['quote']) for ev in claim['evidence']
            ):
                claim[field] = ''
                claim['source_status'] = 'needs_pdf_review'
                missing[field] += 1
    reopened = 0
    for entry in data['coverage']:
        block_id = entry['block_id']
        reason = None
        if VISUAL.search(blocks[block_id]) and entry['status'] != 'pending':
            reason = 'Нужна сверка визуального материала по физической странице PDF.'
        elif entry['status'] == 'excluded' and references[block_id]:
            reason = 'Блок использован в доказательствах. Требуется проверить, содержит ли он отдельное заявление.'
        if reason:
            entry.update(status='pending', reason=reason)
            entry.pop('exclusion_rule', None)
            reopened += 1
        # Reconstruct links only to citations already present. check() verifies every quote and ID.
        entry['claim_ids'] = references[block_id]
        if entry['status'] == 'extracted' and not entry['claim_ids']:
            entry.update(status='pending', reason='Нет цитаты и ссылки на извлечённое заявление. Нужна проверка.')
            reopened += 1
        if entry['status'] == 'extracted' and any(
            claim.get('quantitative') is True and claim.get('source_status') == 'needs_pdf_review'
            and claim['id'] in entry['claim_ids'] for claim in data['claims']
        ):
            entry.update(status='pending', reason='Не закрыт числовой контекст заявления; требуется сверка PDF.')
            reopened += 1
    _, stats = profile.check(work, data)
    return data, {**stats, 'cleared_unsupported_fields': dict(missing), 'reopened_blocks': reopened}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work', type=Path)
    parser.add_argument('response', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; preserve original and use a separate revision path')
    data, stats = review(args.work, args.response)
    base.write(args.output, data)
    print(base.json.dumps(stats, ensure_ascii=False))
