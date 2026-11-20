"""Managed launch: persist the actual process exit, including native crashes."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent.parent


def main():
    job_file = BASE / '_проверка/job.json'
    job = json.loads(job_file.read_text())
    output = (BASE / '_проверка/deepseek_corpus.log').open('a')
    command = [sys.executable, '-u', str(BASE / 'tools/run_deepseek_corpus.py'),
               '--workers', '64', '--prepare-workers', '3']
    process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
    job.update(pid=process.pid, started_at=time.time(), status='running',
               controller='global_page_queue_process_isolated_pdf', workers=64, prepare_workers=3,
               command='python3 tools/run_deepseek_corpus.py --workers 64 --prepare-workers 3')
    job_file.write_text(json.dumps(job, ensure_ascii=False, indent=2) + '\n')
    monitor_file = BASE / '_проверка/monitor_job.json'
    if monitor_file.exists():
        try:
            os.kill(json.loads(monitor_file.read_text())['pid'], signal.SIGTERM)
        except ProcessLookupError:
            pass
    monitor_log = (BASE / '_проверка/monitor.log').open('a')
    monitor = subprocess.Popen([sys.executable, '-u', str(BASE / 'tools/monitor_run.py')],
                               stdout=monitor_log, stderr=subprocess.STDOUT, start_new_session=True)
    monitor_file.write_text(json.dumps({'pid': monitor.pid, 'started_at': time.time()}, indent=2) + '\n')
    print('Started', process.pid, 'PDF processing:3isolated processes; API requests:64threads', flush=True)
    code = process.wait()
    receipt = {'pid': process.pid, 'returncode': code, 'finished_at': time.time(),
               'normal_exit': code >= 0, 'signal': -code if code < 0 else None}
    (BASE / '_проверка/deepseek_process_exit.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)
    raise SystemExit(code if code >= 0 else 128 - code)


if __name__ == '__main__':
    main()
