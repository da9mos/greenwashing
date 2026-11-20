"""Resume the existing extraction cache locally and publish honest corpus summaries."""
import argparse
from collections import Counter
from copy import deepcopy
from contextlib import contextmanager
import csv
from datetime import datetime
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import time
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
PLATFORM = PROJECT.parent.parents[1] / '4_итерация/ESG_платформа'
if not (PLATFORM / 'worker.py').exists():
    PLATFORM = PROJECT / '05_Дополнительные_материалы/ESG_платформа'
spec = importlib.util.spec_from_file_location('sber_existing_worker', PLATFORM / 'worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
STATE = Path.home() / '.local/state/sber-esg-worker'
CONTROL = Path.home() / '.local/state/sber-corpus-run-20261120'
OUTPUT = PROJECT / '04_Итоги_проверки'


def now():
    return datetime.now(ZoneInfo('Asia/Yekaterinburg')).isoformat(timespec='seconds')


def atomic(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def registry():
    return worker.base.read(PROJECT / '00_Отчёты/manifest.json')


def cache_for(report):
    revision = worker.base.sha(worker.AGENT / 'agent/esg_agent_v3_1.md')[:10]
    return STATE / f"{report['report_id']}-{report['packaged_md_sha256'][:10]}-{revision}"


def extraction_status(total, accepted, pending, invalid, pending_classifications=0):
    if invalid:
        return 'Требуется разбор отклонённых ответов'
    if not accepted:
        return 'Партии подготовлены, извлечение не выполнено'
    if accepted < total:
        return 'Частичное извлечение'
    if pending_classifications:
        return 'Извлечение выполнено, есть неоднозначные классификации'
    if pending:
        return 'Извлечение выполнено, есть открытые блоки/PDF'
    return 'Охват MD заявлен; независимая сверка и фактчекинг открыты'


def canonical_batch(data):
    """Namespace batch-local IDs in derived exports without editing model originals."""
    result = deepcopy(data)
    mapping = {c['id']: f"{data['batch_id']}::{c['id']}" for c in data['claims']}
    provenance = []
    for claim in result['claims']:
        original = claim['id']
        claim['id'] = mapping[original]
        provenance.append({'id': claim['id'], 'original_id': original, 'batch_id': data['batch_id']})
    for block in result['coverage']:
        block['claim_ids'] = [mapping[x] for x in block['claim_ids']]
    return result, provenance


def research_path(report, claim):
    identity = json.dumps([report['packaged_md_sha256'], claim['id'], claim['statement']], ensure_ascii=False)
    key = __import__('hashlib').sha256(identity.encode()).hexdigest()
    return OUTPUT / report['company'] / 'Текущий_прогон/Фактчекинг' / report['report_id'] / (key + '.json')


def source_review_for(report, claim):
    proof = PROJECT / '08_Аудит_агентов_2026-11-20/01_PDF/patch_review.json'
    if not proof.exists():
        return None
    data = worker.base.read(proof)
    if data.get('patched_output', {}).get('sha256') != report['packaged_md_sha256']:
        return None
    for item in data.get('claims', []):
        if item.get('status') == 'verified' and item.get('output_locator', {}).get('excerpt') == claim['statement']:
            return {'status': 'verified', 'method': item['method'],
                    'locator': json.dumps(item['source_locator'], ensure_ascii=False),
                    'proof_file': str(proof.relative_to(PROJECT)), 'proof_sha256': worker.base.sha(proof)}
    return None


def research_step():
    """Execute the existing project fact agent on an accepted claim without waiting for the entire corpus."""
    for report in registry():
        _, data = inspect_report(report)
        for claim in data['claims']:
            path = research_path(report, claim)
            if path.exists():
                previous = worker.base.read(path)
                if previous['result'].get('status') == 'complete' or previous.get('retry_after_epoch', 0) > time.time():
                    continue
            state = {'state': 'researching', 'report_id': report['report_id'], 'claim_id': claim['id'],
                     'updated_at': now(), 'pid': os.getpid(), 'project_agent': '03_Фактчекинг/Агент/FACT_CHECK_AGENT.md'}
            atomic(CONTROL / 'current.json', state)
            snapshot(state)
            result = worker.search_claim({'report': report, 'claim': claim, 'source_review': source_review_for(report, claim)})
            atomic(path, {'report_id': report['report_id'], 'claim_id': claim['id'],
                          'source_sha256': report['packaged_md_sha256'], 'updated_at': now(), 'result': result,
                          'retry_after_epoch': 0 if result.get('status') == 'complete' else time.time() + 3600})
            finished = {'state': 'research_complete' if result.get('status') == 'complete' else 'research_open',
                        'report_id': report['report_id'], 'claim_id': claim['id'], 'updated_at': now()}
            atomic(CONTROL / 'current.json', finished)
            snapshot(finished)
            return True
    return False


def inspect_report(report):
    source = PROJECT / report['repository_path']
    if worker.base.sha(source) != report['packaged_md_sha256']:
        raise ValueError(f"{report['report_id']}: changed source")
    root = cache_for(report)
    work = root / 'prepared'
    if not work.exists():
        root.mkdir(parents=True, exist_ok=True)
        worker.profile.prepare(source, work, report['report_id'])
    manifest, _ = worker.base.workspace(work)
    worker.profile.policy_for(work)
    if manifest['source_sha256'] != report['packaged_md_sha256']:
        raise ValueError('Cached source version mismatch')
    claims, coverage, accepted, invalid, ids, id_provenance = [], [], [], [], set(), []
    pending_claims = pending_classifications = 0
    for batch in manifest['batches']:
        path = root / 'accepted' / (batch['id'] + '.json')
        published = OUTPUT / report['company'] / 'Текущий_прогон/Ответы' / report['packaged_md_sha256'][:12] / (batch['id'] + '.json')
        legacy = published.parent.parent / published.name
        candidate = published if published.exists() else legacy
        if not path.exists() and candidate.exists():
            saved = worker.base.read(candidate)
            if saved.get('source_sha256') == report['packaged_md_sha256']:
                try:
                    worker.profile.check(work, candidate)
                except (ValueError, KeyError, TypeError) as exc:
                    invalid.append({'batch_id': batch['id'], 'error': str(exc)})
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(candidate.read_bytes())
        if not path.exists():
            continue
        try:
            data, summary = worker.profile.check(work, path)
            data, mapping = canonical_batch(data)
            new_ids = [c['id'] for c in data['claims']]
            if ids.intersection(new_ids):
                raise ValueError('Duplicate claim ID across batches')
            ids.update(new_ids)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            invalid.append({'batch_id': batch['id'], 'error': str(exc)})
            continue
        claims.extend(data['claims'])
        id_provenance.extend(mapping)
        coverage.extend(data['coverage'])
        pending_claims += summary['pending_claims']
        pending_classifications += summary['pending_classifications']
        accepted.append(batch['id'])
        published.parent.mkdir(parents=True, exist_ok=True)
        published.write_bytes(path.read_bytes())
    pending_blocks = sum(c['status'] == 'pending' for c in coverage)
    total = len(manifest['batches'])
    researched = [worker.base.read(p) for c in claims if (p := research_path(report, c)).exists()]
    finished = sum(p['result'].get('status') == 'complete' for p in researched)
    result = {
        'report_id': report['report_id'], 'company': report['company'],
        'company_id': report['company_id'], 'pages': report['physical_pages'],
        'source_sha256': report['packaged_md_sha256'],
        'profile_sha256': manifest['prompt_sha256'], 'total_batches': total,
        'accepted_batches': len(accepted), 'candidate_claims': len(claims),
        'pending_blocks': pending_blocks, 'pending_claims': pending_claims,
        'pending_classifications': pending_classifications,
        'research_attempted': len(researched), 'research_finished': finished,
        'invalid_batches': invalid, 'accepted_batch_ids': accepted,
        'esg_counts': dict(Counter(c['block'] for c in claims)),
        'type_counts': dict(Counter(c['type'] for c in claims)),
        'status': extraction_status(total, len(accepted), pending_blocks + pending_claims, invalid,
                                    pending_classifications),
        'pdf_review': 'Полная независимая сверка не подтверждена',
        'factcheck': f'Внешнее исследование: {finished}/{len(claims)} кандидатов; приёмка корпуса открыта',
    }
    return result, {'report_id': report['report_id'], 'source_sha256': report['packaged_md_sha256'],
                    'accepted_batch_ids': accepted, 'expected_batches': total,
                    'complete': False, 'claims': claims, 'coverage': coverage,
                    'id_provenance': id_provenance,
                    'limitation': 'Partial MD extraction; PDF review, semantic recall and external verification remain open.'}


def snapshot(control=None):
    reports, by_company = [], {}
    for report in registry():
        summary, data = inspect_report(report)
        reports.append(summary)
        company = by_company.setdefault(report['company_id'], {'name': report['company'], 'reports': []})
        company['reports'].append(summary)
        target = OUTPUT / report['company'] / 'Текущий_прогон'
        atomic(target / (report['report_id'] + '.json'), data)
    stamp = now()
    totals = {key: sum(r[key] for r in reports) for key in
              ('pages', 'total_batches', 'accepted_batches', 'candidate_claims', 'pending_blocks', 'pending_claims',
               'pending_classifications')}
    totals.update({key: sum(r.get(key, 0) for r in reports) for key in ('research_attempted', 'research_finished')})
    payload = {'updated_at': stamp, 'companies': len(by_company), 'reports': len(reports),
               'totals': totals, 'control': control or {}, 'report_status': reports}
    atomic(HERE / 'status.json', payload)
    for company in by_company.values():
        rows = company['reports']
        lines = [f"# Сводка — {company['name']}", '', f'Обновлено: {stamp}.', '',
                 'Рабочий результат. Кандидатное заявление не означает подтверждённый факт. '
                 'Полная сверка с PDF, независимая полнота и массовый фактчекинг остаются открытыми.', '',
                 '| Отчёт | Страниц | Принято партий | Кандидатов | Открытых блоков | Требуют PDF | Неоднозначных классификаций | Внешних исследований | Статус |',
                 '|---|---:|---:|---:|---:|---:|---:|---:|---|']
        for row in rows:
            lines.append(f"| {row['report_id']} | {row['pages']} | {row['accepted_batches']}/{row['total_batches']} | "
                         f"{row['candidate_claims']} | {row['pending_blocks']} | {row['pending_claims']} | "
                         f"{row['pending_classifications']} | {row.get('research_finished', 0)} | {row['status']} |")
        lines += ['', 'Открытые блоки посчитаны только в принятых партиях; непройденные партии в этот счётчик не входят.', '',
                  '[Данные текущего прогона](Текущий_прогон/). Сохранены точные цитаты, страницы, тип, E/S/G, '
                  'числовой контекст и основания методики. Прежние пилотные Excel/CSV сохранены отдельно.', '']
        path = OUTPUT / company['name'] / 'Сводка_компании.md'
        path.write_text('\n'.join(lines))
        readme = path.with_name('README.md')
        if readme.exists():
            text = readme.read_text()
            marker = '> Актуальный статус: [сводка компании](Сводка_компании.md). '
            if marker not in text:
                pos = text.find('\n') + 1
                text = text[:pos] + '\n' + marker + 'Ниже сохранены сведения прежнего пилота/подготовки.\n' + text[pos:]
                readme.write_text(text)
    fields = ['report_id', 'company', 'pages', 'total_batches', 'accepted_batches', 'candidate_claims',
              'pending_blocks', 'pending_claims', 'pending_classifications', 'research_attempted', 'research_finished', 'status', 'pdf_review', 'factcheck']
    with (HERE / 'Сводка_прогона.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=';', extrasaction='ignore')
        writer.writeheader(); writer.writerows(reports)
    return payload


@contextmanager
def exclusive():
    CONTROL.mkdir(parents=True, exist_ok=True)
    with (CONTROL / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def run(watch, stage='all'):
    with exclusive():
        # One executor owns the shared accepted cache. The existing SSH worker obeys this pause.
        (STATE / 'PAUSED').write_text('Local corpus controller owns extraction; see 06_Прогон_корпуса.\n')
        failures = 0
        blocked_reports = {}
        turn = 1 if stage == 'all' else 0
        while not (CONTROL / 'STOP').exists():
            status = snapshot({'state': 'selecting', 'pid': os.getpid(), 'validation_blocks': blocked_reports})
            todo = next((r for r in status['report_status']
                         if r['accepted_batches'] < r['total_batches'] and r['report_id'] not in blocked_reports), None)
            if stage == 'factcheck' or (stage == 'all' and (turn % 2 or not todo)):
                if research_step():
                    turn += 1
                    if not watch:
                        return
                    continue
                if stage == 'factcheck':
                    snapshot({'state': 'research_queue_waiting', 'updated_at': now(),
                              'next_required': 'New accepted claims or review of partial/blocked research.'})
                    return
            if not todo:
                snapshot({'state': 'awaiting_quality_review', 'validation_blocks': blocked_reports,
                          'next_required': 'Independent PDF/semantic review and external fact-checking before final exports.'})
                return
            report = next(r for r in registry() if r['report_id'] == todo['report_id'])
            root = cache_for(report)
            attempt = CONTROL / 'attempts' / report['report_id'] / str(time.time_ns())
            attempt.mkdir(parents=True)
            old = root / 'model/response.json'
            if old.exists():
                shutil.copy2(old, attempt / 'previous_response.json')
            atomic(CONTROL / 'current.json', {'state': 'extracting', 'report_id': report['report_id'], 'updated_at': now()})
            try:
                result = worker.process(report, 1, batch_timeout=900)
            except Exception as exc:
                result = {'status': 'failed', 'reason': f'{type(exc).__name__}: {exc}', 'processed': todo['accepted_batches']}
            if old.exists():
                shutil.copy2(old, attempt / 'response.json')
            atomic(attempt / 'result.json', result)
            turn += 1
            after, _ = inspect_report(report)
            if after['accepted_batches'] > todo['accepted_batches']:
                failures = 0
                snapshot({'state': 'running', 'last_report': report['report_id'], 'updated_at': now()})
                print(f"{now()} {report['report_id']}: {after['accepted_batches']}/{after['total_batches']}", flush=True)
            else:
                failures += 1
                logs = sorted(root.glob('*.log'), key=lambda p: p.stat().st_mtime)
                tail = logs[-1].read_text(errors='replace')[-20000:] if logs else ''
                network = bool(re.search(r'reconnect|timed? ?out|routing discovery|403 Forbidden|401 Unauthorized|connection|stream disconnected', tail, re.I))
                reason = 'model_connection_unavailable' if network else 'response_validation_failed'
                if not network:
                    blocked_reports[report['report_id']] = reason
                delay = min(300, 30 * 2 ** min(failures - 1, 4))
                state = {'state': 'waiting_for_model' if network else 'validation_block',
                         'report_id': report['report_id'], 'reason': reason,
                         'retry_seconds': delay, 'updated_at': now(), 'pid': os.getpid()}
                atomic(CONTROL / 'current.json', state)
                snapshot(state)
                print(json.dumps(state, ensure_ascii=False), flush=True)
                if watch and network:
                    time.sleep(delay)
            if not watch:
                return
        stopped = {'state': 'stopped_by_control_file', 'updated_at': now()}
        atomic(CONTROL / 'current.json', stopped)
        snapshot(stopped)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', action='store_true')
    p.add_argument('--watch', action='store_true')
    p.add_argument('--stage', choices=['all', 'extraction', 'factcheck'], default='all')
    args = p.parse_args()
    if args.run:
        run(args.watch, args.stage)
    else:
        s = snapshot({'state': 'prepared', 'updated_at': now()})
        print(json.dumps({'companies': s['companies'], 'reports': s['reports'], **s['totals']}, ensure_ascii=False))
