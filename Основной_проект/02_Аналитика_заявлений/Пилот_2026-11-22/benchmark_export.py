import importlib
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter

BASELINE = 'c5ec4426bd7e9a5c0ec740f92c37c8a40c929f84'
project = Path(__file__).resolve().parents[2]
repo = project.parent
scripts = next(project.glob('02*/Агент/scripts'))
agent = scripts.parent
prefix = scripts.relative_to(repo).as_posix()
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    for name in ('esg_agent_v3', 'esg_agent_v3_1'):
        content = subprocess.check_output(['git', '-C', str(repo), 'show', f'{BASELINE}:{prefix}/{name}.py'])
        (root / f'{name}.py').write_bytes(content)
    sys.path.insert(0, str(root))
    old = importlib.import_module('esg_agent_v3_1')
    sys.path[0] = str(scripts)
    for name in ('esg_agent_v3', 'esg_agent_v3_1'):
        del sys.modules[name]
    new = importlib.import_module('esg_agent_v3_1')
    for company in ('NORN', 'LKOH', 'CHMF'):
        source = next(project.glob(f'00*/*/{company}-2023-ОУР.md'))
        work = root / company
        manifest = new.prepare(source, work, source.stem)
        responses = []
        for entry in manifest['batches']:
            batch = new.base.read(work / entry['file'])
            responses.append(dict(
                schema_version=new.base.VERSION,
                batch_id=entry['id'],
                source_sha256=manifest['source_sha256'],
                reviewer='technical timing fixture',
                claims=[],
                coverage=[dict(block_id=block, status='pending', claim_ids=[], reason='fixture')
                          for block in batch['target_block_ids']],
            ))
        measures = {old: [], new: []}
        for repeat in range(3):
            for version in ((old, new) if repeat != 1 else (new, old)):
                start = perf_counter()
                out, summary = version.export(work, responses, root / f'{company}-{id(version)}-{repeat}', True)
                measures[version].append(perf_counter() - start)
                assert summary['claims'] == 0
                assert summary['pending_blocks'] == len(new.base.read(work / 'blocks.json'))
                if version is old:
                    old_data = new.base.read(out / 'claims.json')
                else:
                    new_data = new.base.read(out / 'claims.json')
            assert old_data == new_data
        print(company, len(manifest['batches']),
              *(round(statistics.median(measures[version]), 3) for version in (old, new)), flush=True)
