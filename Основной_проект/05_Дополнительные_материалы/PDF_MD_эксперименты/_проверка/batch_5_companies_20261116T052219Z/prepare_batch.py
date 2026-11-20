import concurrent.futures,subprocess,sys,json,datetime
from pathlib import Path
base=Path.cwd()
rids=json.loads(sys.argv[1]);out=base/'_проверка/batch_5_companies_20261116T052219Z'
def one(rid):
 folder=base/'_проверка/native_candidates'/rid
 receipt=folder/'_проверка/native_coverage.json'
 if receipt.is_file() and (folder/'report.md').is_file():return (rid,'existing')
 with (out/(rid+'_native.log')).open('a') as log:
  p=subprocess.run([sys.executable,'tools/native_candidate.py','--source',str(base/'_источники'/(rid+'.pdf')),'--output',str(folder),'--image-source',str(base/'_проверка/входы'/rid)],stdout=log,stderr=subprocess.STDOUT)
 return (rid,p.returncode)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for result in pool.map(one,rids):print(datetime.datetime.now(datetime.timezone.utc).isoformat(),result,flush=True)
