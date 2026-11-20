from pathlib import Path
import zipfile,json,hashlib
base=Path(__file__).parent
source=base.parent/'Итоговый проект'
dest=base/'Полная_исходная_папка';dest.mkdir(exist_ok=True)
files=sorted(p for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
groups=[[]];total=0
for p in files:
    st=p.stat()
    assert not(getattr(st,'st_flags',0)&0x40000000),str(p)
    if total+st.st_size>90_000_000:
        groups.append([]);total=0
    groups[-1].append(p);total+=st.st_size
manifest=[]
for n,group in enumerate(groups,1):
    target=dest/f'Итоговый_проект.part{n:02d}.zip'
    with zipfile.ZipFile(target,'w') as z:
        for p in group:
            z.write(p,Path(source.name)/p.relative_to(source),compress_type=zipfile.ZIP_STORED if p.suffix=='.png' else zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
    manifest.append(dict(path=str(target.resolve()),bytes=target.stat().st_size,files=len(group),sha256=hashlib.file_digest(target.open('rb'),'sha256').hexdigest()))
(base/'final_packages.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print(json.dumps(manifest,ensure_ascii=False,indent=2))
