from pathlib import Path
import json,re,sys,hashlib,html
sys.path.insert(0,'/private/tmp/sber-pdf-libs');import fitz
r=Path('result');a=r/'_проверка';src=json.load(open('source.json'));doc=fitz.open(src['source_pdf']);s=(r/'report.md').read_text();parts=re.split(r'<!-- pdf_page: (\d+) -->',s);annot=[]
for i in range(1,len(parts),2):
 n=int(parts[i]); links=[]
 for l in doc[n-1].get_links():
  label=' '.join(doc[n-1].get_textbox(l['from']).split()); target=None
  if l.get('uri'): target=l['uri']
  elif l.get('page',-1)>=0:target=f"#pdf-page-{l['page']+1}"
  item={'pdf_page':n,'text':label,'target':target,'kind':l['kind']};annot.append(item)
  if target:
   safe_label=html.escape(label or target);links.append(f'<li><a href="{html.escape(target,quote=True)}">{safe_label}</a></li>')
 if links:parts[i+1]+='\n<details>\n<summary>Служебный реестр ссылок из аннотаций этой страницы</summary>\n<ul>\n'+'\n'.join(links)+'\n</ul>\n</details>\n\n'
s=parts[0]+''.join(f'<!-- pdf_page: {parts[i]} -->{parts[i+1]}' for i in range(1,len(parts),2));(r/'report.md').write_text(s)
(a/'pdf_links.json').write_text(json.dumps(annot,ensure_ascii=False,indent=2))
p=json.loads((a/'pages.json').read_text())
for x in p['pages']:
 n=x['pdf_page'];t=parts[2*n];tables=re.findall(r'<table>.*?</table>',t,re.S);blank=sum(len(re.findall(r'<td[^>]*>\s*</td>',tbl)) for tbl in tables)
 x['content_type']='text_layer_with_graphics' if x['native_glyphs'] else 'image'
 x['printed_page_labels']=re.findall(r'^\s*(\d+)\s*$',doc[n-1].get_text(),re.M)
 x['printed_page_labels_note']='Механически найденные отдельные числа не утверждаются как печатная нумерация; без визуальной проверки печатные номера не установлены.'
 x['render_status']='blocked';x['render_issue']='Chrome завершился с SIGABRT при запуске render_bundle.py в ограниченной среде; снимки результата не получены.'
 if blank and x['review_status']!='checked':x['issues'].append(f'В HTML-таблицах {blank} пустых ячеек: требуется отличить исходные пустоты от лишних колонок детектора.')
 if n not in [1,104,162]:
  needle=f'<a id="pdf-page-{n}"></a>'
  s=s.replace(needle,needle+'\n\n> Служебная пометка: страница converted; полная сверка порядка чтения, таблиц и связей по оригиналу pending.',1)
(a/'pages.json').write_text(json.dumps(p,ensure_ascii=False,indent=2));(r/'report.md').write_text(s)
# Refresh the current HTML without claiming successful rendering.
sys.path.insert(0,'/private/tmp/sber-diff-libs')
try:
 import markdown
 rendered=markdown.markdown(s,extensions=['tables','fenced_code'])
 (a/'render'/'report.html').write_text('<!doctype html><meta charset="utf-8"><style>body{font-family:Arial;max-width:1200px;margin:auto;padding:24px}table{border-collapse:collapse;display:block;overflow-x:auto}td,th{border:1px solid #aaa;padding:6px}img{max-width:100%}details{margin:20px 0}</style>'+rendered)
except ImportError: pass
validation={'physical_pages':len(doc),'markers_in_order':list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',s)))==list(range(1,163)),'missing_image_files':[v for v in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',s) if not (r/v).exists()],'annotation_count':len(annot),'unresolved_annotation_count':sum(not t['target'] for t in annot),'internal_targets_exist':all(f'id="{t["target"][1:]}"' in s for t in annot if t['target'] and t['target'].startswith('#')),'report_sha256':hashlib.sha256((r/'report.md').read_bytes()).hexdigest(),'render_status':'blocked','render_reason':'Chrome launch SIGABRT; no screenshots available; HTML generated only.'}
(a/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2))
print(validation)
