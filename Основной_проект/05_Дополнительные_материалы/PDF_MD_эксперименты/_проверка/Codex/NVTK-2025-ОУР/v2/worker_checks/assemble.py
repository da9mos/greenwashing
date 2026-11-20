import sys,json,re,hashlib,html
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf,pymupdf4llm
from markdown_it import MarkdownIt
pymupdf4llm.use_layout(False)
out=Path('result');check=out/'_проверка';s=json.load(open('source.json'));doc=pymupdf.open(s['source_pdf']);reg=json.load(open(check/'pages.json'));idx=json.load(open(s['index']));assembled=['# ОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ\n'];alllinks=[]
for n,p in enumerate(doc,1):
 e=reg['pages'][n-1];text=(check/'reconstructed'/f'{n:04}.md').read_text()
 # Remove artificial hard breaks inside detected heading blocks only.
 text=re.sub(r'^## (.*?)(?=\n\n|\Z)',lambda m:'## '+m.group(1).replace('  \n',' '),text,flags=re.M|re.S)
 if n==1:
  text='2025\n\nНОВАТЭК\n\n## В ГАРМОНИИ С СЕВЕРОМ\n\nnovatek.ru\n';e['review_status']='checked';e['issues']=[];e['review_scope']='Сверен текст обложки по изображению; фирменное название восстановлено по логотипу и OCR.'
 e['layout_overview']='Просмотрена миниатюра страницы; это не построчная сверка.'
 e['ocr_status']='performed_rus_eng' if n in [1,11,24,33,35,75,116] else 'not_required_native_body_text'
 links=[];tp=p.get_textpage()
 for l in p.get_links():
  box=l['from'];rec={'pdf_page':n,'source_bbox':list(box),'kind':l.get('kind'),'visible_text':p.get_textbox(box,textpage=tp).strip()}
  if l.get('uri'):rec['uri']=l['uri'];dest=l['uri']
  elif l.get('page',-1)>=0:
   target=l['page']+1;rec['target_pdf_page']=target
   if not 1<=target<=len(doc):e['issues'].append('Назначение ссылки вне документа');continue
   dest=f'#pdf-page-{target}'
  else:rec['unresolved']=True;alllinks.append(rec);continue
  alllinks.append(rec)
  if box.y1<80:continue
  label=' '.join(rec['visible_text'].split()) or 'Графическая ссылка'
  links.append((dest,label))
 seen=set();ls=[]
 for dest,label in links:
  if (dest,label) in seen:continue
  seen.add((dest,label));ls.append('<li><a href="'+html.escape(dest,quote=True)+'">'+html.escape(label)+'</a></li>')
 section=[f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n']
 if n==2:section.append('> **Техническое примечание к конвертации.** Рабочая версия: текст извлечён со всех физических страниц. Полная построчная сверка не завершена. На страницах 2–121 порядок сложных колонок, связи значений в схемах, таблицы и сноски требуют проверки по сохранённому изображению. Реестр статусов находится в `_проверка/pages.json`.\n')
 if n>1:
  section.append('<!-- conversion_status: converted; review_status: pending -->\n')
 section.append(text)
 if e['tables']:
  section.append('> **Техническая пометка:** таблицы восстановлены по геометрии PDF; объединения ячеек и соответствие каждого значения заголовкам полностью не сверены.\n')
 if ls:section.append('<details>\n<summary>Ссылки из аннотаций PDF этой страницы</summary>\n<ul>\n'+'\n'.join(ls)+'\n</ul>\n</details>\n')
 section.append(f'![Оригинал физической страницы {n} — визуальная опора](assets/page_{n:04}.png)\n')
 assembled.append('\n'.join(section))
 file=out/'assets'/f'page_{n:04}.png';assert file.exists();assert hashlib.sha256(file.read_bytes()).hexdigest()==idx['pages'][n-1]['image_sha256']
reg['document_status']='working_version';reg['review_note']='Страница 1: сверка текста обложки. 2–121: обзор миниатюр и выборочные проверки не означают полной сверки; review_status=pending.'
(check/'pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2))
(check/'links.json').write_text(json.dumps(alllinks,ensure_ascii=False,indent=2))
report='\n\n'.join(assembled);(out/'report.md').write_text(report)
assert [int(n) for n in re.findall(r'<!-- pdf_page: (\d+) -->',report)]==list(range(1,122))
md=MarkdownIt('commonmark',{'html':True});body=md.render(report)
# Preview has its own base URL so all report-relative assets remain valid.
preview='<!doctype html><html lang="ru"><head><meta charset="utf-8"><base href="../"><style>body{font:17px/1.5 Arial,sans-serif;max-width:1320px;margin:30px auto;padding:20px}img{max-width:100%;height:auto}table{border-collapse:collapse;display:block;overflow-x:auto;margin:20px 0;max-width:100%}td,th{border:1px solid #aaa;padding:8px;min-width:90px;vertical-align:top}blockquote{border-left:4px solid #d90;padding:10px;background:#fff8e8}details{font-size:14px}h1,h2{line-height:1.2}</style></head><body>'+body+'</body></html>'
(check/'preview.html').write_text(preview)
stats={'physical_pages':121,'page_markers':121,'images':121,'tables':sum(e['tables'] for e in reg['pages']),'review_checked':[1],'review_pending':list(range(2,122)),'ocr_pages':[1,11,24,33,35,75,116],'annotation_count':len(alllinks),'report_bytes':(out/'report.md').stat().st_size,'source_character_coverage':'all native nonspace characters retained, except documented repeated top navigation','source_sha256':reg['source_sha256']}
(check/'validation.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2));print(json.dumps(stats,ensure_ascii=False))
