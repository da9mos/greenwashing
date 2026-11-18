"""Validate source versions and prepare reproducible ESG v3.1 batches for the corpus."""
import argparse
import csv
from pathlib import Path

import esg_agent_v3 as base
import esg_agent_v3_1 as profile


PROJECT = Path(__file__).resolve().parents[3]


def prepare_corpus(output, ids, pages_per_batch):
    registry = base.read(PROJECT / '00_Отчёты/manifest.json')
    known = {item['report_id'] for item in registry}
    if ids - known:
        raise ValueError(f'Unknown reports: {sorted(ids - known)}')
    output.mkdir(parents=True, exist_ok=True)
    inventory = []
    for row in registry:
        report_id = row['report_id']
        if ids and report_id not in ids:
            continue
        source = PROJECT / row['repository_path']
        if base.sha(source) != row['packaged_md_sha256']:
            raise ValueError(f'{report_id}: registry checksum differs from MD')
        work = output / report_id
        if work.exists():
            manifest, _ = base.workspace(work)
            profile.policy_for(work)
            if manifest['source_sha256'] != base.sha(source) or manifest['pages_per_batch'] != pages_per_batch:
                raise ValueError(f'{report_id}: use a new work directory for the changed input')
        else:
            manifest = profile.prepare(source, work, report_id, pages_per_batch=pages_per_batch)
        pages = len(base.read(work / 'pages.json'))
        if pages != row['physical_pages']:
            raise ValueError(f'{report_id}: page count mismatch')
        inventory.append(dict(report_id=report_id, company=row['company'], pages=pages,
                              batches=len(manifest['batches'])))
    with (output / 'inventory.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, ['report_id', 'company', 'pages', 'batches'], delimiter=';')
        writer.writeheader()
        writer.writerows(inventory)
    print(f"{len(inventory)} reports, {sum(row['pages'] for row in inventory)} pages, "
          f"{sum(row['batches'] for row in inventory)} prepared batches")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--report-id', action='append', default=[])
    parser.add_argument('--pages-per-batch', type=int, default=4)
    args = parser.parse_args()
    prepare_corpus(args.out, set(args.report_id), args.pages_per_batch)
