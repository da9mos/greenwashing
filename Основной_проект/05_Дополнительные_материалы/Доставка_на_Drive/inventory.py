from pathlib import Path
from urllib.parse import unquote
import re,json,os

root=Path(__file__).resolve().parents[1]
index=root/'Итоговый проект/Корпус_92_отчёта.md'
rows=[]
for company,report,link,pages,version in re.findall(r'\| ([^|]+) \| \[([^]]+)\]\(([^)]+)\) \| (\d+) \| ([^|]+) \|',index.read_text()):
    path=(index.parent/unquote(link)).resolve()
    assert path.is_file(),str(path)
    assets=sorted((path.parent/'assets').rglob('*')) if (path.parent/'assets').exists() else []
    files=[path]+[p for p in assets if p.is_file()]
    for p in files:
        st=p.stat()
        assert not (getattr(st,'st_flags',0)&0x40000000),f'Cloud-only: {p}'
    rows.append(dict(company=company.strip(),report=report,pages=int(pages),version=version.strip(),source=str(path),files=len(files),bytes=sum(p.stat().st_size for p in files)))
assert len(rows)==92
(Path(__file__).parent/'inventory.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
print(json.dumps({'reports':len(rows),'companies':len(set(r['company'] for r in rows)),'files':sum(r['files'] for r in rows),'bytes':sum(r['bytes'] for r in rows),'largest':sorted(rows,key=lambda r:r['bytes'],reverse=True)[:3]},ensure_ascii=False,indent=2))
