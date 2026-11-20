import sys,json,time,urllib.request,urllib.error,uuid
from pathlib import Path
import os,getpass,argparse
ap=argparse.ArgumentParser();ap.add_argument('pdf');ap.add_argument('output');ap.add_argument('--tier',default='agentic',choices=['cost_effective','agentic','agentic_plus']);args=ap.parse_args()
key=os.environ.get('LLAMA_CLOUD_API_KEY') or getpass.getpass('LlamaCloud API key (hidden): ')
if not key:raise SystemExit('Missing key')
base='https://api.cloud.llamaindex.ai'
def req(path,body=None,ctype='application/json'):
 r=urllib.request.Request(base+path,data=body,headers={'Authorization':'Bearer '+key,'Accept':'application/json','Content-Type':ctype})
 try:
  with urllib.request.urlopen(r,timeout=180)as f:return json.load(f)
 except urllib.error.HTTPError as e:print('API_ERROR',e.code,e.read().decode().replace(key,'[REDACTED]')[:500],flush=True);raise SystemExit(1)
folder=Path(args.output);src=Path(args.pdf)
assert(folder/'local_manifest.json').exists(),'Local pass must finish first'
import hashlib
assert hashlib.sha256(src.read_bytes()).hexdigest()==json.loads((folder/'local_manifest.json').read_text())['source_sha256'],'Source differs from local pass'
out=folder/'cloud';out.mkdir(exist_ok=True)
if (out/'result.json').exists():raise SystemExit('Result already exists; use a new output directory to avoid overwrite')
jf=out/'job.json'
if jf.exists():
 j=json.loads(jf.read_text());f=None
else:
 boundary='----'+uuid.uuid4().hex
 b=('--'+boundary+'\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nparse\r\n--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="document.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode()+src.read_bytes()+('\r\n--'+boundary+'--\r\n').encode()
 f=req('/api/v1/beta/files',b,'multipart/form-data; boundary='+boundary);(out/'upload.json').write_text(json.dumps(f,indent=2))
cfg={'file_id':f['id'] if f else json.loads((out/'config.json').read_text())['file_id'],'tier':args.tier,'version':'latest','output_options':{'markdown':{'tables':{'output_tables_as_markdown':True}}}}
if jf.exists():
 cfg=json.loads((out/'config.json').read_text())
 assert cfg['tier']==args.tier,'Resume with original tier'
else:(out/'config.json').write_text(json.dumps(cfg,indent=2))
jf=out/'job.json'
if jf.exists():j=json.loads(jf.read_text())
else:j=req('/api/v2/parse',json.dumps(cfg).encode());jf.write_text(json.dumps(j,indent=2))
print(src.name,'STARTED',j['id'],flush=True)
for i in range(240):
 r=req('/api/v2/parse/'+j['id']+'?expand=markdown&expand=items&expand=metadata&expand=text');status=r.get('job',{}).get('status')
 if i%10==0:print(src.name,status,flush=True)
 if status in ['COMPLETED','FAILED','CANCELLED']:
  (out/'result.json').write_text(json.dumps(r,ensure_ascii=False));print(src.name,status,flush=True)
  if status!='COMPLETED':raise SystemExit(1)
  break
 time.sleep(3)
else:raise SystemExit('Polling timeout; retain job ID to resume')
pages=r['markdown']['pages'];expected=json.loads((folder/'local_manifest.json').read_text())['page_count'];assert sorted(x['page_number']for x in pages)==list(range(1,expected+1)),'Missing or duplicate pages';assert all(x.get('success',True)for x in pages),'Failed page in completed job';(folder/'02_llamaparse.md').write_text('# PDF: '+src.name+'\n\nМашинный результат LlamaParse, без ручных исправлений.\n\n'+'\n\n'.join('<!-- pdf_page: '+str(v['page_number'])+' -->\n## PDF-страница '+str(v['page_number'])+'\n\n'+v['markdown']for v in pages));print(src.name,'PAGES',len(pages),flush=True)
print('ALL_DONE',flush=True)
