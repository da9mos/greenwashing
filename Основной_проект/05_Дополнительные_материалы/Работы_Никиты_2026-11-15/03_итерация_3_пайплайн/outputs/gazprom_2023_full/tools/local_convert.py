from pathlib import Path
import json,hashlib,time
import pymupdf,pymupdf4llm
import argparse
ap=argparse.ArgumentParser();ap.add_argument('pdf');ap.add_argument('output');args=ap.parse_args()
src=Path(args.pdf);o=Path(args.output);(o/'local_pages').mkdir(parents=True,exist_ok=True)
assert not (o/'local_manifest.json').exists(),'Use new output directory; existing result must not be overwritten'
d=pymupdf.open(src);start=time.time();manifest=[]
for i in range(len(d)):
 try:
  md=pymupdf4llm.to_markdown(d,pages=[i],show_progress=False,use_ocr=False)
  if not isinstance(md,str):raise ValueError('Expected per-page Markdown string')
  err=None
 except Exception as e:md='';err=type(e).__name__+': '+str(e)
 raw=d[i].get_text();spans=[]
 for b in d[i].get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   for s in l['spans']:spans.append({k:s[k]for k in ['text','size','origin','bbox','flags']})
 (o/'local_pages'/f'{i+1:03d}.md').write_text(md)
 (o/'local_pages'/f'{i+1:03d}.json').write_text(json.dumps({'pdf_page':i+1,'width':d[i].rect.width,'height':d[i].rect.height,'raw_text':raw,'spans':spans},ensure_ascii=False))
 manifest.append({'pdf_page':i+1,'md_chars':len(md),'raw_chars':len(raw),'error':err,'md_sha256':hashlib.sha256(md.encode()).hexdigest()})
 if(i+1)%10==0:print('local',i+1,'/',len(d),flush=True)
(o/'01_local.md').write_text('# PDF: локальное извлечение\n\nЛокальное машинное извлечение; требует проверки.\n\n'+'\n\n'.join(f'<!-- pdf_page: {i+1} -->\n## PDF-страница {i+1}\n\n'+(o/'local_pages'/f'{i+1:03d}.md').read_text()for i in range(len(d))))
(o/'local_manifest.json').write_text(json.dumps({'engine':'pymupdf4llm','version':getattr(pymupdf4llm,'__version__','unknown'),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'page_count':len(d),'seconds':time.time()-start,'pages':manifest},ensure_ascii=False,indent=2))
print('LOCAL_DONE',len(d),sum(bool(v['error'])for v in manifest),flush=True)
