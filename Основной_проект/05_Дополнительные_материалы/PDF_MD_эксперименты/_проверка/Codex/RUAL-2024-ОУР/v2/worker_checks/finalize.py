import json,re,hashlib,sys
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
root=Path(__file__).resolve().parents[1]
s=(root/'report.md').read_text()
items={33:'Национальные проекты России: Экология. Глобальные цели ООН: 7 — Недорогостоящая и чистая энергия; 13 — Борьба с изменением климата; 15 — Сохранение экосистем суши; 17 — Партнерство в интересах устойчивого развития.',41:'Национальные проекты России: Здравоохранение; Образование; Жилье и городская среда. Глобальные цели ООН: 8 — Достойная работа и экономический рост.'}
cs=json.loads((root/'_проверка/corrections.json').read_text())
for n,caption in items.items():
    pattern=r'(<!-- pdf_page: '+str(n)+r' -->.*?)(> Служебная информация: ссылки исходного PDF)'
    s,count=re.subn(pattern,lambda m:m[1]+'<p>'+caption+'</p>\n\n'+m[2],s,count=1,flags=re.S)
    assert count==1
    cs.append({'pdf_page':n,'change':'Подписи национальных проектов и ЦУР перенесены с увеличенного изображения значков вместо ошибочного дополнительного OCR.','basis':f'Исходное изображение; просмотр увеличенного фрагмента icons{n}.png.'})
(root/'report.md').write_text(s)
(root/'_проверка/corrections.json').write_text(json.dumps(cs,ensure_ascii=False,indent=2))
reg=json.loads((root/'_проверка/pages.json').read_text())
for x in reg['pages']:
    x['corrections']=[c['change'] for c in cs if c['pdf_page']==x['pdf_page']]
    x['printed_designation']=None
    x['printed_designation_status']='Не установлено; не вычислялось по смещению'
    x['content_type']='mixed_scan_and_native_heading' if x['pdf_page']==148 else ('cover' if x['pdf_page']==1 else ('native_text_with_tables_and_graphics' if x['tables'] else 'native_text_and_graphics'))
    if x['pdf_page']==1:x['printed_designation_status']='На обложке отсутствует'
reg['summary']['source_images_viewed_pages']=[x['pdf_page'] for x in reg['pages'] if x['source_image_viewed']]
reg['summary']['source_image_view_scope']='Обложка полностью; остальные отмеченные страницы — проблемные участки либо общий вид структуры. Это не полная сверка страниц.'
(root/'_проверка/pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2))
coverage=json.loads((root/'_проверка/native_coverage.json').read_text())
coverage['applies_to']='baseline/report.md (исходный механический кандидат до исправлений)'
coverage['current_report_has_source_based_edits']=True
(root/'_проверка/native_coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2))
val=json.loads((root/'_проверка/validation.json').read_text())
val['report_sha256']=hashlib.sha256(s.encode()).hexdigest()
assert list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',s)))==list(range(1,150))
assert len(reg['pages'])==149
assert all((root/p).is_file() for p in re.findall(r'\]\((assets/[^)]+)\)',s))
assert not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',s)
assert not re.search(r'\d\t\d\t\d\t\d\t\d',s)
val['technical_tsv_rows_in_report']=0
val['markdown_html_conversion']='Completed locally for final saved report; browser visual inspection unavailable (Chrome exit 134).'
(root/'_проверка/validation.json').write_text(json.dumps(val,ensure_ascii=False,indent=2))
style='<style>body{font:17px Arial,sans-serif;margin:40px;line-height:1.4}table{border-collapse:collapse;display:block;overflow-x:auto;max-width:100%}td,th{padding:6px;border:1px solid #ccc;vertical-align:top;min-width:50px}img{max-width:100%}blockquote{color:#555}</style>'
(root/'_проверка/rendered.html').write_text('<!doctype html><meta charset="utf-8"><base href="../">'+style+MarkdownIt('commonmark',{'html':True}).render(s))
print('Final report:',len(s),'characters; 149 pages; all local image links valid.')
