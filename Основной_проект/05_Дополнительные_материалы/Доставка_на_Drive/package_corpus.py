from pathlib import Path
import json,zipfile,hashlib
base=Path(__file__).parent
rows=json.loads((base/'inventory.json').read_text())
out=base/'Пакеты_отчётов';out.mkdir(exist_ok=True)
manifest=[]
for row in rows:
    source=Path(row['source']); dest=out/(row['report']+'.zip')
    files=[source]+sorted(p for p in (source.parent/'assets').rglob('*') if p.is_file())
    if not dest.exists():
        with zipfile.ZipFile(dest,'w',allowZip64=True) as z:
            for p in files:
                z.write(p,Path(row['report'])/p.relative_to(source.parent),compress_type=zipfile.ZIP_DEFLATED if p.suffix=='.md' else zipfile.ZIP_STORED)
    with zipfile.ZipFile(dest) as z:
        assert len(z.infolist())==len(files)
    parts=[]
    if dest.stat().st_size<=100_000_000:
        parts=[str(dest.resolve())]
    else:
        groups=[[]]; total=0
        for p in files:
            size=p.stat().st_size
            assert size<90_000_000,str(p)
            if total+size>90_000_000:
                groups.append([]);total=0
            groups[-1].append(p);total+=size
        for n,group in enumerate(groups,1):
            part=out/(row['report']+f'.part{n:02d}.zip')
            if not part.exists():
                with zipfile.ZipFile(part,'w') as z:
                    for p in group:
                        z.write(p,Path(row['report'])/p.relative_to(source.parent),compress_type=zipfile.ZIP_DEFLATED if p.suffix=='.md' else zipfile.ZIP_STORED)
            assert part.stat().st_size<100_000_000
            parts.append(str(part.resolve()))
    manifest.append({**row,'archive':str(dest.resolve()),'parts':parts,'archive_bytes':dest.stat().st_size,'sha256':hashlib.file_digest(dest.open('rb'),'sha256').hexdigest()})
    (base/'packages.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(row['report'],dest.stat().st_size,flush=True)
