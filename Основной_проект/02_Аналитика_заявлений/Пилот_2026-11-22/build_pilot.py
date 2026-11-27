"""Export the bounded, visually reviewed pilot from its annotation log."""
import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / 'Агент/scripts'))
import esg_agent_v3 as base
import esg_agent_v3_1 as profile

sys.path.insert(0, str(PROJECT / '03_Фактчекинг/Агент'))
import factcheck

FIELDS = [
    'id', 'report_id', 'physical_pdf_page', 'printed_pages', 'source_url',
    'pdf_sha256', 'quote', 'type', 'block', 'topic', 'secondary_blocks', 'subject',
    'metric', 'value', 'unit', 'period', 'classification_rule', 'source_refs',
    'source_review_method', 'pdf_context', 'review_note',
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook-data', type=Path)
    parser.add_argument('--factcheck-json', type=Path)
    args = parser.parse_args()
    with (PROJECT / '00_Отчёты/Реестр_отчётов.csv').open(encoding='utf-8-sig', newline='') as file:
        registry = {row['report_id']: row for row in csv.DictReader(file, delimiter=';')}
    policy = profile.load_policy(profile.ROOT / 'agent/decision_rules_v3_1.json')
    with (profile.ROOT / 'agent/taxonomy_v3_1.csv').open(encoding='utf-8-sig', newline='') as file:
        topics = {(row['block'], row['topic']) for row in csv.DictReader(file, delimiter=';')}

    claims, log, handoff = [], [], []
    for report in base.read(HERE / 'разметка.json'):
        source = registry[report['report']]
        page = report['page']
        url = source['pdf_source_url']
        for case in report['cases']:
            included = 'type' in case
            log.append([case['id'], source['company'], page, 'Включено' if included else 'Исключено',
                        case['quote'], case['baseline'], case['note']])
            if not included:
                continue
            rule = policy['classification_rules'][case['rule']]
            assert rule['block'] == case['block'] and (case['block'], case['topic']) in topics
            assert case['type'] in base.TYPES
            row = {field: case.get(field, '') for field in FIELDS}
            row.update(report_id=report['report'], physical_pdf_page=page, printed_pages=report['printed'],
                       source_url=url, pdf_sha256=report['pdf_sha256'],
                       classification_rule=case['rule'], source_refs=','.join(rule['source_refs']),
                       secondary_blocks='E' if case['id'] == 'L3' else '',
                       source_review_method='codex_visual_pdf_excerpt', pdf_context=case['context'],
                       review_note=case['note'])
            handoff.append(row)
            claims.append([case['id'], source['company'], page, case['block'], case['type'], case['topic'],
                           case['quote'], case['context']])
    base.require(len({row['id'] for row in handoff}) == len(handoff), 'Дубли ID')
    csv_path = HERE / 'claims_pilot.csv'
    base.csv_write(csv_path, handoff, FIELDS)
    with csv_path.open(encoding='utf-8-sig', newline='') as file:
        exported = list(csv.DictReader(file, delimiter=';'))
    with tempfile.TemporaryDirectory() as tmp:
        packet = Path(tmp) / 'claims.json'
        base.write(packet, {'claims': exported})
        run = Path(tmp) / 'factcheck'
        factcheck.prepare(packet, run)
        plan = factcheck.read(run / 'plan.json')
        assert [(c['source_id'], c['quote']) for c in plan['claims']] == [(r['id'], r['quote']) for r in exported]
        if args.factcheck_json:
            args.factcheck_json.write_bytes(packet.read_bytes())
    if args.workbook_data:
        args.workbook_data.write_text(json.dumps({
            'claims': [['ID', 'Компания', 'PDF', 'ESG', 'Тип', 'Тема', 'Цитата из PDF', 'Где смотреть'], *claims],
            'review': [['ID', 'Компания', 'PDF', 'Решение', 'Фрагмент PDF', 'Архивная разметка', 'Комментарий'], *log],
            'human_review': [['ID', 'Наблюдение Григория', 'Итог по PDF'],
                             *base.read(HERE / 'Ручная_сверка_Григория.json')],
        }, ensure_ascii=False), encoding='utf-8')
    print(f'{len(claims)} claims, {len(log)} reviewed cases')


if __name__ == '__main__':
    main()
