"""Rebuild completed DeepSeek bundles from immutable answers; no model calls."""
import json
from pathlib import Path
import run_models as runner


def main():
    job_file = runner.BASE / '_проверка/job.json'
    if job_file.exists():
        job = json.loads(job_file.read_text())
        runner.RUN_VERSION = job.get('DeepSeek_version', runner.RUN_VERSION)
    for row in runner.ROWS:
        rid = row['report_id']
        meta_file = runner.BASE / '_проверка/DeepSeek' / rid / 'assembled.json'
        if not meta_file.exists():
            continue
        meta = json.loads(meta_file.read_text())
        if meta.get('assembly_version') == 3:
            continue
        index = json.loads((runner.BASE / '_проверка/входы' / rid / 'pages.json').read_text())
        valid = True
        for item in index['pages']:
            file = runner.BASE / '_проверка/DeepSeek' / rid / runner.RUN_VERSION / f"page_{item['pdf_page']:04d}.json"
            if not file.exists():
                valid = False
                break
            answer = json.loads(file.read_text())
            sig = answer.get('request_signature', {})
            if (answer.get('instruction_sha256') != runner.INSTRUCTION_SHA
                    or sig.get('image_sha256') != runner.sha(runner.BASE / item['image'])
                    or sig.get('packet_sha256') != runner.sha(runner.BASE / item['packet'])
                    or answer.get('response', {}).get('pdf_page') != item['pdf_page']):
                valid = False
                break
        if valid:
            print(rid, 'assembled', runner.assemble_deepseek(row, index))


if __name__ == '__main__':
    main()
