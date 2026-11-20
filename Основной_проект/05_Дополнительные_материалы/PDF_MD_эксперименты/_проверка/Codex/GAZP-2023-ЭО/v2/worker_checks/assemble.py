import sys,json,re,collections,html,hashlib
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf,pymupdf4llm
from markdown_it import MarkdownIt
pymupdf4llm.use_layout(False)
root=Path(__file__).resolve().parents[2];out=root/'result';check=out/'_проверка';s=json.loads((root/'source.json').read_text());d=pymupdf.open(s['source_pdf']);states=json.loads((check/'pages.json').read_text())['pages']
checked={1,2,76,77,78,79,80,81,82,83,84}
parts=['# Экологический отчет ПАО «Газпром» за 2023 год','> **Техническая пометка о переносе. Рабочая версия.** Учтены все 84 физические страницы. Текст извлечен из PDF; текст растрового приложения распознан локально и исправлен по изображениям. Полная сверка остальных страниц, чисел, сложных таблиц и диаграмм не завершена. Статусы и ограничения перечислены в `_проверка/pages.json`. Изображения страниц сохраняют исходную графику и служат визуальной опорой.']
links=[];coverage=[];total_tables=0
for n,p in enumerate(d,1):
 st=states[n-1];text=(check/'pages'/f'{n:04}.md').read_text().strip()
 if n in {2,80,81,82,83}:text='<!-- Страница без текста; фон и оформление сохранены на изображении. -->'
 st['conversion_status']='converted';st['review_status']='checked' if n in checked else 'pending'
 if n in checked:
  st['issues']=[];st['review_basis']='Визуально прочитано изображение исходной страницы; OCR исправлен там, где применялся.'
 if n in {76,77,78,79}:
  st['printed_page']={'outer':str(n-2),'enclosed':None if n==76 else str(n-75)};st['method']='local Tesseract rus+eng plus full visual correction';st['content_type']='mixed: scanned assurance report with native header and folio'
 if n in {2,80,81,82,83}:st['content_type']='blank/background';st['printed_page']=None
 if n==1:st['method']='visual transcription of cover';st['content_type']='image cover';st['printed_page']=None
 if n==84:st['printed_page']=None
 if n not in checked:
  note='> **Пометка о переносе, страница '+str(n)+':** текст конвертирован; полная сверка по оригиналу не завершена. Числа, связи в таблицах и диаграммах, сноски и переносы требуют проверки.'
 else:note=''
 page_links=[]
 for a in p.get_links():
  if a.get('kind')==pymupdf.LINK_GOTO and a.get('page',-1)>=0:
   target=a['page']+1;href=f'#pdf-page-{target}';label=p.get_text(clip=a['from']).strip() or f'Переход на физическую страницу {target}'
  elif a.get('uri'):href=a['uri'];label=p.get_text(clip=a['from']).strip() or href
  else:
   if a.get('kind') not in {0}:st['issues'].append('Аннотация PDF с неустановленным назначением.');
   continue
  links.append({'pdf_page':n,'label':label,'destination':href});page_links.append((label,href))
 if page_links:
  # Keep PDF annotations separately from author's visible text; exact physical targets only.
  text+='\n\n<details><summary>Ссылки из аннотаций PDF</summary>\n\n'+'\n'.join(f'- [{lab.replace(chr(10)," ")}]({href})' for lab,href in page_links)+'\n\n</details>'
 block=f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+(note+'\n\n' if note else '')+text+f'\n\n![Исходная физическая страница {n}](assets/page_{n:04}.png)'
 parts.append(block);st['converted_chars']=len(text);total_tables+=text.count('<table>')
 # Coverage diagnostic only, not a claim of content verification.
 body=''.join(sp['text'] for b in p.get_text('dict')['blocks'] if b['type']==0 for l in b['lines'] if l['dir'][0]>.5 and l['bbox'][1]<803 for sp in l['spans'])
 plain=html.unescape(re.sub('<[^>]*>','',text));a=collections.Counter(c for c in body if c.isalnum());b=collections.Counter(c for c in plain if c.isalnum());missing=a-b
 coverage.append({'pdf_page':n,'source_body_alnum':sum(a.values()),'missing_alnum_count':sum(missing.values()),'missing_chars':dict(missing)})
report='\n\n'.join(parts)+'\n';(out/'report.md').write_text(report)
(check/'pages.json').write_text(json.dumps({'document':'GAZP-2023-ЭО','physical_pages':84,'conversion_status':'converted','review_status':'pending','pages':states},ensure_ascii=False,indent=2))
(check/'links.json').write_text(json.dumps(links,ensure_ascii=False,indent=2));(check/'coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2))
md=MarkdownIt('commonmark',{'html':True}).enable('table');rendered=md.render(report)
rendered=rendered.replace('src="assets/','loading="lazy" src="../assets/')
css='body{font:16px/1.5 system-ui;max-width:1200px;margin:40px auto;padding:0 24px}img{max-width:100%;height:auto;display:block;margin:24px 0}table{border-collapse:collapse;display:block;overflow-x:auto;max-width:100%;margin:24px 0;font-size:13px}td,th{border:1px solid #aab;padding:6px;min-width:55px;vertical-align:top}blockquote{background:#fff4de;padding:12px;border-left:4px solid #dd9b30}pre{overflow-x:auto}a[id]{display:block;border-top:3px solid #0672b1;margin-top:60px}'
(check/'preview.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Экологический отчет — рабочая конвертация</title><style>'+css+'</style><body>'+rendered+'</body></html>')
print('pages',len(states),'checked',len(checked),'tables',total_tables,'links',len(links),'chars',len(report));print('coverage gaps',[(c['pdf_page'],c['missing_alnum_count']) for c in coverage if c['missing_alnum_count']])
