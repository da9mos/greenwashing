"""Keep the local status current while the explicitly requested batch runs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent.parent
TOOLS = BASE / 'tools'


def invoke(name):
    result = subprocess.run([sys.executable, str(TOOLS / name)], cwd=BASE,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(time.strftime('%Y-%m-%d %H:%M:%S'), name, result.returncode,
          result.stdout[-1200:], flush=True)
    return result.returncode


def final_job_state(current, monitored_pid, summary=None, timestamp=None):
    """End the monitor, not a blocked external dependency; never use stale job."""
    if current.get('pid') != monitored_pid:return None
    result=dict(current);now=time.time() if timestamp is None else timestamp
    if str(current.get('status','')).startswith('blocked_'):
        result['monitor_ended_at']=now
        return result
    result['status']='ended_pending_review'
    if summary is not None:
        result['status']='ended' if summary.get('overall_complete') else 'ended_with_pending'
    result['ended_at']=now
    return result


def main():
    job = json.loads((BASE / '_проверка/job.json').read_text())
    pid = job['pid']
    codex_state = BASE / '_проверка/codex_controller.json'
    last_outputs = None
    while True:
        invoke('reassemble_ready.py')
        patch_file = BASE / '_проверка/patches_gazprom2023.json'
        if patch_file.exists() and (BASE / '_проверка/source_corrections_applied.json').exists():
            result = subprocess.run([sys.executable, str(TOOLS / 'apply_verified_patches.py'), str(patch_file)],
                                    cwd=BASE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if result.returncode:
                print('Source-correction projection needs review:', result.stdout[-1200:], flush=True)
        outputs = list((BASE / 'DeepSeek').glob('*/*/report.md')) + list((BASE / 'Codex').glob('*/*/report.md'))
        outputs += list((BASE / '_проверка/DeepSeek').glob('*/assembled.json'))
        outputs += list((BASE / '_проверка/Codex').glob('*/v2/receipt.json'))
        stamp = tuple(sorted((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in outputs))
        if stamp and stamp != last_outputs:
            invoke('compare_results.py')
            invoke('render_results.py')
            last_outputs = stamp
        invoke('update_status.py')
        current = json.loads((BASE / '_проверка/job.json').read_text())
        if current['pid'] != pid:
            print('A new controller has replaced this monitored run', flush=True)
            return
        pids = [pid]
        if codex_state.exists():
            info = json.loads(codex_state.read_text())
            if info.get('pid'):
                pids.append(info['pid'])
        active = False
        for target in pids:
            try:
                os.kill(target, 0)
                active = True
            except ProcessLookupError:
                pass
        if not active:
            break
        time.sleep(30)
    invoke('compare_results.py')
    invoke('update_status.py')
    current = json.loads((BASE / '_проверка/job.json').read_text())
    if current['pid'] != pid:
        return
    summary = BASE / '_проверка/run_summary.json'
    result = json.loads(summary.read_text()) if summary.exists() else None
    final = final_job_state(current, pid, result)
    if final is None:return
    path=BASE / '_проверка/job.json'
    temporary=path.with_name(path.name+f'.monitor-{os.getpid()}.part')
    temporary.write_text(json.dumps(final, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


if __name__ == '__main__':
    main()
