import sys,json,re,hashlib,collections,html
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
import pymupdf
root=Path('result');p=root/'report.md';s=p.read_text();a=re.split(r'<!-- pdf_page: (\d+) -->',s)
for n in [1,3,18,22,30,45,55,83,103,117,125,141,160,167]:a[n*2]=a[n*2].replace('<p>ТАТНЕФТЬ</p>','<p>TATNEFT</p>')
for n in range(1,201):a[n*2]=re.sub(r'\n\n> Служебная пометка: conversion_status=converted; review_status=pending[^\n]*', '', a[n*2])
# Each page explicitly carries its actual review limitation.
checked={1,3,18,22,30,45,55,83,103,117,125,141,160,167,165,178,200}
viewed={1,2,3,4,5,18,22,30,45,55,67,83,103,117,125,141,160,164,165,166,167,178,200}
registry=json.load(open(root/'_проверка/pages.json'))
source=json.load(open('source.json'));doc=pymupdf.open(source['source_pdf']);sourcehash=hashlib.sha256(Path(source['source_pdf']).read_bytes()).hexdigest()
corrections=json.load(open(root/'_проверка/current_run/native_changes.json'))
for x in registry['pages']:
 n=x['pdf_page'];x['conversion_status']='converted';x['review_status']='checked' if n in checked else 'pending';x['semantic_source_review_completed']=n in checked
 x.setdefault('original_diagnostics',list(x['issues']));x['issues']=[]
 x['printed_page_label']=None
 txt=doc[n-1].get_text()
 m=re.search(r'(?m)^([0-9]+)\s*[|]\s*([0-9]+)\s*$',txt)
 if m:x['printed_page_label']=m[1]+' | '+m[2]
 x['content_type']='native_text_with_graphics'
 if n in [164,165,166]:x['content_type']='mixed_native_and_scanned_text'
 if n==200:x['content_type']='graphic_back_cover_without_text'
 x['source_image_viewed']=n in viewed
 x['verification_scope']='Полная сверка видимого основного содержания страницы с исходным изображением и проверка сохраненного текста.' if n in checked else ('Изображение просмотрено; проверены диагностические участки, полная сверка всей страницы не завершена.' if n in viewed else 'Механическая конвертация; содержательная и визуальная сверка страницы не выполнена.')
 if n not in checked:x['issues'].append('Полная постраничная сверка текста, порядка чтения, всех ячеек, сносок и графических связей не завершена.')
 if n in [2,67,178]:x['diagnostic_resolution']='Все неоднозначные назначения относятся только к пробелам; символы содержательных значений не потеряны. Структура страниц 2 и 178 восстановлена, на 67 добавлены заголовки годов.'
 if n in [2,5]:x['unicode_resolution']='Невидимый управляющий U+0007 удален по изображению, спецшрифт TatSymbol восстановлен как стрелки.'
 if 168<=n<=180 and n!=178:x['issues'].append('В этом приложении следует отдельно проверить цветные графические отметки статусов и разделение двух таблиц разворота: общий учет глифов их не подтверждает.')
 if n==4:x['issues'].append('Подписи карты и легенда перенесены визуально; пространственные связи значков увеличенной карты полностью не проверены.')
 if n in [164,166]:x['issues'].append('OCR исправлен по просмотренным изображениям; итоговая полная сверка всех текстовых и графических элементов страницы не заявлена.')
 if n not in checked:
  note='\n\n> Служебная пометка: conversion_status=converted; review_status=pending. Полная сверка этой страницы по оригиналу не завершена.'
  if n==4:note+=' Пространственные связи карты требуют проверки.'
  if 168<=n<=180 and n!=178:note+=' Цветные отметки статусов и разделение таблиц разворота требуют проверки по изображению.'
  a[n*2]=a[n*2].replace('<details>',note+'\n\n<details>',1)
s=a[0]+''.join('<!-- pdf_page: '+a[i]+' -->'+a[i+1] for i in range(1,len(a),2));p.write_text(s)
registry['source_sha256']=sourcehash;registry['review_summary']={'converted':200,'checked':len(checked),'pending':200-len(checked),'source_images_viewed':sorted(viewed),'full_document_review_completed':False}
(root/'_проверка/pages.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n')
render=MarkdownIt('commonmark',{'html':True}).enable('table').render(s)
soup=BeautifulSoup(render,'html.parser');ids={x.get('id') for x in soup.select('[id]')};missing=[]
for tag in soup.find_all(['img','a']):
 target=tag.get('src') if tag.name=='img' else tag.get('href')
 if not target:
  if not tag.get('id'):missing.append(str(tag))
  continue
 if target.startswith('#'):
  if target[1:] not in ids:missing.append(target)
 elif not re.match(r'^[a-zA-Z]+:',target) and not (root/target).exists():missing.append(target)
assert not missing,missing
assert [int(x) for x in re.findall(r'<!-- pdf_page: (\d+) -->',s)]==list(range(1,201))
assert len(doc)==200
bad=[(i,ord(c)) for i,c in enumerate(s) if (ord(c)<32 and c not in '\n\t\r') or c=='\ufffd'];assert not bad,bad[:20]
style='''body{font:16px/1.55 Arial,sans-serif;max-width:1300px;margin:auto;padding:24px;color:#222}table{border-collapse:collapse;display:block;overflow-x:auto;max-width:100%;margin:20px 0}td,th{border:1px solid #bbb;padding:7px;min-width:80px;vertical-align:top}img{max-width:100%}blockquote{background:#f0f4f3;padding:12px;border-left:4px solid #00a66e}a{overflow-wrap:anywhere}'''
# Path to assets is relative to the preview inside _проверка/current_run.
render=render.replace('src="assets/','src="../../assets/')
(root/'_проверка/current_run/preview.html').write_text('<!DOCTYPE html><html lang="ru"><meta charset="utf-8"><title>TATN — проверка конвертации</title><style>'+style+'</style><body>'+render+'</body></html>')
summary={'source_sha256':sourcehash,'source_pages':200,'page_markers':200,'assets':len(list((root/'assets').glob('*'))),'local_links_valid':True,'invalid_unicode_controls':len(bad),'html_parse_completed':True,'render_screenshot_completed':False,'report_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'checked_pages':sorted(checked),'pending_pages':[n for n in range(1,201) if n not in checked]}
(root/'_проверка/current_run/validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
coverage=json.load(open(root/'_проверка/native_coverage.json'));coverage['coverage_scope']='Original mechanical candidate only. Final report contains documented source-based changes; original glyph inventory is not a fidelity assertion for final report.';coverage['final_report_sha256']=summary['report_sha256'];coverage['full_document_review_completed']=False
(root/'_проверка/native_coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k not in ['checked_pages','pending_pages']},ensure_ascii=False));print('checked',sorted(checked))
