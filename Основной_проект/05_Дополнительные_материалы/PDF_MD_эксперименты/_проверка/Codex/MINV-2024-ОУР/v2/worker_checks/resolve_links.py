from pathlib import Path
import sys,json,re,html,hashlib
sys.path.insert(0,'/private/tmp/sber-pdf-libs');import fitz
r=Path('result');a=r/'_проверка';d=fitz.open(json.load(open('source.json'))['source_pdf']);names=d.resolve_names();s=(r/'report.md').read_text();parts=re.split(r'<!-- pdf_page: (\d+) -->',s);records=[]
for n,p in enumerate(d,1):
 for l in p.get_links():
  if l['kind']!=4:continue
  name=l.get('nameddest','')
  try:name=name.encode('latin1').decode('utf8')
  except (UnicodeError,ValueError):pass
  dest=names.get(name);label=' '.join(p.get_textbox(l['from']).split());target=f'#pdf-page-{dest["page"]+1}' if dest and dest.get('page',-1)>=0 else None
  records.append({'pdf_page':n,'text':label,'name':name,'target':target})
  if target:parts[2*n]+=f'\n<p><a href="{target}">{html.escape(label or name)}</a></p>\n'
  else:parts[2*n]+='\n> Служебная пометка: назначение внутренней ссылки не установлено: '+html.escape(label or name)+'\n'
s=parts[0]+''.join(f'<!-- pdf_page: {parts[i]} -->{parts[i+1]}' for i in range(1,len(parts),2));(r/'report.md').write_text(s);(a/'named_links.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
v=json.loads((a/'validation.json').read_text());v['unresolved_annotation_count']=sum(not x['target'] for x in records);v['named_links_resolved']=sum(bool(x['target']) for x in records);v['report_sha256']=hashlib.sha256((r/'report.md').read_bytes()).hexdigest();(a/'validation.json').write_text(json.dumps(v,ensure_ascii=False,indent=2))
sys.path.insert(0,'/private/tmp/sber-diff-libs');import markdown
(a/'render'/'report.html').write_text('<!doctype html><meta charset="utf-8"><style>body{font-family:Arial;max-width:1200px;margin:auto;padding:24px}table{border-collapse:collapse;display:block;overflow-x:auto}td,th{border:1px solid #aaa;padding:6px}img{max-width:100%}</style>'+markdown.markdown(s,extensions=['tables','fenced_code']))
print('resolved',v['named_links_resolved'],'unresolved',v['unresolved_annotation_count'])
