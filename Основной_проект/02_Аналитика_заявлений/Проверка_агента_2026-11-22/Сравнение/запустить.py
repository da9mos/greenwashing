"""Replay the frozen six inputs in a new output directory using the saved model settings."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from time import perf_counter

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    cases = [('KMAZ-2024-ОУР', 120), ('ALRS-2024-ОУР', 177), ('PLZL-2025-ИО', 88)]
    for index, (report, page) in enumerate(cases):
        for version in (('old', 'new') if index % 2 == 0 else ('new', 'old')):
            stem = f'{report}-{version}'
            saved = json.loads((HERE / f'{stem}.meta.json').read_text(encoding='utf-8'))
            prompt = (HERE / f'{stem}.prompt.txt').read_text(encoding='utf-8')
            image = HERE.parent / f'{report[:4]}_PDF_{page}.png'
            assert hashlib.sha256(prompt.encode()).hexdigest() == saved['prompt_sha256']
            assert hashlib.sha256(image.read_bytes()).hexdigest() == saved['image_sha256']
            command = [
                'codex', 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
                '--sandbox', 'read-only', '-m', saved['model'],
                '-c', f'model_reasoning_effort="{saved["effort"]}"',
                '-c', 'web_search="disabled"', '-C', str(output),
                '--output-schema', str(HERE / 'schema.json'),
                '-o', str(output / f'{stem}.json'), '-i', str(image), '-',
            ]
            start = perf_counter()
            process = subprocess.run(command, input=prompt, encoding='utf-8',
                                     capture_output=True, timeout=360)
            saved.update(elapsed_seconds=perf_counter() - start, exit_code=process.returncode)
            (output / f'{stem}.log').write_text(process.stdout + '\n' + process.stderr, encoding='utf-8')
            (output / f'{stem}.meta.json').write_text(json.dumps(saved, indent=2) + '\n', encoding='utf-8')
            process.check_returncode()
            print(stem, round(saved['elapsed_seconds'], 2), flush=True)


if __name__ == '__main__':
    main()
