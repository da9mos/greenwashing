"""Global page queue with a shared fatal-dependency stop, never source blame.

Native PDF preparation stays in spawned processes; API threads never prepare PDFs.
A persisted blocked job refuses startup without any provider/balance request.
"""
import argparse
from collections import Counter
import concurrent.futures as futures
import fcntl
import json
import os
import multiprocessing
import queue
import re
import shutil
import threading
import time
import run_models as rm
from run_deepseek_v3 import transcribe, VERSION
from prepare_geometry import prepare_report

DEFERRED = 'deferred_external_dependency'


def dependency_error(exc):
    """Classify provider-wide failures; exception text is not copied as secrets."""
    status = None
    for obj in (exc, getattr(exc, 'response', None)):
        for name in ('status_code', 'status', 'code'):
            candidate = getattr(obj, name, None)
            if str(candidate) in ('401', '402', '403'):
                status = int(candidate)
    text = str(exc).lower()
    if status is None:
        match = re.search(r'\b(?:http|status(?:_code)?)\s*[:=]?\s*(401|402|403)\b', text)
        if match:status = int(match[1])
    balance = bool(re.search(r'insufficient[_\s-]*(?:balance|quota)|balance[_\s-]*(?:unavailable|exhausted)|payment required', text))
    credential = 'credential unavailable' in text
    if status not in (401, 402, 403) and not balance and not credential:return None
    kind = 'balance' if status == 402 or balance else ('auth' if status == 401 or credential else 'access')
    return {'state': DEFERRED, 'kind': kind, 'http_status': status,
            'job_status': 'blocked_deepseek_' + kind,
            'reason': 'Provider-wide '+kind+' dependency; explicit operator resolution required'}


def read_json(path):
    if not path.exists():return {}
    return json.loads(path.read_text())


def persisted_dependency(base):
    job = read_json(base / '_проверка/job.json')
    if str(job.get('status', '')).startswith('blocked_deepseek_'):
        kind = job['status'].removeprefix('blocked_deepseek_')
        return {'state': DEFERRED, 'kind': kind, 'job_status': job['status'],
                'reason': 'Persisted blocked job; no API preflight or automatic resume'}
    control = read_json(base / '_проверка/deepseek_controller.json')
    if (control.get('dependency') or {}).get('state') == DEFERRED:
        return control['dependency']
    return None


def record_fatal_job(base, reason):
    path = base / '_проверка/job.json';job = read_json(path)
    # An obsolete worker must not overwrite a newly launched controller's job.
    if job.get('pid') not in (None, os.getpid()):return
    job.update(status=reason['job_status'], dependency=reason, stopped_at=time.time())
    rm.put_json(path, job)


class FatalStop:
    def __init__(self, on_fatal=None):
        self.event = threading.Event();self.lock = threading.Lock()
        self.reason = None;self.on_fatal = on_fatal

    def trip(self, reason):
        with self.lock:
            if self.event.is_set():return
            self.reason = dict(reason);self.event.set()
        if self.on_fatal:self.on_fatal(self.reason)

    def deferred(self, attempts=0):
        return {'success': False, 'state': DEFERRED, 'attempts': attempts,
                'dependency': self.reason}


_FALLBACK_STOP = FatalStop()


def attempt_page(row, item, max_attempts, stop=None):
    if stop is None:
        stop = _FALLBACK_STOP
        dependency = persisted_dependency(rm.BASE)
        if dependency:stop.trip(dependency)
    folder = rm.BASE / '_проверка/DeepSeek' / row['report_id'] / VERSION
    filename = f"page_{item['pdf_page']:04d}.json"
    errors = []
    for attempt in range(1, max_attempts + 1):
        if stop.event.is_set():return stop.deferred(attempt - 1)
        raw = folder / 'raw' / filename
        if raw.exists() and not (folder / filename).exists():
            history = folder / 'raw_history' / f"{raw.stem}_{time.time_ns()}.json"
            history.parent.mkdir(parents=True, exist_ok=True);shutil.copy2(raw, history)
        try:
            if stop.event.is_set():return stop.deferred(attempt - 1)
            result = transcribe(row, item)
            # A success already in flight is kept even if another thread blocked.
            return {'success': True, 'review_status': result['review_status'], 'model': result['model'],
                    'attempts': attempt, 'usage': result.get('usage')}
        except Exception as exc:
            fatal = dependency_error(exc)
            if fatal:
                stop.trip(fatal)
                return stop.deferred(attempt)
            if stop.event.is_set():return stop.deferred(attempt)
            errors.append({'attempt': attempt, 'type': type(exc).__name__, 'error': str(exc)[:1500]})
            rm.put_json(folder / 'errors' / filename, {'pdf_page': item['pdf_page'], 'errors': errors})
            rm.log('PAGE ERROR', row['report_id'], item['pdf_page'], type(exc).__name__, 'attempt', attempt)
            if isinstance(exc, ValueError) and 'Different source or prompt' in str(exc):break
            if attempt < max_attempts and stop.event.wait(min(10, 2 * attempt)):
                return stop.deferred(attempt)
    return {'success': False, 'attempts': len(errors), 'errors': errors}


def saved_response_pages(base, rid):
    """Already saved successful API responses, not a checked/assembly claim."""
    result=[]
    for path in (base / '_проверка/DeepSeek' / rid / VERSION).glob('page_*.json'):
        match=re.fullmatch(r'page_(\d{4})\.json',path.name)
        if not match:continue
        try:record=read_json(path)
        except (ValueError,OSError):continue
        if not isinstance(record,dict):continue
        answer=record.get('response',{})
        if not isinstance(answer,dict):continue
        if (record.get('instruction_sha256')==rm.INSTRUCTION_SHA and
            answer.get('pdf_page')==int(match[1]) and isinstance(answer.get('markdown'),str)):
            result.append(int(match[1]))
    return sorted(result)


def starting_states(rows, base, dependency=None):
    previous = read_json(base / '_проверка/deepseek_controller.json').get('reports', {}) if dependency else {}
    manifest = read_json(base / '_проверка/sources_manifest.json')
    expected = {r['report_id']:r.get('pages') for r in manifest.get('reports', [])}
    states = {}
    for row in rows:
        rid = row['report_id'];state = dict(previous.get(rid, {}))
        state.setdefault('pages_done', 0);state.setdefault('page_errors', [])
        state.setdefault('pages_pending_review', []);state.setdefault('pages_successful', [])
        state.setdefault('pages_deferred_external_dependency', [])
        if expected.get(rid):state.setdefault('pages_expected', int(expected[rid]))
        if not state.get('assembled'):
            state['stage'] = DEFERRED if dependency else 'preparing'
            if dependency:
                state['dependency'] = dependency
                state['responses_already_saved']=saved_response_pages(base,rid)
                done=set(state['responses_already_saved']) | set(state.get('pages_successful',[])) | set(state.get('page_errors',[]))
                state['pages_deferred_external_dependency']=[n for n in range(1,state.get('pages_expected',0)+1) if n not in done]
        states[rid] = state
    return states


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=64)
    parser.add_argument('--prepare-workers', type=int, default=2)
    parser.add_argument('--attempts', type=int, default=2)
    parser.add_argument('--reports', nargs='*')
    args = parser.parse_args(argv)
    if min(args.workers, args.prepare_workers, args.attempts) < 1:parser.error('Counts must be positive')
    rows = [r for r in rm.ROWS if not args.reports or r['report_id'] in args.reports]
    if args.reports and set(args.reports) - {r['report_id'] for r in rm.ROWS}:parser.error('Unknown report ID')
    # Local guard before pools, PDF preparation, Client construction or API calls.
    dependency = persisted_dependency(rm.BASE)
    started = time.time();states = starting_states(rows, rm.BASE, dependency)
    state_file = rm.BASE / '_проверка/deepseek_controller.json'
    models = Counter();usage = Counter()
    stop = FatalStop(lambda reason:record_fatal_job(rm.BASE, reason))
    if dependency:stop.trip(dependency)

    def save(ended=False):
        counts = {'reports_requested': len(rows),
                  'reports_assembled': sum(bool(x.get('assembled')) for x in states.values()),
                  'pages_done': sum(x['pages_done'] for x in states.values()),
                  'page_failures': sum(len(x['page_errors']) for x in states.values()),
                  'pages_deferred_external_dependency': sum(len(x['pages_deferred_external_dependency']) for x in states.values()),
                  'reports_deferred_external_dependency': sum(x.get('stage') == DEFERRED for x in states.values()),
                  'reports_pending': sum(x.get('stage') != 'assembled' for x in states.values())}
        rm.put_json(state_file, {'pid': os.getpid(), 'version': VERSION, 'started_at': started,
                    'updated_at': time.time(), 'finished_at': time.time() if ended else None,
                    'status': 'blocked_external_dependency' if stop.event.is_set() else ('ended' if ended else 'running'),
                    'dependency': stop.reason, 'workers': args.workers, 'counts': counts,
                    'reports': states, 'models': dict(models),
                    'usage_of_responses_including_cached': dict(usage), 'instruction_sha256': rm.INSTRUCTION_SHA,
                    'quality_scope': 'Structural assembly; external dependency is not a PDF/source failure; not checked'})

    if dependency:
        save(ended=True)
        rm.log('DEEPSEEK DEFERRED', dependency['kind'], 'no API requests; explicit resolution required')
        raise SystemExit(3)
    lock = (rm.BASE / '_проверка/deepseek_controller.lock').open('w')
    try:fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close();raise SystemExit('A corpus controller is already running')
    try:
        rm.RUN_VERSION = VERSION
        events = queue.Queue();indexes = {};by_id = {r['report_id']: r for r in rows}
        preparation_left = len(rows);pages_left = 0;api_jobs = [];prep_jobs = [];cancelled = False
        save()
        with futures.ProcessPoolExecutor(max_workers=args.prepare_workers, mp_context=multiprocessing.get_context('spawn')) as prep, futures.ThreadPoolExecutor(max_workers=args.workers) as api:
            for row in rows:
                future = prep.submit(prepare_report, row);prep_jobs.append(future)
                future.add_done_callback(lambda f, rid=row['report_id']: events.put(('prepared', rid, None, f)))
            while preparation_left or pages_left:
                kind, rid, item, future = events.get()
                if stop.event.is_set() and not cancelled:
                    cancelled = True
                    for job in api_jobs + prep_jobs:job.cancel()
                    for report_id,state in states.items():
                        if not state.get('assembled') and state.get('stage') != 'source_error':
                            state.update(stage=DEFERRED, dependency=stop.reason)
                            state['responses_already_saved']=saved_response_pages(rm.BASE,report_id)
                            done=set(state['responses_already_saved']) | set(state.get('pages_successful',[])) | set(state.get('page_errors',[]))
                            state['pages_deferred_external_dependency']=[n for n in range(1,state.get('pages_expected',0)+1) if n not in done]
                if kind == 'prepared':
                    preparation_left -= 1
                    try:
                        index = future.result();indexes[rid] = index
                        states[rid]['pages_expected'] = len(index['pages'])
                        if stop.event.is_set():
                            states[rid].update(stage=DEFERRED, dependency=stop.reason)
                            already=set(states[rid].get('responses_already_saved',[])) | set(saved_response_pages(rm.BASE,rid))
                            states[rid]['pages_deferred_external_dependency'] = [p['pdf_page'] for p in index['pages'] if p['pdf_page'] not in already]
                            continue
                        states[rid]['stage'] = 'converting'
                        for page in index['pages']:
                            if stop.event.is_set():
                                states[rid].update(stage=DEFERRED, dependency=stop.reason)
                                states[rid]['pages_deferred_external_dependency'].append(page['pdf_page']);continue
                            job = api.submit(attempt_page, by_id[rid], page, args.attempts, stop)
                            pages_left += 1;api_jobs.append(job)
                            job.add_done_callback(lambda f, report_id=rid, p=page: events.put(('page', report_id, p, f)))
                    except futures.CancelledError:
                        states[rid].update(stage=DEFERRED, dependency=stop.reason)
                    except Exception as exc:
                        states[rid].update(stage='source_error', error=str(exc)[:1500])
                else:
                    pages_left -= 1
                    try:result = future.result()
                    except futures.CancelledError:result = stop.deferred()
                    state = states[rid]
                    if result.get('state') == DEFERRED:
                        state.update(stage=DEFERRED, dependency=stop.reason)
                        if item['pdf_page'] not in state['pages_deferred_external_dependency'] and item['pdf_page'] not in state.get('responses_already_saved',[]):
                            state['pages_deferred_external_dependency'].append(item['pdf_page'])
                    else:
                        if item['pdf_page'] in state['pages_deferred_external_dependency']:
                            state['pages_deferred_external_dependency'].remove(item['pdf_page'])
                        state['pages_done'] += 1
                        if not result['success']:state['page_errors'].append(item['pdf_page'])
                        else:
                            state['pages_successful'].append(item['pdf_page']);models[result['model']] += 1
                            for key, value in (result.get('usage') or {}).items():
                                if isinstance(value, (int, float)):usage[key] += value
                            if result['review_status'] == 'pending':state['pages_pending_review'].append(item['pdf_page'])
                        if state['pages_done'] == state['pages_expected']:
                            if not state['page_errors']:
                                try:
                                    state['assembled'] = rm.assemble_deepseek(by_id[rid], indexes[rid])
                                    state['stage'] = 'assembled' if state['assembled'] else 'structural_issues'
                                except Exception as exc:state.update(stage='assembly_error', error=str(exc)[:1500])
                            else:state['stage'] = 'incomplete'
                            rm.log('REPORT', rid, state['stage'], 'pages', state['pages_done'])
                save()
        save(ended=True)
        complete = not stop.event.is_set() and all(s.get('assembled') for s in states.values())
        rm.put_json(rm.BASE / '_проверка/deepseek_run_summary.json', {
            'status': 'blocked_external_dependency' if stop.event.is_set() else 'ended',
            'dependency': stop.reason, 'all_requested_reports_assembled': complete,
            'reports_requested': len(rows), 'reports': states, 'instruction_sha256': rm.INSTRUCTION_SHA,
            'full_source_fidelity_verified': False})
        rm.log('DEEPSEEK CORPUS ENDED', 'all_assembled', complete)
        if not complete:raise SystemExit(3 if stop.event.is_set() else 2)

    finally:
        lock.close()


if __name__ == '__main__':main()
