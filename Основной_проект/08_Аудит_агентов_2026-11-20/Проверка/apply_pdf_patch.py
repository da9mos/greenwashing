"""Apply the PDF-agent's verified patch, retaining prior inputs and reusable batches."""
from copy import deepcopy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

AUDIT = Path(__file__).resolve().parents[1]
PROJECT = AUDIT.parent
sys.path.insert(0, str(PROJECT / '02_Аналитика_заявлений/Агент/scripts'))
import esg_agent_v3 as base
import esg_agent_v3_1 as profile


def main():
    patch = base.read(AUDIT / '01_PDF/patch_review.json')
    master = PROJECT / '00_Отчёты/Газпром/GAZP-2023-ЭО.md'
    candidate = AUDIT / '01_PDF/patched_report.md'
    old_sha = patch['original_output']['sha256']
    new_sha = patch['patched_output']['sha256']
    assert base.sha(master) == old_sha, 'Master version moved; inspect rather than overwrite'
    assert base.sha(candidate) == new_sha
    registry_path = PROJECT / '00_Отчёты/manifest.json'
    registry = base.read(registry_path)
    report = next(r for r in registry if r['report_id'] == 'GAZP-2023-ЭО')
    assert report['packaged_md_sha256'] == old_sha
    state = Path.home() / '.local/state/sber-esg-worker'
    revision = base.sha(PROJECT / '02_Аналитика_заявлений/Агент/agent/esg_agent_v3_1.md')[:10]
    old_root = state / f"{report['report_id']}-{old_sha[:10]}-{revision}"
    old_work = old_root / 'prepared'
    old_manifest, _ = base.workspace(old_work)
    frozen = state / 'frozen_inputs' / (old_sha + '.md')
    frozen.parent.mkdir(exist_ok=True)
    if not frozen.exists():
        frozen.write_bytes(master.read_bytes())
    assert base.sha(frozen) == old_sha
    before_manifest = (old_work / 'manifest.json').read_bytes()
    (AUDIT / 'Проверка/previous_workspace_manifest.json').write_bytes(before_manifest)
    old_manifest['source_path'] = str(frozen)
    base.write(old_work / 'manifest.json', old_manifest)
    (old_work / 'manifest.sha256').write_text(base.sha(old_work / 'manifest.json') + '\n')
    base.workspace(old_work)
    (AUDIT / 'Проверка/previous_corpus_manifest.json').write_bytes(registry_path.read_bytes())
    (AUDIT / 'Проверка/previous_report_registry.csv').write_bytes((PROJECT / '00_Отчёты/Реестр_отчётов.csv').read_bytes())
    master.write_bytes(candidate.read_bytes())
    report['packaged_md_sha256'] = new_sha
    report['version'] += '; адресная PDF-сверка 20.11.2026'
    report['source_patch_provenance'] = '08_Аудит_агентов_2026-11-20/01_PDF/patch_review.json'
    base.write(registry_path, registry)
    csv_path = PROJECT / '00_Отчёты/Реестр_отчётов.csv'
    with csv_path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter=';'); fields = reader.fieldnames; rows = list(reader)
    for row in rows:
        if row['report_id'] == report['report_id']:
            row['packaged_md_sha256'] = new_sha
            row['version'] = report['version']
    with csv_path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fields, delimiter=';'); writer.writeheader(); writer.writerows(rows)
    new_root = state / f"{report['report_id']}-{new_sha[:10]}-{revision}"
    work = new_root / 'prepared'
    manifest = profile.prepare(master, work, report['report_id'])
    migrated, rerun = [], []
    for new_batch in manifest['batches']:
        old_batch = next(b for b in old_manifest['batches'] if b['id'] == new_batch['id'])
        previous = old_root / 'accepted' / (old_batch['id'] + '.json')
        if not previous.exists():
            continue
        a, b = base.read(old_work / old_batch['file']), base.read(work / new_batch['file'])
        for key in ('source_sha256',):
            a.pop(key, None); b.pop(key, None)
        if a != b:
            rerun.append({'batch_id': new_batch['id'], 'reason': 'source blocks or context changed'})
            continue
        data = base.read(previous)
        data['source_sha256'] = new_sha
        data['derivation'] = {'type': 'unchanged_batch_rebase', 'model_rerun': False,
                              'parent_source_sha256': old_sha, 'parent_response_sha256': base.sha(previous),
                              'basis': 'All batch target/context blocks are byte-identical; source edits are outside this batch.'}
        try:
            profile.check(work, data)
        except ValueError as exc:
            rerun.append({'batch_id': new_batch['id'], 'reason': str(exc)})
            continue
        target = new_root / 'accepted' / previous.name
        target.parent.mkdir(exist_ok=True)
        base.write(target, data)
        migrated.append({'batch_id': new_batch['id'], 'old_response_sha256': base.sha(previous),
                         'new_response_sha256': base.sha(target),
                         'basis': 'Byte-identical batch blocks/context; only whole-document source hash rebased. No model rerun claimed.'})
    result = {'old_source_sha256': old_sha, 'new_source_sha256': new_sha,
              'old_source_frozen': str(frozen), 'prior_cache_preserved': True,
              'unchanged_batches_rebased': migrated, 'requires_model_rerun': rerun}
    base.write(AUDIT / 'Проверка/source_patch_application.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
