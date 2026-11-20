"""Build the six-column export input from one fact-check export per company report."""
import argparse
import json
from pathlib import Path
import re

HEADERS = ['№', 'Заявление', 'Тип заявления', 'E/S/G', 'Проверка', 'Почему и на основании чего']
VERDICTS = {
    'true': 'Подтверждено', 'false': 'Опровергнуто', 'partial': 'Частично подтверждено',
    'insufficient_evidence': 'Недостаточно сопоставимых данных',
    'not_verifiable': 'Нет проверяемого критерия', 'not_due': 'Срок ещё не наступил',
}
TYPES = {
    'обязательство': 'Обязательство', 'результат': 'Утверждение о результате',
    'декларация': 'Общая декларация',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def display(record, report, number):
    item = record['original']
    assessment = record.get('assessment') or {}
    quote = item.get('statement') or record['quote']
    if re.search(r'^\s*\|.*\|\s*$', quote, re.M):
        raise ValueError(f"{report['report_id']}: rewrite table {record['id']} with traceable context before exporting")
    pages = {int(m[1]) for e in item.get('evidence', [])
             if (m := re.search(r':p(\d+):b\d+$', e['block_id']))}
    for page_key in ('page', 'pdf_page'):
        if type(item.get(page_key)) is int:
            pages.add(item[page_key])
    if not pages or min(pages) < 1 or max(pages) > report['physical_pages']:
        raise ValueError(f"{report['report_id']}: source pages missing or invalid for {record['id']}")
    status = record['research_status']
    verdict = (VERDICTS[assessment['verdict']] if status == 'complete' else
               'Внешняя проверка не выполнена' if status == 'not_researched' else 'Внешняя проверка открыта')
    explanation = assessment.get('reason') or 'Внешний поиск ещё не выполнен.'
    page_list = ', '.join(map(str, sorted(pages)))
    links = list(dict.fromkeys(s['url'] for s in assessment.get('sources', [])))
    trace = f"Страницы PDF {page_list}. {report['pdf_source_url']}"
    return [number, quote, TYPES[item['type']], item['block'], verdict,
            '\n'.join([explanation, trace, *links])]


def prepare(company_id, exports, allow_draft):
    registry = read(Path(__file__).resolve().parents[1] / '00_Отчёты/manifest.json')
    reports = [r for r in registry if r['company_id'] == company_id]
    if not reports:
        raise ValueError(f'Unknown company: {company_id}')
    sheets = []
    draft = False
    for report in reports:
        directory = exports / report['report_id']
        draft_directory = exports / (report['report_id'] + '_draft')
        if directory.exists() and draft_directory.exists():
            raise ValueError(f"Ambiguous export for {report['report_id']}")
        if allow_draft and not directory.exists() and draft_directory.exists():
            directory = draft_directory
        if not directory.exists() and allow_draft:
            draft = True
            continue
        summary = read(directory / 'summary.json')
        claims = read(directory / 'claims.json')['claims']
        if summary['total'] != len(claims):
            raise ValueError(f"{report['report_id']}: count mismatch")
        if summary.get('report_id') not in (None, report['report_id']):
            raise ValueError(f"{report['report_id']}: wrong fact-check export")
        complete = (
            summary['status'] == 'research_complete'
            and summary.get('report_id') == report['report_id']
            and summary.get('md_sha256') == report['packaged_md_sha256']
            and summary.get('extraction_coverage_complete') is True
            and all(r['research_status'] == 'complete' for r in claims)
        )
        if not complete and not allow_draft:
            raise ValueError(f"{report['report_id']}: unfinished extraction or research")
        draft |= not complete
        rows = [display(record, report, i) for i, record in enumerate(claims, 1)]
        sheets.append({'id': report['report_id'], 'title': f"{report['year']} {report['report_type']}", 'rows': rows})
    if not sheets or len({s['title'] for s in sheets}) != len(sheets):
        raise ValueError('Missing report exports or duplicate report tab names')
    return {'company': reports[0]['company'], 'draft': draft, 'headers': HEADERS, 'sheets': sheets}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('company_id')
    parser.add_argument('exports', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--allow-draft', action='store_true')
    args = parser.parse_args()
    args.output.write_text(json.dumps(prepare(args.company_id, args.exports, args.allow_draft),
                                      ensure_ascii=False, indent=2), encoding='utf-8')
