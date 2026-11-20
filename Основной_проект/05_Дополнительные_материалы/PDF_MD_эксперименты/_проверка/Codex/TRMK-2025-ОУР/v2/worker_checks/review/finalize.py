from pathlib import Path
import re,json,hashlib,sys,unicodedata
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
r=Path('result/report.md');s=r.read_text(); old=Path('result/_проверка/report.before_review.md').read_text()
for n in range(90,96):
 pat=rf'<!-- pdf_page: {n} -->.*?(?=<!-- pdf_page: |\Z)'; prior=re.search(pat,old,re.S).group(); now=re.search(pat,s,re.S).group()
 if '> Служебная информация: ссылки исходного PDF' in prior:
  links=prior[prior.index('> Служебная информация: ссылки исходного PDF'):prior.index('<details>')]
  now=now.replace('<details>',links+'<details>',1);s=re.sub(pat,lambda m:now,s,count=1,flags=re.S)
# source-checked row links on physical page 7
rows=[('1','Клиентоориентированность и обеспечение качества продукции','=','GRI 418'),('1','Охрана труда и здоровье сотрудников','=','GRI 403'),('1','Экономическая результативность','=','GRI 201'),('1','Выбросы загрязняющих веществ в атмосферу','↑','GRI 305'),('1','Устойчивая цепочка поставок','↑','GRI 204, 308, 414'),('1','Водопотребление и сбросы','↑','GRI 303'),('2','Управление отходами','=','GRI 306'),('2','Деловая этика и противодействие коррупции','=','GRI 205, 206'),('2','Занятость и достойные условия труда','↓','GRI 202, 401, 402, 405'),('2','Влияние на изменение климата','↑','GRI 305'),('2','Потребление энергии и энергоэффективность','↑','GRI 302'),('2','Соблюдение прав человека','=','GRI 405, 406, 407, 408, 409'),('3','Использование сырья и материалов','↓','GRI 301'),('3','Обучение и развитие персонала','↓','GRI 404'),('3','Развитие регионов присутствия и благотворительность','=','GRI 203, 413'),('3','Рекультивация и сохранение биоразнообразия','=','GRI 101 (2024)')]
def table(rows):return '<table>\n<tr><th>Приоритет</th><th>Тема</th><th>Изменения относительно 2024 года</th><th>Показатель GRI</th></tr>\n'+'\n'.join('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>' for row in rows)+'\n</table>'
p7=re.search(r'<!-- pdf_page: 7 -->.*?(?=<!-- pdf_page: 8 -->)',s,re.S).group(); tables=list(re.finditer(r'<table>.*?</table>',p7,re.S))
for m,repl in reversed(list(zip(tables,[table(rows[:12]),table(rows[12:])]))):p7=p7[:m.start()]+repl+p7[m.end():]
s=re.sub(r'<!-- pdf_page: 7 -->.*?(?=<!-- pdf_page: 8 -->)',lambda m:p7,s,flags=re.S)
# Explicit local uncertainty notes keep unverified relations visible beside the content.
registry=json.load(open('result/_проверка/pages.json')); repaired=json.load(open('result/_проверка/review/repaired_table_accounting.json'))
full_checked=[1,2,115]; source_images_seen=[1,2,7,13,31,90,91,92,93,94,95,102,110,115]
unicode_pages=sorted({x['page'] for x in json.load(open('result/_проверка/review/unicode_lines.json'))})
for page in registry['pages']:
 n=page['pdf_page']; page['initial_diagnostics']=page['issues'][:]; page['review_status']='checked' if n in full_checked else 'pending';page['semantic_source_review_completed']=n in full_checked
 page['conversion_status']='converted';page['issues']=[] if n in full_checked else ['Полная сверка текста, порядка чтения и связей по оригиналу не завершена.']
 page['verification_scope']='Полный визуальный просмотр исходной обложки и сверка ее текста' if n in full_checked else 'Механический перенос; дополнительные проверки указаны отдельно'
 page['source_image_inspected']=n in source_images_seen
 page['printed_labels']=None
 page['content_type']='native_text_with_graphics_or_tables' if page['native_glyphs'] else 'graphic'
 if n in [1,2]:page['content_type']='cover_native_text_and_graphics'
 if n==115:page['content_type']='blank_back_cover';page['printed_labels']=[]
 if n==1 or n==2:page['printed_labels']=[]
 if n==7:page['printed_labels']=['10','11'];page['checked_blocks']=['Обе таблицы перечней тем: все 16 строк, приоритеты, изменения, коды GRI; визуальная сверка по изображению'];page['issues'].append('Схема и порядок чтения остального текста не сверены полностью.')
 if n==13:page['printed_labels']=['22','23']
 if n==31:page['printed_labels']=['58','59']
 if 90<=n<=95:page['printed_labels']=[str(176+(n-90)*2),str(177+(n-90)*2)]
 if n==102:page['printed_labels']=['200','201']
 if n==110:page['printed_labels']=['216','217']
 if n in unicode_pages:
  page['unicode_review']={'status':'checked','scope':'Все строки с Co/Cc; просмотрены растровые фрагменты исходного PDF. Cc 02/03 невидимы; E804 — цветной круг легенды.','remaining':0};page['unresolved_unicode_original']=page['unresolved_unicode'];page['unresolved_unicode']=0
 if str(n) in repaired:
  page['table_geometry_repair']=repaired[str(n)];page['issues'].append('Геометрия таблиц перестроена по горизонтальным линиям оригинала; все ячейки и объединения требуют полной сверки.');page['checked_blocks']=page.get('checked_blocks',[])+['Диагностические неоднозначности — пробелы на границах ячеек; не числовые значения.']
 if page['tables'] and n!=7:page['issues'].append('Исходная автоматическая сетка может разделять строки или объединять колонки; требуется сверка каждой ячейки.')
 if n not in full_checked:
  msg='> Служебная информация: проверка страницы pending. Порядок чтения и связи элементов полностью не сверены.'
  if page['tables']:msg+=' Табличные связи требуют проверки по приложенному оригиналу.'
  s=s.replace(f'<a id="pdf-page-{n}"></a>',f'<a id="pdf-page-{n}"></a>\n\n{msg}',1)
registry['scope']='Все 115 физических страниц конвертированы; полностью сверены обложки 1, 2, 115; другие страницы pending.'
registry['reviewed_source_images']=source_images_seen;registry['reviewed_unicode_crops']=187
r.write_text(s);Path('result/_проверка/pages.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n')
html=MarkdownIt('commonmark',{'html':True}).render(s);soup=BeautifulSoup(html,'html.parser'); markers=[int(n) for n in re.findall(r'<!-- pdf_page: (\d+) -->',s)];missing=[]
for img in soup.find_all('img'):
 if not (r.parent/img['src']).is_file():missing.append(img['src'])
ids={a['id'] for a in soup.find_all(id=True)};badlinks=[a['href'] for a in soup.find_all('a',href=True) if a['href'].startswith('#') and a['href'][1:] not in ids]
assert markers==list(range(1,116));assert not missing and not badlinks
validation={'pages':len(markers),'page_order_ok':True,'missing_assets':missing,'missing_anchors':badlinks,'report_sha256':hashlib.sha256(r.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(Path(json.load(open('source.json'))['source_pdf']).read_bytes()).hexdigest(),'html_tables':len(soup.find_all('table')),'source_images':len(soup.find_all('img')),'render_status':'blocked: Chrome SIGABRT at launch; HTML generated, no browser screenshots','full_source_checked_pages':full_checked,'all_other_pages_review_status':'pending'}
Path('result/_проверка/validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n');print(validation)
