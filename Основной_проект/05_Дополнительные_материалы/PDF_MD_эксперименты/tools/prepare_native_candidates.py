"""Prepare exact native-text candidates for model review, in isolated processes."""
import argparse
import concurrent.futures as futures
import multiprocessing
from pathlib import Path
import json
import os
import time
import traceback
import run_models as rm
import native_candidate as native


def one(row):
    rid = row['report_id']
    source = rm.BASE / '_источники' / (rid + '.pdf')
    out = rm.BASE / '_проверка/native_candidates' / rid
    coverage = out / '_проверка/native_coverage.json'
    if coverage.exists() and (out / 'report.md').exists():
        old = json.loads(coverage.read_text())
        if (old.get('source_sha256') == rm.sha(source) and old.get('implementation_sha256') == native.IMPLEMENTATION_SHA
                and old.get('report_sha256') == rm.sha(out / 'report.md')):
            return old
    native.convert(source, out, image_source=rm.BASE / '_проверка/входы' / rid)
    return json.loads(coverage.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    # Feed not-yet-published Codex reports first; completed reports are audited later.
    rows = sorted(rm.ROWS, key=lambda r: ((rm.report_dir('Codex', r) / 'report.md').exists(), rm.ROWS.index(r)))
    records = {}
    started = time.time()
    def save():
        rm.put_json(rm.BASE / '_проверка/native_candidate_batch.json', {
            'pid': os.getpid(), 'started_at': started, 'updated_at': time.time(),
            'reports_requested': len(rows), 'reports_finished': len(records),
            'reports': records, 'implementation_sha256': native.IMPLEMENTATION_SHA,
            'scope': 'Mechanical native-text candidates with glyph accounting; not completed model or visual review'})
    save()
    with futures.ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context('spawn')) as pool:
        pending = {pool.submit(one, row): row for row in rows}
        for future in futures.as_completed(pending):
            row = pending[future]
            try:
                result = future.result()
                records[row['report_id']] = {'state': 'candidate_ready', **result}
            except Exception as exc:
                records[row['report_id']] = {'state': 'needs_review', 'error': str(exc)[:1600], 'traceback': traceback.format_exc()}
            save()
            print('NATIVE CANDIDATE', row['report_id'], records[row['report_id']]['state'], flush=True)
    save()


if __name__ == '__main__':
    main()
