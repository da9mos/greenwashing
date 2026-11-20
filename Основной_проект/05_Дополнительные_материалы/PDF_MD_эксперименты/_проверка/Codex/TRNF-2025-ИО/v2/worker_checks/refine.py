from pathlib import Path
import sys,json,re,html,hashlib,importlib.util,collections
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1]
source=json.loads((root.parent/'source.json').read_text())
tool=Path(source['index']).parents[3]/'tools/native_candidate.py'
spec=importlib.util.spec_from_file_location('native',tool);native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
doc=pymupdf.open(source['source_pdf'])
original=(root/'_проверка/session_input/report.native.md').read_text()
parts={int(n):t for n,t in re.findall(r'<!-- pdf_page: (\d+) -->(.*?)(?=<!-- pdf_page:|\Z)',original,re.S)}
log=[]
def record(n,what):log.append({'pdf_page':n,'change':what,'basis':'Исходное изображение PDF и координаты исходных глифов; числа не переписывались.'})
def units(n):
 out=[]
 for bi,b in enumerate(doc[n-1].get_text('rawdict')['blocks']):
  for li,l in enumerate(b.get('lines',[])):
   for sp in l['spans']:
    for c in sp['chars']:
     out.append(dict(text=c['c'],bbox=c['bbox'],line=(bi,li),sequence=len(out),flags=sp['flags']))
 return out
U={n:units(n) for n in [3,60,104]}
def region(n,box):
 us=[u for u in U[n] if box[0]<=(u['bbox'][0]+u['bbox'][2])/2<box[2] and box[1]<=(u['bbox'][1]+u['bbox'][3])/2<box[3]]
 return native.render_glyphs(us)
def table(n,xs,ys):
 return '<table>\n'+'\n'.join('<tr>'+''.join('<td>'+region(n,(x0,y0,x1,y1))+'</td>' for x0,x1 in zip(xs,xs[1:]))+'</tr>' for y0,y1 in zip(ys,ys[1:]))+'\n</table>'
def replace_body(n,body):
 old=parts[n];k=old.find('> Служебная информация: ссылки исходного PDF');links=old[k:old.find('<details>',k)] if k>=0 else ''
 detail=old[old.find('<details>'):] if '<details>' in old else ''
 parts[n]='\n<a id="pdf-page-'+str(n)+'"></a>\n\n'+body+'\n\n'+links+'\n\n'+detail
# OCR text retained in baseline; each original diagnostic remains in pages registry.
for n,t in parts.items():
 if '> Служебная пометка: распознанный' in t:
  parts[n]=re.sub(r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\.\s*.*?(?=> Служебная информация: ссылки исходного PDF|<details>)','',t,flags=re.S)
  record(n,'Удалён из основного текста дополнительный OCR: дубли текстового слоя, обрывки строк и артефакты распознавания фото/логотипов. Сырой OCR сохранён в session_input/report.native.md. Это не означает полной сверки страницы.')
replace_body(1,'# ГОДОВОЙ ОТЧЕТ 2025\n\nТРАНСНЕФТЬ\n\n## В ПОТОКЕ ВРЕМЕНИ')
record(1,'По изображению обложки восстановлены название, год, логотип и полный слоган; ошибочное G удалено.')
replace_body(2,'''## Содержание

| Раздел | Название | Тема | Страница |
|---|---|---|---|
| 1 | Портрет Компании | Сквозь пространство и время | стр. 4 |
| 2 | Положение в отрасли | Соединяя прошлое, настоящее и будущее | стр. 20 |
| 3 | Результаты деятельности | В непрерывном потоке | стр. 26 |
| 4 | Стратегический отчет | Опережая время | стр. 32 |
| 5 | Финансовый отчет | Время – деньги | стр. 48 |
| 6 | Устойчивое развитие | Наследие прошлого. Энергия настоящего. Уверенность в будущем | стр. 62 |
| 7 | Корпоративное управление | Скорость мысли, вызов времени | стр. 104 |
| 8 | Исполнение поручений Президента и Правительства Российской Федерации | Перенимая опыт поколений, создаем будущее | стр. 134 |
| | Трубопроводы Победы | Связь поколений | стр. 144 |
| | Приложения | | стр. 148 |

Годовой отчет ПАО «Транснефть» за 2025 год предварительно утвержден Советом директоров ПАО «Транснефть» 26.05.2026 (протокол от 28.05.2026 №7), утвержден распоряжением Росимущества от 30.06.2026 №1523-р.''')
record(2,'Карточки оглавления собраны в порядке 1–8; отделена декоративная цифра 8 от строки об утверждении. Весь текст страницы сверен с изображением.')
# Contents: left column, then right column; source glyphs, no inferred page targets.
b=['## Содержание']
for box in [(85,78,438,550),(440,78,790,550)]:
 us=[u for u in U[3] if box[0]<=(u['bbox'][0]+u['bbox'][2])/2<box[2] and box[1]<=(u['bbox'][1]+u['bbox'][3])/2<box[3]]
 b.append('<p>'+native.render_glyphs(us)+'</p>')
b.append('<p>1</p>');replace_body(3,'\n\n'.join(b));record(3,'Исправлен порядок чтения оглавления: сначала целиком левая колонка, затем правая. Ссылки оставлены по аннотациям PDF, без вывода целей по печатным номерам.')
# Correct page 60: four separate tables. Headers extracted separately where merged cells are real.
b=[ '<p>'+region(60,(40,10,780,35))+'</p>', '<h2>'+region(60,(40,50,690,108))+'</h2>', '<p>'+region(60,(690,110,780,142))+'</p>']
for title, xs, ys in [
 ((40,145,400,168),[56,145,196,245,294,345,396],[169,204,223,272.5,290]),
 ((405,145,760,168),[411,522,567,612.5,660,705,752],[169,204,232,249,276,294,311]),
 ((40,350,211,374),[56,167.5,212.5,257,305.5,354,396],[375,394.5,412]),
 ((40,422,410,446),[56,212.5,274,335,396],[449,465.5,483])]:
 b.append('<h3>'+region(60,title)+'</h3>')
 # one-level headers with explicit change subheaders; merged header native text spans x boundaries
 if len(xs)==7:
  headers=['Наименование показателя','2025','2024','Изменение 2025/2024, млн руб.','Изменение 2025/2024, %','2023']
  markup=table(60,xs,ys[1:]);markup=markup.replace('<table>','<table>\n<tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr>',1)
  b.append(markup)
 else:b.append(table(60,xs,ys))
b.append('<p>58</p>');replace_body(60,'\n\n'.join(b));record(60,'Разделены независимые таблицы выручки и расходов; убрана фиктивная разделительная колонка. Восстановлена шапка таблицы чистой прибыли. Все четыре таблицы и их ячейки сверены с изображением.')
# Correct page 104: two independent tables, rows determined from source alternating fills.
b=['<p>ГОДОВОЙ ОТЧЕТ 2025 — УСТОЙЧИВОЕ РАЗВИТИЕ</p>','<h2>'+region(104,(50,55,340,108))+'</h2>']
b.append(table(104,[56,145.5,184.5,223,262.5,301,335.5],[113,130.5,157,193,229.5,265.5,312.5,358,435,461,507,564]))
b.append('<h2>'+region(104,(365,55,755,76))+'</h2>')
xs=[367.5,437,480.5,534.5,589,643.5,698.5,754]
headers=[region(104,(xs[i],76,xs[i+1],123)) for i in range(7)]
b.append(table(104,xs,[123,175,202.5,235.5,263,296,328.5,371,442,469.5,511.5,574]).replace('<table>','<table>\n<tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr>',1))
b.append('<p>102</p>');replace_body(104,'\n\n'.join(b));record(104,'Разделены две самостоятельные таблицы; восстановлены заголовок, строки энергоресурсов и принадлежность величин годам. Все значения перенесены из исходных глифов по визуально установленным границам, обе таблицы сверены с изображением.')
# Two adjacent bond tables were fused across blank separator column.
soup=BeautifulSoup(parts[130],'html.parser');tbl=soup.find('table');rows=tbl.find_all('tr')
assert all(len(r.find_all('td'))==11 for r in rows)
new=[]
for lo,hi in [(0,5),(6,11)]:new.append('<table>'+''.join('<tr>'+''.join(str(c) for c in r.find_all('td')[lo:hi])+'</tr>' for r in rows)+'</table>')
tbl.replace_with(BeautifulSoup('\n\n'.join(new),'html.parser'));parts[130]=str(soup);record(130,'Две таблицы облигаций разделены по подтверждённому изображением межколоночному промежутку; данные и пустые ячейки сохранены.')
# Page 30 fake table columns: only 2 actual source columns.
soup=BeautifulSoup(parts[30],'html.parser');tbl=soup.find('table')
for r in tbl.find_all('tr'):
 cells=r.find_all('td');assert len(cells)==4
 assert not cells[1].get_text(strip=True) and not cells[2].get_text(strip=True)
 cells[1].decompose();cells[2].decompose()
parts[30]=str(soup);record(30,'Удалены две фиктивные пустые колонки в таблице структуры экспортного грузооборота. В исходнике два поля: страна и тыс. т. Пустая колонка пояснений на странице 187 сохранена как содержательная.')
# Invisible BEL glyphs are layout spacers (source visual has no missing letters).
for n,t in parts.items():
 if '\x07' in t:
  count=t.count('\x07');parts[n]=t.replace('\x07','');record(n,f'Удалены невидимые управляющие U+0007 ({count} вхождений вместе с повторами в подписях ссылок). В источнике это интервалы перед пунктами/легендами, а не буквенные символы.')
replace_body(190,'ТРАНСНЕФТЬ');record(190,'Логотип прочитан визуально; удалены ложные знаки OCR.')
# Output explicitly separates work-state note from author text.
intro='> Служебная информация: рабочая версия полной конвертации 190 физических страниц. Полная постраничная сверка текста, таблиц и графиков не завершена. Статусы и ограничения: `_проверка/pages.json` и `_проверка/review.md`. Изображения — визуальная опора, не замена тексту.\n\n'
report=''
for n in range(1,191):
 t=parts[n]
 if n==1:t=t.replace('# ГОДОВОЙ ОТЧЕТ 2025','# ГОДОВОЙ ОТЧЕТ 2025\n\n'+intro,1)
 report+=f'<!-- pdf_page: {n} -->'+t.rstrip()+'\n\n'
# Document must start with source title, while preserving marker 1.
report=report.replace('<!-- pdf_page: 1 -->\n<a id="pdf-page-1"></a>\n\n# ГОДОВОЙ ОТЧЕТ 2025','# ГОДОВОЙ ОТЧЕТ 2025\n\n<!-- pdf_page: 1 -->\n<a id="pdf-page-1"></a>',1)
(root/'report.md').write_text(report)
(root/'_проверка/corrections.json').write_text(json.dumps(log,ensure_ascii=False,indent=2))
print('written',len(report),'chars;',len(log),'changes')
