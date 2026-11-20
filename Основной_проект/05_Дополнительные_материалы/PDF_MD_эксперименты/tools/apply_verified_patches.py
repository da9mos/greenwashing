"""Apply exact, source-evidenced corrections while preserving model originals."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import time
import run_models as rm


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    previous_file = rm.BASE / '_проверка/source_corrections_applied.json'
    previous = json.loads(previous_file.read_text()) if previous_file.exists() else []
    previous_by_id = {(r['engine'], r['report_id']): r for r in previous}
    grouped = defaultdict(list)
    for patch in manifest['patches']:
        grouped[(patch['engine'], patch['report_id'], patch['path'])].append(patch)
    proposed = []
    evidence_cache = {}
    for (engine, rid, file), patches in grouped.items():
        target = (rm.ROOT / file).resolve()
        expected_folder = (rm.BASE / engine / rid.split('-')[0] / rid).resolve()
        if target != expected_folder / 'report.md':
            raise ValueError('Unexpected output target')
        original = target.read_text()
        original_sha = hashlib.sha256(original.encode()).hexdigest()
        earlier = previous_by_id.get((engine, rid))
        if earlier and earlier['corrected_report_sha256'] == original_sha and earlier['patch_manifest_sha256'] == rm.sha(args.manifest):
            continue
        if any(p['expected_report_sha256'] != original_sha for p in patches):
            raise ValueError('Input MD hash changed: ' + rid)
        updated = original
        for patch in patches:
            n = patch['pdf_page']
            evidence = patch['source_evidence']
            source = (rm.ROOT / evidence['pdf']).resolve()
            if source != (rm.BASE / '_источники' / (rid + '.pdf')).resolve() or evidence['pdf_page'] != n:
                raise ValueError('Wrong source evidence identity')
            key = (rid, n)
            span_key = lambda sp: (sp['text'], tuple(round(x, 3) for x in sp['bbox']), round(sp['size'], 3), sp['flags'])
            if key not in evidence_cache:
                with rm.fitz.open(source) as doc:
                    evidence_cache[key] = {span_key(s) for b in doc[n - 1].get_text('dict')['blocks']
                                           for line in b.get('lines', []) for s in line['spans']}
            if any(span_key(s) not in evidence_cache[key] for s in evidence.get('spans', [])):
                raise ValueError('Evidence spans do not match source: ' + patch['id'])
            matches = list(re.finditer(r'<!--\s*pdf_page:\s*(\d+)\s*-->', updated))
            targets = [(i, m) for i, m in enumerate(matches) if int(m[1]) == n]
            if len(targets) != 1:
                raise ValueError('Page boundary not unique')
            i, marker = targets[0]
            end = matches[i + 1].start() if i + 1 < len(matches) else len(updated)
            body = updated[marker.end():end]
            before = patch['before']
            if not before or body.count(before) != patch.get('expected_occurrences_in_page', 1):
                raise ValueError('Exact page replacement guard failed: ' + patch['id'])
            body = body.replace(before, patch['after'], 1)
            updated = updated[:marker.end()] + body + updated[end:]
        index = json.loads((rm.BASE / '_проверка/входы' / rid / 'pages.json').read_text())
        proposed.append((target, engine, rid, patches, original, updated, original_sha, index))
    # All guards pass before any publication.
    applied = []
    for target, engine, rid, patches, original, updated, original_sha, index in proposed:
        history = rm.BASE / '_проверка/pre_source_corrections' / engine / rid
        history.mkdir(parents=True, exist_ok=True)
        (history / (original_sha + '.md')).write_text(original)
        tmp = target.with_suffix('.md.corrected.part')
        tmp.write_text(updated)
        tmp.replace(target)
        gate = rm.validate_bundle(target.parent, index)
        if not gate['assembled']:
            target.write_text(original)
            raise ValueError('Correction broke structural checks: ' + str(gate['errors']))
        receipt = (rm.BASE / '_проверка/DeepSeek' / rid / 'assembled.json' if engine == 'DeepSeek'
                   else rm.BASE / '_проверка/Codex' / rid / 'v2/receipt.json')
        record = {'engine': engine, 'report_id': rid, 'base_report_sha256': original_sha,
                  'corrected_report_sha256': rm.sha(target), 'patch_ids': [p['id'] for p in patches],
                  'patch_manifest_sha256': rm.sha(args.manifest), 'source_sha256': rm.sha(rm.BASE / '_источники' / (rid + '.pdf')),
                  'source_review_scope': 'Listed cells/tables/objects only; not all source pages',
                  'whole_report_checked': False, 'structural_check': gate, 'applied_at': time.time()}
        if receipt.exists():
            if not (history / 'original_receipt.json').exists():
                shutil.copy2(receipt, history / 'original_receipt.json')
            meta = json.loads(receipt.read_text())
            meta['report_sha256'] = record['corrected_report_sha256']
            meta['source_corrections'] = {k: v for k, v in record.items() if k != 'structural_check'}
            rm.put_json(receipt, meta)
        rm.put_json(history / 'applied.json', record)
        applied.append(record)
    for record in applied:
        previous_by_id[(record['engine'], record['report_id'])] = record
    rm.put_json(previous_file, list(previous_by_id.values()))
    print('Applied', sum(len(r['patch_ids']) for r in applied), 'source-evidenced replacements to', len(applied), 'MD files')


if __name__ == '__main__':
    main()
