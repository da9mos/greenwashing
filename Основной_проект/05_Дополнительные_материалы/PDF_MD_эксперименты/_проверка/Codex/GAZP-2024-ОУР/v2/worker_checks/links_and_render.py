from pathlib import Path
import json,re,html,hashlib
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
O=Path('result');A=O/'_проверка';s=json.load(open('source.json'));D=pymupdf.open(s['source_pdf']);reg=json.load(open(A/'pages.json'));alllinks=[];names=D.resolve_names()
for n,p in enumerate(D,1):
 links=[];display=[];seen=set()
 for l in p.get_links():
  dest=None
  if l.get('uri'):dest=l['uri']
  elif 0<=l.get('page',-1)<len(D):dest=f'#pdf-page-{l["page"]+1}'
  elif l.get('nameddest'):
   key=l['nameddest']
   try: key=key.encode('latin1').decode('utf8')
   except (UnicodeError,AttributeError): pass
   resolved=names.get(key,{})
   if 0<=resolved.get('page',-1)<len(D):dest=f'#pdf-page-{resolved["page"]+1}'
  label=p.get_textbox(l['from']).strip().replace('\n',' ')
  x={'source_page':n,'kind':l['kind'],'bbox':list(l['from']),'label':label,'target':dest}
  if l.get('nameddest'):x['named_destination']=l['nameddest']
  links.append(x);alllinks.append(x)
  if dest and l['from'].y0>65 and dest not in seen:
   seen.add(dest);label=(label or 'Переход из аннотации PDF').replace('[','\\[').replace(']','\\]')
   display.append(f'- [{label}](<{dest}>)')
 f=A/'pages'/f'{n:04}.md';t=f.read_text()
 t=re.sub(r'<details><summary>Ссылки из аннотаций PDF.*?</details>\s*','',t,flags=re.S)
 if display:
  pos=t.index('<details><summary>Оригинал')
  t=t[:pos]+'<details><summary>Ссылки из аннотаций PDF (технический реестр страницы)</summary>\n\n'+'\n'.join(display)+'\n\n</details>\n\n'+t[pos:]
 f.write_text(t);reg['pages'][n-1]['links']=links
(A/'pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2));(A/'links.json').write_text(json.dumps(alllinks,ensure_ascii=False,indent=2))
t=(O/'report.md').read_text();head=t[:t.index('<!-- pdf_page: 1 -->')];t=head+'\n\n'.join((A/'pages'/f'{n:04}.md').read_text() for n in range(1,151));(O/'report.md').write_text(t)
markers=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',t)));assert markers==list(range(1,151))
anchors=set(re.findall(r'id="([^"]+)"',t));targets=re.findall(r'\]\(<#([^>]+)>\)',t);assert set(targets)<=anchors
checks=json.load(open(A/'integrity.json'));checks.update(internal_targets=len(targets),missing_internal_targets=list(set(targets)-anchors),source_annotations=len(alllinks),resolved_annotations=sum(x['target'] is not None for x in alllinks),report_bytes=len(t.encode()),report_sha256=hashlib.sha256(t.encode()).hexdigest());(A/'integrity.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
from markdown_it import MarkdownIt
md=MarkdownIt('commonmark',{'html':True}).enable('table');body=md.render(t)
css='''body{font:16px/1.5 system-ui,sans-serif;max-width:1160px;margin:40px auto;padding:0 24px;color:#222}pre{overflow-x:auto;background:#f4f5f6;padding:16px;font:12px/1.5 monospace;white-space:pre}table{border-collapse:collapse;min-width:700px;margin:16px 0}td,th{border:1px solid #bbb;padding:8px;text-align:left;vertical-align:top}th{background:#f0edf8}img{max-width:100%;height:auto}details{margin:20px 0}a[id^="pdf-page-"]{display:block;border-top:2px solid #167db5;margin-top:60px}blockquote{border-left:3px solid #aaa;padding-left:16px;color:#555}'''
(A/'report_preview.html').write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><base href="../"><title>Конвертация отчета</title><style>'+css+'</style></head><body>'+body+'</body></html>')
print(json.dumps(checks,ensure_ascii=False,indent=2))
