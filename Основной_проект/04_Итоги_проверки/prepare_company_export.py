"""Build one company workbook grouped by reporting year, with literal context and concise evidence."""
import argparse
import json
from pathlib import Path
import re

HEADERS = ['№', 'Заявление', 'Тип заявления', 'E/S/G', 'Проверка', 'Причина (источник)']
VERDICTS = {
    'true': 'Правда', 'false': 'Неправда', 'partial': 'Частично правда',
    'insufficient_evidence': 'Не установлено',
    'not_verifiable': 'Непроверяемое заявление', 'not_due': 'Срок ещё не наступил',
}
TYPES = {
    'обязательство': 'Обязательство', 'результат': 'Результат',
    'декларация': 'Декларация',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def verify_risk_assessment(record):
    """Apply the current mandatory-source policy even to an older accepted export."""
    import importlib.util
    path = Path(__file__).resolve().parents[1] / '03_Фактчекинг/Агент/factcheck.py'
    spec = importlib.util.spec_from_file_location('annual_fact_contract', path)
    contract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(contract)
    assessment = record.get('assessment') or {}
    plan = {'source_sha256': assessment.get('source_sha256'),
            'claims': [{'id': record['id'], 'quote': record['quote'], 'original': record.get('original', {})}],
            'required_risk_categories': list(contract.RISK_CATEGORIES)}
    contract.validate(assessment, plan)


def display(record, report, number, presentation=None, require_presentation=False):
    item = record['original']
    assessment = record.get('assessment') or {}
    presentation = presentation or record.get('presentation') or {}
    quote = presentation.get('exact_quote') or item.get('presentation_quote')
    if require_presentation and not quote:
        raise ValueError(f"{report['report_id']}: context-complete display quote missing for {record['id']}")
    # Compatibility for historical internal callers; annual final exports require presentation.
    quote = quote or item.get('statement') or record['quote']
    if re.search(r'^\s*\|.*\|\s*$', quote, re.M):
        raise ValueError(f"{report['report_id']}: table is not a continuous prose quotation: {record['id']}")
    pages = {int(m[1]) for e in item.get('evidence', [])
             if (m := re.search(r':p(\d+):b\d+$', e['block_id']))}
    pages.update(presentation.get('pages', []))
    for page_key in ('page', 'pdf_page'):
        if type(item.get(page_key)) is int:
            pages.add(item[page_key])
    if not pages or any(type(p) is not int for p in pages) or min(pages) < 1 or max(pages) > report['physical_pages']:
        raise ValueError(f"{report['report_id']}: source pages missing or invalid for {record['id']}")
    status = record['research_status']
    if require_presentation and status == 'complete':
        verify_risk_assessment(record)
    if (require_presentation and assessment.get('verdict') in {'true', 'false', 'partial'}
            and presentation.get('assessed_quote_complete') is not True):
        raise ValueError('Categorical verdict must cover every material assertion of the displayed quote')
    verdict = (VERDICTS[assessment['verdict']] if status == 'complete' else
               'Не проверено' if status == 'not_researched' else 'Проверка не завершена')
    explanation = presentation.get('short_reason') or assessment.get('short_reason')
    if require_presentation and not explanation:
        raise ValueError(f"{report['report_id']}: concise source-based explanation missing for {record['id']}")
    explanation = explanation or assessment.get('reason') or 'Внешние источники ещё не проверены.'
    if require_presentation and (len(explanation) > 900 or re.search(
            r'\bвывод\s*:|направлени[яй].{0,30}поиска|сохранен[ыо].{0,30}журнал|проверка проектных агентов|research_complete',
            explanation, re.I)):
        raise ValueError(f"{report['report_id']}: explanation contains process text or is too long")
    source_items = presentation.get('sources', assessment.get('sources', []))
    links = list(dict.fromkeys(s['url'] for s in source_items))
    page_list = ', '.join(map(str, sorted(pages)))
    trace = (f"{report.get('report_type', 'Отчёт')} {report.get('year', '')}, с. {page_list}." if require_presentation
             else f"Страницы PDF {page_list}. {report['pdf_source_url']}")
    return [number, quote, TYPES[item['type']], item['block'], verdict,
            '\n'.join([explanation, trace] if require_presentation else [explanation, trace, *links])]


def verify_presentation(record, report):
    """Check the displayed span against the current source; semantic/PDF review remains separate."""
    import hashlib
    import importlib.util
    project = Path(__file__).resolve().parents[1]
    source = project / report['repository_path']
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != report['packaged_md_sha256']:
        raise ValueError('Current report source hash differs from registry')
    spec = importlib.util.spec_from_file_location('export_quote_contract', project / '02_Аналитика_заявлений/Агент/scripts/esg_agent_v3.py')
    contract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(contract)
    pages, _ = contract.load_pages(source)
    texts = {p['page']: p['text'] for p in pages}
    item = record['original']
    presentation = record.get('presentation') or {}
    quote = presentation.get('exact_quote') or item.get('presentation_quote')
    raw_quote = presentation.get('raw_md_quote') or quote
    if not quote:
        raise ValueError('No literal context-complete presentation quote')
    review_pages = presentation.get('pages') or [int(re.search(r':p(\d+):b\d+$', item['presentation_block_id'])[1])]
    if not any(page in texts and contract.whole_word_quote(raw_quote, texts[page]) for page in review_pages):
        raise ValueError('Display quotation is not one continuous whole-word span in the current source')
    if presentation:
        transformed = raw_quote
        for operation in presentation.get('formatting_only_transform', []):
            if operation != 'remove_markdown_bold':
                raise ValueError('Unsupported display transformation')
            transformed = transformed.replace('**', '')
        if transformed != quote:
            raise ValueError('Display quote differs beyond documented formatting removal')
        if presentation.get('source_md_sha256') != digest or presentation.get('verified') is not True:
            raise ValueError('Display quote review is missing or belongs to another source version')
    else:
        blocks = {b['id']: b for b in contract.blocks_for(pages, report['report_id'])}
        contract.presentation_status(item, blocks)
    return quote


def prepare(company_id, exports, allow_draft):
    registry = read(Path(__file__).resolve().parents[1] / '00_Отчёты/manifest.json')
    reports = [r for r in registry if r['company_id'] == company_id]
    if not reports:
        raise ValueError(f'Unknown company: {company_id}')
    by_year = {str(r['year']): [] for r in reports}
    by_year_citations = {year: [] for year in by_year}
    report_ids = {year: [] for year in by_year}
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
            report_ids[str(report['year'])].append(report['report_id'])
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
        year = str(report['year'])
        report_ids[year].append(report['report_id'])
        displayed_quotes = set()
        for record in claims:
            verified_quote = verify_presentation(record, report)
            if verified_quote in displayed_quotes:
                raise ValueError('Repeated full quote: assess all of its aspects together before exporting one row')
            displayed_quotes.add(verified_quote)
            by_year[year].append(display(record, report, len(by_year[year]) + 1, require_presentation=True))
            presentation = record.get('presentation') or {}
            pages = presentation.get('pages') or [record['original'].get('pdf_page', record['original'].get('page'))]
            by_year_citations[year].append({'quote_url': report['pdf_source_url'], 'pages': pages,
                                          'external_sources': presentation.get('sources', [])})
    sheets = [{'id': year, 'title': year, 'report_ids': report_ids[year], 'rows': by_year[year], 'citations': by_year_citations[year]} for year in sorted(by_year)]
    return {'company': reports[0]['company'], 'draft': draft, 'layout': 'annual', 'headers': HEADERS, 'sheets': sheets}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('company_id')
    parser.add_argument('exports', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--allow-draft', action='store_true')
    args = parser.parse_args()
    args.output.write_text(json.dumps(prepare(args.company_id, args.exports, args.allow_draft),
                                      ensure_ascii=False, indent=2), encoding='utf-8')
