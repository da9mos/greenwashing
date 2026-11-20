from pathlib import Path
import json,re,hashlib,sys,unicodedata
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
import pymupdf
report=Path('result/report.md');parts=re.split(r'(<!-- pdf_page: \d+ -->)',report.read_text());log=[]
# Cover: read against the full source image.
c=parts[2];start=c.index('<p>Сплав</p>');end=c.index('<details>');c=c[:start]+'РУСАЛ. 25 лет\n\nЕдиный отчет — 2025\n\n'+c[end:];parts[2]=c;parts[0]='# Сплав интересов\n\n> Служебная информация: рабочая полная конвертация 294 физических страниц. Текст и геометрия перенесены из PDF; выполнены адресные исправления. Полная построчная сверка документа не завершена. Состояние каждой страницы указано в `_проверка/pages.json`.\n\n'
log.append({'page':1,'correction':'Заголовок объединён; добавлена надпись логотипа РУСАЛ. 25 лет; удалён ложный OCR-штрих','basis':'Полное изображение обложки'})
# Clean nonprinting font-map artifacts only at visually inspected locations.
for n,char in [(2,'\x08'),(155,'\x07')]:
 count=parts[2*n].count(char);parts[2*n]=parts[2*n].replace(char,'');log.append({'page':n,'correction':f'Удалён управляющий символ U+{ord(char):04X}, {count} вхождений','basis':'Изображение: после названий оглавления/перед текстом сносок нет отдельного печатного знака'})
# OCR duplicates of existing native text and decorative square markers.
for n in [2,7,52,135,191]:
 c=parts[2*n];a=c.index('> Служебная пометка: распознанный');b=c.index('> Служебная информация:',a)
 Path(f'result/_проверка/ocr_removed_{n:04}.txt').write_text(c[a:b]);c=c[:a]+c[b:]
 if n in [7,52,135,191]:
  label='РУСАЛ. 25 лет'
  if n in [52,135]:label+='; ALLOW'
  c=c.replace('<details>',f'> Служебная информация: текст графических логотипов по изображению: {label}.\n\n<details>',1)
 parts[2*n]=c;log.append({'page':n,'correction':'Удалён ложный OCR, дублирующий текстовый слой, и шум декоративных элементов','basis':'Изображение страницы; удалённый OCR сохранён отдельно'})
# Restore independent columns of contents, rather than fictitious row relationships.
left=[('Об Отчете','2'),('Обращение Председателя Совета директоров','6'),('Обращение Генерального директора','8'),('СТРАТЕГИЧЕСКИЙ ОТЧЕТ','10'),('РУСАЛ сегодня — краткий обзор','12'),('Энергетические активы','28'),('Обзор рынка','36'),('Бизнес-модель','56'),('Стратегия РУСАЛа','58'),('Обзор финансовых результатов','62'),('Инвестиционная программа и инновационное развитие','72'),('Система корпоративного управления','90'),('Информация для акционеров и инвесторов','96'),('УСТОЙЧИВОЕ РАЗВИТИЕ','100'),('Управление устойчивым развитием в РУСАЛе','102'),('Охрана окружающей среды и забота о климате','116'),('Забота о людях','156'),('Ответственное управление','230'),('ФИНАНСОВАЯ ОТЧЕТНОСТЬ','266')]
right=[('ПРИЛОЖЕНИЯ','378'),('Приложение 1. Отчет Совета директоров','380'),('Приложение 2. Отчет о корпоративном управлении','426'),('Приложение 3. Отчет о соблюдении принципов и рекомендаций российского Кодекса корпоративного управления','446'),('Приложение 4. Условные обязательства','478'),('Приложение 5. Дополнительная ESG-информация','480'),('Приложение 6. Основные количественные ESG-данные','492'),('Приложение 7. Основные нормативные документы','522'),('Приложение 8. Таблица показателей GRI','524'),('Приложение 9. Таблица показателей SASB','548'),('Приложение 10. Перечень показателей Стандарта общественного капитала бизнеса и Методических рекомендаций по подготовке отчетности МЭР','552'),('Приложение 11. Таблица показателей индексов РСПП','567'),('Приложение 12. Глоссарий','570'),('Приложение 13. Заявление независимого практикующего специалиста о задании, обеспечивающем уверенность','581'),('Приложение 14. Корпоративная и контактная информация','583')]
make=lambda rows:'<table>\n'+''.join('<tr><td>'+a+'</td><td>'+b+'</td></tr>\n' for a,b in rows)+'</table>'
parts[4]=re.sub(r'<table>.*?</table>',make(left)+'\n\n'+make(right),parts[4],count=1,flags=re.S)
log.append({'page':2,'correction':'Оглавление разделено на две независимые колонки; продолжения названий собраны в одну запись с печатным номером','basis':'Увеличенное изображение всей области оглавления'})
# Source alignment: both sections have four subcolumns, not 3+5.
for n in [180,181,182]:
 c=parts[n*2];c,count=re.subn(r'<td colspan="3" rowspan="1">Балансовая стоимость</td><td colspan="5" rowspan="1">Справедливая стоимость</td>',r'<td colspan="4" rowspan="1">Балансовая стоимость</td><td colspan="4" rowspan="1">Справедливая стоимость</td>',c)
 parts[n*2]=c
 if count:log.append({'page':n,'correction':f'Объединения шапок Балансовая/Справедливая стоимость: 4+4 вместо 3+5 ({count})','basis':'Изображения разворотов: четыре подколонки в каждой группе'})
registry=json.load(open('result/_проверка/pages.json'));diagnostic_pages=[]
for entry in registry['pages']:
 n=entry['pdf_page'];entry['conversion_status']='converted';entry['review_status']='pending';entry['semantic_source_review_completed']=False
 entry['verification_scope']='Механический перенос; полная семантическая сверка по оригиналу не завершена.'
 if entry.get('issues'):
  diagnostic_pages.append(n);entry['diagnostic_review']={'records_examined':True,'source_image_overview_examined':True,'full_cell_by_cell_review':False,'result':'Проверена природа диагностики. Подробности адресных исправлений — geometry_repairs.json, remaining_geometry_repairs.json и corrections.json. Полная сверка остаётся pending.'}
 if not entry['issues']:entry['issues']=['Полная проверка порядка чтения, таблиц, примечаний и графики по оригиналу не выполнена.']
 if n in [1,2,7,52,135,155,191]:entry['source_detail_review']='Увеличенное изображение обложки/оглавления/текстовой области разделителя/сносок просмотрено; это не означает полной сверки всей страницы.'
 if n in [84,141]:entry['geometry_repair']={'method':'partition nested detector rectangles','native_inventory_matches':True,'semantic_review':'pending'}
 if n==32:entry['structure_repair']='Четыре колонки и строки схемы выделены по видимой вёрстке. Все исходные глифы учтены ровно один раз; подписи ЦУР прочитаны визуально. Связи продолжений требуют полной сверки.'
 entry['manual_corrections']=[x for x in log if x['page']==n]
 if n in [2,155]:entry['unresolved_unicode_after_correction']=0
 if n==1:
  entry['review_status']='checked';entry['semantic_source_review_completed']=True;entry['verification_scope']='Весь текст обложки и иллюстрация сверены по полному исходному изображению.';entry['issues']=[]
 else:
  warning='> Служебная пометка: converted / pending — полная сверка этой страницы по оригиналу не завершена.'
  if n in diagnostic_pages:warning+=' Диагностика структуры/OCR рассмотрена; исправления и нерешённые связи перечислены в `_проверка/pages.json`.'
  parts[n*2]=re.sub(r'(<a id="pdf-page-\d+"></a>)',r'\1\n\n'+warning,parts[n*2],count=1)
report.write_text(''.join(parts));Path('result/_проверка/pages.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n');Path('result/_проверка/corrections.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n')
src=json.load(open('source.json'));pdf=Path(src['source_pdf']);doc=pymupdf.open(pdf)
text=report.read_text();markers=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',text)));assert markers==list(range(1,295));html=MarkdownIt('commonmark',{'html':True}).render(text);soup=BeautifulSoup(html,'html.parser');missing=[]
for tag in soup.find_all(['a','img']):
 value=tag.get('href') if tag.name=='a' else tag.get('src')
 if not value:continue
 if value.startswith('#'):
  if soup.find(id=value[1:]) is None:missing.append(value)
 elif not re.match(r'[a-zA-Z]+:',value) and not (Path('result')/value).exists():missing.append(value)
assert not missing,missing
controls=[(i,ord(c)) for i,c in enumerate(text) if unicodedata.category(c)=='Cc' and c not in '\n\r\t'];assert not controls,controls[:10]
preview='<!doctype html><meta charset="utf-8"><title>Сплав интересов</title><style>body{font-family:Arial,sans-serif;max-width:1250px;margin:auto;padding:24px;line-height:1.4}table{border-collapse:collapse;display:block;overflow-x:auto;margin:20px 0}td{border:1px solid #bbb;padding:6px;min-width:65px;vertical-align:top}img{max-width:100%}blockquote{color:#666;background:#f3f3f3;padding:8px}</style>'+html
# Preview sits in result root so its relative assets links remain valid.
Path('result/preview.html').write_text(preview)
source_hash=hashlib.sha256(pdf.read_bytes()).hexdigest();coverage=json.load(open('result/_проверка/native_coverage.json'));Path('result/_проверка/baseline/native_coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2))
coverage.update({'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),'pages':294,'source_sha256':source_hash,'review_status':'pending','semantic_source_review_completed':False,'pending_pages':list(range(2,295)),'checked_pages':[1],'original_native_accounting_scope':'Исходный механический кандидат; не доказательство итогового порядка чтения или полного совпадения после ручных правок.','post_edit_native_accounting':'Правки геометрии прошли отдельный учёт глифов; ручные изменения перечислены в corrections.json.','diagnostic_pages_overview_examined':diagnostic_pages})
Path('result/_проверка/native_coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n')
validation={'physical_pages':len(doc),'page_markers_sequential':True,'registry_pages':len(registry['pages']),'missing_links':missing,'control_characters':controls,'html_parse_succeeded':True,'visual_browser_render_checked':False,'report_bytes':report.stat().st_size,'source_sha256':source_hash,'review_status_counts':{'checked':1,'pending':293}}
Path('result/_проверка/validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n');print(validation)
