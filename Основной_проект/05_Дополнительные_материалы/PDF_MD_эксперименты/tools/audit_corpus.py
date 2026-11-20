"""Read-only structural and page-diagnostic audit of the selected 92-report corpus.

Only the requested audit directory is written. Decimal differences are source-text
layer diagnostics. Source images and every-word semantic review remain separate.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
from pathlib import Path
import re
import sys
import traceback
from urllib.parse import unquote, urlsplit

import compare_results as comparison
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
import pymupdf

BASE = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = BASE / '_проверка/Аудит_всего_корпуса_2026-11-16'
CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
PRIVATE_USE = re.compile(r'[\ue000-\uf8ff\U000f0000-\U000ffffd\U00100000-\U0010fffd]')
RENDERER = MarkdownIt('commonmark', {'html': True}).enable('table')
ORIGINAL_DECODE_IMAGE = comparison.decode_image
ORIGINAL_SAFE_LOCAL = comparison.safe_local


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text())


def local_file(path):
    """Metadata-only residency check before opening any corpus file."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Symlink is not an accepted direct corpus artifact')
    stat = path.stat()
    if not path.is_file():
        raise ValueError('Artifact is not a regular file')
    if stat.st_flags & 0x40000000 or stat.st_size and not stat.st_blocks:
        raise ValueError('Cloud-only or unconfirmed local residency')
    return stat


def checked_hash(path):
    local_file(path)
    return comparison.sha(path)


def resident_decode_image(path):
    try:
        local_file(path)
    except Exception as error:
        return {'ok': False, 'error': str(error), 'residency_blocked': True}
    return ORIGINAL_DECODE_IMAGE(path)


comparison.decode_image = resident_decode_image


def resident_safe_local(base, url):
    target, parsed = ORIGINAL_SAFE_LOCAL(base, url)
    if target is not None and parsed.path and target.exists() and not target.is_dir():
        local_file(target)
    return target, parsed


comparison.safe_local = resident_safe_local


def finding(code, severity='suspect', **evidence):
    return {'code': code, 'severity': severity, **evidence}


def page_records(path):
    if not path.is_file():
        return {}, 'missing_page_registry'
    try:
        local_file(path)
    except ValueError:
        return {}, 'nonresident_page_registry'
    data = read_json(path)
    records = data.get('pages', []) if isinstance(data, dict) else data
    if isinstance(records, dict):
        records = [dict(value, pdf_page=int(key)) for key, value in records.items()]
    if not isinstance(records, list):
        return {}, 'unsupported_page_registry'
    mapping = {}
    for record in records:
        number = record.get('pdf_page', record.get('page'))
        if isinstance(number, int):
            mapping[number] = record
    return mapping, None


def author_markdown(body):
    body = re.sub(r'<!-- corpus_note_start: \d+ -->.*?<!-- corpus_note_end: \d+ -->', '', body, flags=re.S)
    return re.sub(r'^\s*>\s*Служебн[^\n]*', '', body, flags=re.M | re.I)


def characters_diagnostic(text):
    result = []
    for code, pattern in [('control_characters', CONTROL), ('private_use_characters', PRIVATE_USE)]:
        matches = list(pattern.finditer(text))
        if matches:
            result.append(finding(code, count=len(matches), examples=[
                {'codepoint': f'U+{ord(m.group()):04X}', 'context': text[max(0, m.start()-50):m.end()+50]}
                for m in matches[:12]
            ]))
    if '\ufffd' in text:
        result.append(finding('unicode_replacement_characters', count=text.count('\ufffd')))
    return result


def table_diagnostics(soup):
    diagnostics = []
    for table_number, table in enumerate(soup.find_all('table'), 1):
        rows = table.find_all('tr')
        if len(rows) < 2:
            continue
        grid = {}
        invalid_span = False
        for row_number, row in enumerate(rows):
            column = 0
            for cell in row.find_all(['th', 'td'], recursive=False):
                while (row_number, column) in grid:
                    column += 1
                try:
                    colspan = int(cell.get('colspan', 1))
                    rowspan = int(cell.get('rowspan', 1))
                    if not 1 <= colspan <= 500 or not 1 <= rowspan <= 500:
                        raise ValueError('span out of bounds')
                except (TypeError, ValueError):
                    invalid_span = True
                    continue
                value = cell.get_text(' ', strip=True)
                for rr in range(row_number, min(len(rows), row_number + rowspan)):
                    for cc in range(column, column + colspan):
                        grid[rr, cc] = value
                column += colspan
        if invalid_span:
            diagnostics.append(finding('invalid_table_span', table=table_number))
        if not grid:
            continue
        width = max(column for _, column in grid) + 1
        if width < 2:
            continue
        empty_columns = [column + 1 for column in range(width)
                         if all(not grid.get((row, column), '') for row in range(len(rows)))]
        empty = sum(not grid.get((row, column), '') for row in range(len(rows)) for column in range(width))
        fraction = empty / (len(rows) * width)
        if empty_columns or width >= 6 and fraction > .4:
            diagnostics.append(finding('sparse_table_structure', table=table_number,
                                       rows=len(rows), columns=width, empty_columns=empty_columns,
                                       empty_cell_fraction=round(fraction, 4)))
    return diagnostics


def inherited_diagnostics(record, native_limitations):
    diagnostics = []
    issues = record.get('issues', [])
    if issues:
        diagnostics.append(finding('inherited_open_issues', severity='pending', issues=issues))
    for key in ('unresolved_unicode', 'ambiguous_cell_assignments', 'table_detection_error',
                'overlapping_native_conflicts', 'unresolved_source_links'):
        value = record.get(key)
        if value:
            diagnostics.append(finding('inherited_' + key, value=value))
    if native_limitations:
        diagnostics.append(finding('published_native_limitations', severity='pending', details=native_limitations))
    if record.get('review_status') == 'checked':
        evidence = record.get('evidence') or record.get('review_evidence') or record.get('source_evidence')
        if not evidence:
            diagnostics.append(finding('legacy_checked_without_explicit_evidence_manifest', severity='pending',
                                       reported_scope=record.get('review_scope', record.get('verification_scope'))))
    return diagnostics


def decimal_diagnostic(body, page_dict):
    reference = comparison.decimal_span_reference(page_dict)
    result = comparison.compare_decimals_to_spans(body, reference)
    if not result['pdf_only'] and not result['markdown_only']:
        return None
    evidence = result['pdf_span_evidence']
    markdown_evidence = result['markdown_evidence']
    result['pdf_span_evidence'] = evidence[:40]
    result['markdown_evidence'] = markdown_evidence[:40]
    result['evidence_truncated'] = len(evidence) > 40 or len(markdown_evidence) > 40
    result['pdf_span_evidence_total'] = len(evidence)
    result['markdown_evidence_total'] = len(markdown_evidence)
    return finding('decimal_difference_vs_pdf_text_spans', **result)


def report_metadata(base, row):
    rid = row['report_id']
    if row['kind'].startswith('Codex'):
        directory = base / '_проверка/Codex' / rid / 'v2'
        receipt_path = directory / 'receipt.json'
        records_path = directory / 'worker_checks/pages.json'
    else:
        receipt_path = base / 'Все_отчёты_MD/_проверка/published' / (rid + '.json')
        records_path = base / '_проверка/native_candidates' / rid / '_проверка/pages.json'
        try:
            local_file(receipt_path)
        except ValueError:
            ledger_path = base / '_проверка/native_corpus_validation.json'
            local_file(ledger_path)
            cached = read_json(ledger_path)['reports'][rid]
            records, error = page_records(records_path)
            cached = dict(cached, published_receipt_not_local=str(receipt_path))
            return cached, ledger_path, records, error
    local_file(receipt_path)
    records, error = page_records(records_path)
    return read_json(receipt_path), receipt_path, records, error


def audit_one(task):
    base = Path(task['base'])
    output = Path(task['output'])
    row = task['row']
    source_meta = task['source']
    rid = row['report_id']
    result = {'report_id': rid, 'kind': row['kind'], 'selected_path': row['path'],
              'source_path': source_meta['path'], 'expected_pages': row['pages'],
              'started_at': now(), 'findings': [], 'full_source_semantic_review_confirmed': False}
    result['audit_implementation_sha256'] = comparison.sha(Path(__file__))
    pages = []
    source = Path(source_meta['path'])
    md = Path(row['path'])
    try:
        source_before = local_file(source)
        md_before = local_file(md)
        receipt, receipt_path, records, registry_error = report_metadata(base, row)
        result['receipt_path'] = str(receipt_path)
        result['receipt_sha256'] = checked_hash(receipt_path)
        if receipt.get('published_receipt_not_local'):
            result['findings'].append(finding('published_receipt_uses_local_ledger_cache', 'pending',
                                              nonresident_path=receipt['published_receipt_not_local']))
        source_hash = checked_hash(source)
        result['source_sha256'] = source_hash
        expected_md_hash = receipt.get('report_sha256', receipt.get('final_md_sha256'))
        if source_hash != source_meta['sha256'] or source_hash != receipt.get('source_sha256'):
            result['findings'].append(finding('source_identity_mismatch', 'failed'))
        structure = comparison.inspect_markdown(md, row['pages'])
        result['report_sha256'] = structure['report_sha256']
        if structure['report_sha256'] != row['sha256'] or structure['report_sha256'] != expected_md_hash:
            result['findings'].append(finding('markdown_identity_mismatch', 'failed'))
        for item in structure['issues']:
            nonresident = 'local residency' in item.get('error', '')
            severity = 'pending' if item['code'] == 'remote_image_not_verified' or nonresident else 'failed'
            if item.get('target', '').startswith('missing-reference-definition:'):
                severity = 'suspect'
            result['findings'].append(finding('structure_' + item['code'], severity, details=item))
        result['images_checked'] = structure['image_count']
        result['images'] = structure['images']
        result['external_links_not_fetched'] = structure['external_links_not_fetched']
        result['markers'] = structure['markers']
        if registry_error:
            result['findings'].append(finding(registry_error, 'pending'))
        elif sorted(records) != list(range(1, row['pages'] + 1)):
            result['findings'].append(finding('incomplete_page_registry', 'failed'))
        if row['kind'].startswith('Codex'):
            frozen = base / '_проверка/Инструкция_на_старте.md'
            prompt = receipt_path.parent / 'prompt.txt'
            if not frozen.is_file() or checked_hash(frozen) != receipt.get('instruction_sha256'):
                result['findings'].append(finding('instruction_identity_mismatch', 'failed'))
            if not prompt.is_file() or checked_hash(prompt) != receipt.get('prompt_sha256'):
                result['findings'].append(finding('prompt_identity_mismatch', 'failed'))
        with pymupdf.open(source) as document:
            if len(document) != row['pages'] or len(document) != source_meta['pages']:
                result['findings'].append(finding('source_page_count_mismatch', 'failed', actual=len(document)))
            for number, page in enumerate(document, 1):
                body = structure['pages'].get(number, '')
                record = records.get(number, {})
                page_findings = inherited_diagnostics(record, receipt.get('limitations', {}).get(str(number)))
                author = author_markdown(body)
                # Rendering inserts separators between cells. Decimal extraction uses
                # the existing span-aware comparator and preserves those boundaries.
                soup = BeautifulSoup(RENDERER.render(author), 'html.parser')
                visible = soup.get_text(' ')
                page_findings.extend(characters_diagnostic(visible))
                page_findings.extend(table_diagnostics(soup))
                for link in soup.find_all(['a', 'img']):
                    value = link.get('href', link.get('src'))
                    if value is not None and urlsplit(unquote(value)).scheme.casefold() in ('javascript', 'vbscript', 'file'):
                        page_findings.append(finding('unsafe_or_nonportable_uri_scheme', 'failed', target=value[:300]))
                page_dict = page.get_text('dict')
                source_chars = sum(len(span.get('text', '')) for block in page_dict['blocks']
                                   for line in block.get('lines', []) for span in line.get('spans', []))
                images = page.get_image_info()
                large_raster = any(pymupdf.Rect(image['bbox']).get_area() > page.rect.get_area() * .35 for image in images)
                if images and source_chars < 100 or large_raster and source_chars < 500:
                    if not record.get('ocr_verified'):
                        page_findings.append(finding('image_dominant_page_without_verified_ocr',
                                                     severity='pending', source_text_chars=source_chars,
                                                     source_image_count=len(images)))
                decimal = decimal_diagnostic(author, page_dict)
                if decimal:
                    page_findings.append(decimal)
                pages.append({'report_id': rid, 'pdf_page': number, 'findings': page_findings,
                              'reported_review_status': record.get('review_status'),
                              'source_text_chars': source_chars, 'source_image_count': len(images),
                              'full_source_semantic_review_confirmed': False,
                              'source_review_pending': True})
        source_after = source.stat()
        md_after = md.stat()
        if (source_before.st_size, source_before.st_mtime_ns) != (source_after.st_size, source_after.st_mtime_ns):
            result['findings'].append(finding('source_changed_during_audit', 'failed'))
        if (md_before.st_size, md_before.st_mtime_ns) != (md_after.st_size, md_after.st_mtime_ns):
            result['findings'].append(finding('markdown_changed_during_audit', 'failed'))
    except Exception as error:
        result['findings'].append(finding('audit_exception', 'failed', error=type(error).__name__ + ': ' + str(error)))
        result['traceback'] = traceback.format_exc()
    result['pages_audited'] = len(pages)
    result['pages_source_review_pending'] = [page['pdf_page'] for page in pages]
    counts = Counter(item['code'] for page in pages for item in page['findings'])
    counts.update(item['code'] for item in result['findings'])
    result['finding_counts'] = dict(counts)
    result['structural_failed'] = any(item['severity'] == 'failed' for item in result['findings']) or any(
        item['severity'] == 'failed' for page in pages for item in page['findings'])
    result['state'] = 'failed' if result['structural_failed'] else 'structurally_passed_with_pending_source_review'
    result['finished_at'] = now()
    report_directory = output / 'reports'
    report_directory.mkdir(parents=True, exist_ok=True)
    (report_directory / (rid + '.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    with (report_directory / (rid + '.pages.jsonl')).open('w') as stream:
        for page in pages:
            stream.write(json.dumps(page, ensure_ascii=False) + '\n')
    return result


def write_results(output, snapshot, results, finished):
    ordered = sorted(results, key=lambda result: [row['report_id'] for row in snapshot['reports']].index(result['report_id']))
    codes = Counter()
    for result in ordered:
        codes.update(result['finding_counts'])
    summary = {'updated_at': now(), 'finished': finished, 'reports_expected': len(snapshot['reports']),
               'reports_audited': len(results), 'pages_expected': sum(row['pages'] for row in snapshot['reports']),
               'pages_audited': sum(result['pages_audited'] for result in results),
               'structural_failed_reports': [result['report_id'] for result in ordered if result['structural_failed']],
               'finding_counts': dict(codes), 'full_source_semantic_review_confirmed': False,
               'source_review_pending_pages': sum(result['pages_audited'] for result in results),
               'scope': 'All selected PDFs and MD pages mechanically audited. Source-layer decimal differences are suspect diagnostics. Images decoded without visual content adjudication.',
               'reports': ordered}
    (output / 'audit.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    if not finished:
        return
    with (output / 'findings.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, ['report_id', 'pdf_page', 'severity', 'code', 'evidence'], delimiter=';')
        writer.writeheader()
        for result in ordered:
            for item in result['findings']:
                writer.writerow({'report_id': result['report_id'], 'pdf_page': '', 'severity': item['severity'],
                                 'code': item['code'], 'evidence': json.dumps(item, ensure_ascii=False)})
            for line in (output / 'reports' / (result['report_id'] + '.pages.jsonl')).read_text().splitlines():
                page = json.loads(line)
                for item in page['findings']:
                    writer.writerow({'report_id': result['report_id'], 'pdf_page': page['pdf_page'],
                                     'severity': item['severity'], 'code': item['code'],
                                     'evidence': json.dumps(item, ensure_ascii=False)})
    with (output / 'source_review_pending_pages.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream, delimiter=';')
        writer.writerow(['report_id', 'pdf_page', 'review_status'])
        for result in ordered:
            for number in result['pages_source_review_pending']:
                writer.writerow([result['report_id'], number, 'pending_full_source_semantic_review'])
    lines = ['# Аудит выбранного корпуса PDF и Markdown', '',
             f"Проверены {summary['reports_audited']} отчёта из {summary['reports_expected']} и {summary['pages_audited']} страниц из {summary['pages_expected']}.", '',
             f"Структурные ошибки найдены у {len(summary['structural_failed_reports'])} отчётов. Все {summary['source_review_pending_pages']} страниц сохраняют открытый статус полной смысловой сверки по оригиналу.", '',
             'Проверка охватила идентичность PDF, Markdown и протоколов, последовательность страниц, якоря, локальные ссылки, декодирование изображений, управляющие символы, пустые колонки и диагностическое сравнение десятичных значений с отдельными PDF-span.', '',
             'Десятичные расхождения требуют чтения оригинала. Текстовый слой PDF может быть повреждён. Геометрия сносок и границы ячеек сохранены при сравнении. Декодирование изображений подтверждает читаемость файла, полная визуальная сверка содержания остаётся открытой.', '',
             '[Полный результат](audit.json) · [Все замечания](findings.csv) · [Все страницы ожидающие смысловой сверки](source_review_pending_pages.csv)', '',
             '| Код проверки | Число замечаний |', '|---|---:|']
    lines.extend(f'| {code} | {count} |' for code, count in codes.most_common())
    lines += ['', '| Отчёт | Страниц | Структурный итог |', '|---|---:|---|']
    for result in ordered:
        lines.append(f"| [{result['report_id']}](reports/{result['report_id']}.json) | {result['pages_audited']} | {result['state']} |")
    (output / 'Отчёт.md').write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=BASE)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--workers', type=int, choices=(1, 2, 3), default=3)
    parser.add_argument('--reports', nargs='*')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    raw = (args.base / '_проверка/unified_corpus_index.json').read_bytes()
    snapshot = json.loads(raw)
    if args.reports:
        unknown = set(args.reports) - {row['report_id'] for row in snapshot['reports']}
        if unknown:
            parser.error('Unknown report IDs ' + str(sorted(unknown)))
        snapshot['reports'] = [row for row in snapshot['reports'] if row['report_id'] in args.reports]
    sources = {row['report_id']: row for row in read_json(args.base / '_проверка/sources_manifest.json')['reports']}
    snapshot['audit_snapshot_at'] = now()
    snapshot['audit_implementation_sha256'] = comparison.sha(Path(__file__))
    snapshot['index_file_sha256'] = hashlib.sha256(raw).hexdigest()
    (args.output / 'snapshot_index.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
    tasks = [{'base': str(args.base.resolve()), 'output': str(args.output.resolve()), 'row': row,
              'source': sources[row['report_id']]} for row in snapshot['reports']]
    results = []
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context('spawn')) as pool:
        jobs = {pool.submit(audit_one, task): task['row']['report_id'] for task in tasks}
        for job in as_completed(jobs):
            result = job.result()
            results.append(result)
            write_results(args.output, snapshot, results, False)
            print(json.dumps({'finished_reports': len(results), 'total_reports': len(tasks),
                              'report_id': result['report_id'], 'pages': result['pages_audited'],
                              'state': result['state']}, ensure_ascii=False), flush=True)
    write_results(args.output, snapshot, results, True)
    print(json.dumps({'finished': True, 'reports': len(results), 'pages': sum(r['pages_audited'] for r in results),
                      'structural_failed_reports': sum(r['structural_failed'] for r in results)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
