"""List queued report batches in preparation order, validating any reusable response."""
import argparse
import csv
import json
from pathlib import Path

import esg_agent_v3 as base
import esg_agent_v3_1 as profile


def queue(work_root, responses, report_ids, limit):
    with (work_root / 'inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
        inventory = list(csv.DictReader(stream, delimiter=';'))
    ordered = [r['report_id'] for r in inventory]
    if report_ids - set(ordered):
        raise ValueError('Requested report missing from the inventory')
    for report_id in ordered:
        if report_ids and report_id not in report_ids:
            continue
        work = work_root / report_id
        m, taxonomy = base.workspace(work)
        policy = profile.load_workspace_policy(m)
        model_inputs = None
        for batch in m['batches']:
            response = responses / report_id / f"{batch['id']}.json"
            if response.exists():
                profile.check_batch(work, response, m, taxonomy, policy)
                continue
            if model_inputs is None:
                model_inputs = profile.write_model_inputs(work / 'model_inputs', m, policy)
            yield {'report_id': report_id, 'batch_id': batch['id'], 'input': str(work / batch['file']),
                   'response': str(response), 'workspace': str(work), **model_inputs}
            limit -= 1
            if not limit:
                return


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work', type=Path)
    parser.add_argument('responses', type=Path)
    parser.add_argument('--report-id', action='append', default=[])
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error('limit must be positive')
    for item in queue(args.work, args.responses, set(args.report_id), args.limit):
        print(json.dumps(item, ensure_ascii=False))
