"""Explicit input revision: archive rejected cache entries before new requests."""
import concurrent.futures as futures
import json
from pathlib import Path
import shutil
import time
import run_models as rm
from run_deepseek_v3 import transcribe, VERSION


def repair(row, item):
    folder = rm.BASE / '_проверка/DeepSeek' / row['report_id'] / VERSION
    file = folder / f"page_{item['pdf_page']:04d}.json"
    try:
        value = transcribe(row, item)
        return {'report_id': row['report_id'], 'pdf_page': item['pdf_page'], 'state': 'current', 'request_sha256': value['request_sha256']}
    except ValueError as exc:
        if 'Different source or prompt' not in str(exc):
            raise
    original = json.loads(file.read_text())
    archive = folder / 'input_revision_history' / original['request_sha256']
    archive.mkdir(parents=True, exist_ok=True)
    for old in (file, folder / 'raw' / file.name, folder / 'requests' / file.name):
        if old.exists():
            target = archive / (old.parent.name + '_' + old.name)
            if target.exists() and rm.sha(target) != rm.sha(old):
                raise ValueError('Historical input collision')
            old.replace(target)
    rm.put_json(archive / 'revision_reason.json', {
        'reason': 'Source geometry extraction flags changed while PDF source remained unchanged. Rejected stale request cache was archived; no original answer deleted.',
        'old_request_signature': original['request_signature'], 'old_instruction_sha256': original['instruction_sha256'],
        'pdf_page': item['pdf_page'], 'timestamp': time.time()})
    value = transcribe(row, item)
    return {'report_id': row['report_id'], 'pdf_page': item['pdf_page'], 'state': 'regenerated',
            'old_request_sha256': original['request_sha256'], 'request_sha256': value['request_sha256'],
            'model': value['model'], 'review_status': value['review_status']}


def main():
    state = json.loads((rm.BASE / '_проверка/deepseek_controller.json').read_text())
    jobs = []
    for row in rm.ROWS:
        record = state['reports'].get(row['report_id'], {})
        if record.get('stage') not in ('incomplete', 'assembled', 'structural_issues'):
            continue
        if not record.get('page_errors'):
            continue
        index = json.loads((rm.BASE / '_проверка/входы' / row['report_id'] / 'pages.json').read_text())
        by_page = {p['pdf_page']: p for p in index['pages']}
        for n in record['page_errors']:
            jobs.append((row, by_page[n]))
    results = []
    with futures.ThreadPoolExecutor(max_workers=12) as executor:
        pending = {executor.submit(repair, row, item): (row, item) for row, item in jobs}
        for future in futures.as_completed(pending):
            row, item = pending[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({'report_id': row['report_id'], 'pdf_page': item['pdf_page'], 'state': 'failed', 'error': str(exc)[:1500]})
            rm.put_json(rm.BASE / '_проверка/input_revision_repairs.json', results)
    print('Input revision repairs', len(results), 'failed', sum(r['state'] == 'failed' for r in results))


if __name__ == '__main__':
    main()
