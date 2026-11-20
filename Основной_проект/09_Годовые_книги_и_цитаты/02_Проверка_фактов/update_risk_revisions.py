import copy
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
from research_common import *
P=D.parent.parent;sys.path.insert(0,str(P/'03_Фактчекинг/Агент'));import factcheck
plan=factcheck.load(D/'run')
for n in range(1,9):
 prior=D/f'run/results/C{n:06}.r000001.json';p=copy.deepcopy(json.loads(prior.read_text()));p['revision']=2;p['checked_at']=datetime.now(ZoneInfo('Asia/Yekaterinburg')).isoformat();p=add_risks(p,2023);p['risk_revision_parent_sha256']=sha(prior)
 p['limitations'].append('Четыре категории внешних рисков проверены отдельными реальными запросами. Негативные факты несовпадающего периметра/метрики не назначены опровержением.')
 factcheck.validate(p,plan);out=D/f'responses/C{n:06}.r000002.json';write(out,p);factcheck.ingest(D/'run',out)
print(factcheck.export(D/'run',D/'export_r2'))
