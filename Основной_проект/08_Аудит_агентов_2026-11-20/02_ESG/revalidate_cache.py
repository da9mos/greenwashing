"""Read-only revalidation; derivatives stay inside this audit directory."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(PROJECT / '02_Аналитика_заявлений/Агент/scripts'))
import esg_agent_v3_1 as profile
import review_response

spec = importlib.util.spec_from_file_location('audit_controller', PROJECT / '06_Прогон_корпуса/run_corpus.py')
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def diff(original, revised):
    changes = []
    for old, new in zip(original['claims'], revised['claims']):
        for key in sorted(set(old) | set(new)):
            if old.get(key) != new.get(key):
                changes.append({'claim_id': old['id'], 'field': key,
                                'before': old.get(key), 'after': new.get(key)})
    for old, new in zip(original['coverage'], revised['coverage']):
        if old != new:
            changes.append({'block_id': old['block_id'], 'before': old, 'after': new})
    return changes


def numeric_diagnostics(work, data):
    """Show every numeric support issue without inferring the correct replacement."""
    manifest = profile.base.read(work / 'manifest.json')
    item = next(b for b in manifest['batches'] if b['id'] == data['batch_id'])
    batch = profile.base.read(work / item['file'])
    blocks = {b['id']: b['text'] for b in batch['blocks']}
    issues = []
    for claim in data['claims']:
        for evidence in claim['evidence']:
            if evidence['role'] in ('value', 'period') and not profile.base.evidence_supports(
                    evidence['role'], evidence['quote'], blocks[evidence['block_id']]):
                source = blocks[evidence['block_id']]
                start = source.find(evidence['quote'])
                issues.append({'claim_id': claim['id'], 'issue': 'numeric_evidence_span',
                               'role': evidence['role'], 'block_id': evidence['block_id'],
                               'quote': evidence['quote'],
                               'source_context': source[max(0, start - 80):start + len(evidence['quote']) + 80]})
        if claim.get('quantitative'):
            for field in ('value', 'period'):
                value = claim.get(field, '')
                if value and not any(e['role'] == field and profile.base.evidence_supports(field, value, e['quote'])
                                     for e in claim['evidence']):
                    issues.append({'claim_id': claim['id'], 'issue': 'unsupported_field',
                                   'field': field, 'value': value,
                                   'quotes': [e['quote'] for e in claim['evidence'] if e['role'] == field]})
    return issues


def main():
    started = datetime.now(timezone.utc).isoformat()
    reports = controller.registry()
    entries, inventory = [], []
    tracked = {}
    totals = Counter(reports_in_registry=len(reports))
    for report in reports:
        cache = controller.cache_for(report)
        work = cache / 'prepared'
        files = sorted((cache / 'accepted').glob('*.json'))
        row = {'report_id': report['report_id'], 'cache': str(cache),
               'source_sha256_expected': report['packaged_md_sha256'],
               'accepted_files': len(files)}
        source = PROJECT / report['repository_path']
        tracked[str(source)] = digest(source)
        row['source_sha256_actual'] = tracked[str(source)]
        if files:
            for name in ('manifest.json', 'manifest.sha256', 'pages.json', 'blocks.json', 'preamble.txt'):
                tracked[str(work / name)] = digest(work / name)
            manifest = profile.base.read(work / 'manifest.json')
            for batch in manifest['batches']:
                tracked[str(work / batch['file'])] = digest(work / batch['file'])
        inventory.append(row)
        for path in files:
            before = digest(path)
            tracked[str(path)] = before
            data = profile.base.read(path)
            entry = {'report_id': report['report_id'], 'batch_id': data.get('batch_id'),
                     'path': str(path), 'original_sha256': before,
                     'claims': len(data.get('claims', [])), 'coverage_blocks': len(data.get('coverage', []))}
            totals['accepted_files_found'] += 1
            totals['claims_in_accepted_files'] += entry['claims']
            try:
                _, stats = profile.check(work, path)
                entry.update(status='validated', validation=stats)
                totals['validated_batches'] += 1
                totals['validated_claims'] += entry['claims']
                for key in ('pending_blocks', 'pending_claims', 'pending_classifications'):
                    totals['validated_' + key] += stats[key]
            except (ValueError, TypeError, KeyError, OSError) as exc:
                entry.update(status='invalid', reason=str(exc), exception=type(exc).__name__)
                entry['numeric_diagnostics'] = numeric_diagnostics(work, data)
                totals['invalid_batches'] += 1
                totals['claims_in_invalid_batches'] += entry['claims']
                try:
                    revised, stats = review_response.review(work, path)
                    changes = diff(data, revised)
                    if not changes:
                        raise ValueError('review produced no changes')
                    target = HERE / 'cache_revisions' / report['report_id'] / path.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    profile.base.write(target, revised)
                    profile.check(work, target)
                    entry['revision_candidate'] = {
                        'path': str(target.relative_to(HERE)), 'original_sha256': before,
                        'new_sha256': digest(target), 'diff_summary': changes, 'validation': stats,
                        'status': 'derivative_only_not_promoted_to_accepted'}
                    totals['derivative_candidates'] += 1
                    totals['claims_in_derivative_candidates'] += len(revised['claims'])
                except (ValueError, TypeError, KeyError, OSError) as review_exc:
                    entry['automatic_revision'] = {'status': 'not_created', 'reason': str(review_exc),
                        'note': 'No inferred number, period or sliced numeric quote was reconstructed.'}
            entries.append(entry)
    changes = []
    for path, before in tracked.items():
        after = digest(path)
        if before != after:
            changes.append({'path': path, 'before': before, 'after': after})
    result = {
        'started_at_utc': started, 'finished_at_utc': datetime.now(timezone.utc).isoformat(),
        'validator_files': {str(path): digest(path) for path in
                            [Path(profile.__file__), Path(profile.base.__file__), Path(review_response.__file__)]},
        'selection': 'All accepted/*.json under cache_for for the current 92-report registry; sourceSHA+promptSHA.',
        'scope': 'Structural, quote, coverage, quantitative context and classification trace validation; no semantic recall or truth certification.',
        'totals': dict(totals), 'reports': inventory, 'entries': entries,
        'source_and_cache_readback': {'files_tracked': len(tracked), 'changed_files': changes,
                                     'all_originals_unchanged': not changes},
        'invalid_reason_counts': dict(Counter(e['reason'] for e in entries if e['status'] == 'invalid'))
    }
    profile.base.write(HERE / 'cache_revalidation.json', result)
    print(json.dumps({'totals': result['totals'], 'readback': result['source_and_cache_readback'],
                      'invalid_reason_counts': result['invalid_reason_counts']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
