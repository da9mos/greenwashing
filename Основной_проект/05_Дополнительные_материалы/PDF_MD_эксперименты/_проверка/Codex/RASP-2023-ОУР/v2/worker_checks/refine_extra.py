import sys,re,json,hashlib
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
root=Path(__file__).resolve().parents[1]
s=(root/'report.md').read_text();parts=re.split(r'<!-- pdf_page: \d+ -->',s)[1:];prefix=s.split('<!-- pdf_page: 1 -->')[0]
changes=json.load(open(root/'_проверка/corrections.json'))
def log(n,x):changes.append({'pdf_page':n,'correction':x,'basis':'Original full page image inspected'})
def table(headers,rows):
 return '<div style="overflow-x:auto">\n<table>\n<tr>'+''.join('<th>'+x+'</th>' for x in headers)+'</tr>\n'+''.join('<tr>'+''.join('<td>'+x+'</td>' for x in r)+'</tr>\n' for r in rows)+'</table>\n</div>'
years=['2023','2022','2021']
def chart(title,header,rows):return '<h3>'+title+'</h3>\n'+table(header,rows)+'\n\n'
# Page 35: preserve body; only replace chart region after checking all values and legend colors.
t=parts[34];a=t.index('<p>Структура закупок');b=t.index('<p>Самой крупной статьей',a)
new=chart('Структура закупок (%)',['Год','Товарно-материальные ценности','Инвестиционная деятельность','Услуги'],[['2023','12,6','5,3','82,1'],['2022','26','9,4','64,6']])
new+=chart('Общий объем закупок; закупки у местных поставщиков (млрд руб. с НДС)',['Год','Общий объем закупок','Закупки у местных поставщиков'],[['2023','175','41'],['2022','85','22'],['2021','54','18']])
parts[34]=t[:a]+new+t[b:];log(35,'Rebuilt purchase structure and both purchase-volume charts: period/series/value associations checked, duplicated labels removed.')
# Page 62: preserve quantitative strings, including the visibly broken source totals.
t=parts[61];a=t.index('<p>Количество работников, которые');b=t.index('<p>1</p>',a)
new=chart('Количество работников, которые не являются работниками и чей труд контролируется организацией (человек); GRI 2-8',['Год','Количество'],[['2023','53'],['2022','71'],['2021','59']])
new+=chart('Доля высшего руководства, нанятого из представителей местного сообщества (%); GRI 202-2',['Год','Доля'],[['2023','89,1'],['2022','84,9'],['2021','80,5']])
new+=chart('Число работников, имеющих право на отпуск по уходу за ребенком (человек); GRI 401-3',['Год','Мужчины','Женщины','Итого, как напечатано'],[['2023','2 370','324','2 694'],['2022','2 411','302','2'],['2021','2 405','312','713']])
new+='> Техническая пометка: в исходном PDF подпись «Итого» за 2022 год отображается как «2», за 2021 — как «713». Сохранено видимое написание; отсутствующие части не восстановлены расчетом. См. изображение страницы.\n\n'
new+=chart('Число работников, вернувшихся из отпуска по уходу за ребенком (человек); GRI 401-3',['Год','Женщины','Мужчины','Итого'],[['2023','46','1','47'],['2022','59','4','63'],['2021','62','2','64']])
new+=chart('Число работников, трудоустроенных в Компании спустя 12 месяцев после выхода из отпуска по уходу за ребенком (человек); GRI 401-3',['Год','Женщины','Мужчины','Итого'],[['2023','46','1','47'],['2022','55','2','57'],['2021','58','2','60']])
new+=chart('Количество работников, состоящих в профсоюзных организациях (человек); GRI 2-30',['Год','Росуглепроф','НПГР<sup>1</sup>'],[['2023','9 359','49'],['2022','9 376','58'],['2021','9 470','63']])
# Locate actual footnote after the last chart, not small value 1 earlier.
b=t.index('<p>Первичная [профсоюзная]');b=t.rfind('<p>1</p>',a,b)
parts[61]=t[:a]+new+t[b:]
t=parts[61];a=t.index('<p>Валовые прямые выбросы');b=t.index('> Служебная информация:',a)
new=chart('Валовые прямые выбросы парниковых газов (область охвата 1) (тыс. т CO<sub>2</sub>-экв.); GRI 305-1',['Объем валовых прямых выбросов парниковых газов','2023','2022','2021'],[['CH<sub>4</sub>','11 776','13 419','12 472'],['CO<sub>2</sub>','863','958','840'],['N<sub>2</sub>O','6','7','5'],['Объем валовых прямых выбросов парниковых газов (Scope 1)','12 644','14 384','13 317']])
new+=chart('Валовые косвенные выбросы парниковых газов (область охвата 2) (т CO<sub>2</sub>-экв.); GRI 305-2',['Показатель','2023','2022','2021'],[['Объем валовых косвенных выбросов парниковых газов','372 491','364 984','355 996']])
new+=chart('Коэффициент интенсивности выбросов парниковых газов по областям охвата 1 и 2 на единицу продукции (т CO<sub>2</sub>-экв./т добытого угля); GRI 305-4',['Год','Коэффициент'],[['2023','0,68'],['2022','0,67'],['2021','0,58']])
new+=chart('Объем сокращенных выбросов парниковых газов, являющийся непосредственным результатом реализации инициатив по сокращению выбросов (т CO<sub>2</sub>-экв.); GRI 305-5',['Год','Объем'],[['2023','233 975'],['2022','334 143'],['2021','161 798']])
parts[61]=t[:a]+new+t[b:];log(62,'Rebuilt six HR charts and greenhouse-gas tables/charts; split merged columns, preserved source totals 2 / 713 without arithmetic repair; compared first emissions table to image.')
# Identify remaining grid problems, without claiming a visual review of their content.
table_diagnostics=[]
for n,t in enumerate(parts,1):
 soup=BeautifulSoup(t,'html.parser')
 for k,tbl in enumerate(soup.find_all('table'),1):
  cells=tbl.find_all(['td','th']);empty=sum(not c.get_text(strip=True) for c in cells)
  combined=sum(bool(re.search(r'20(?:21|22|23)\s*20(?:21|22|23)',c.get_text(' ',strip=True))) for c in cells)
  if empty or combined:table_diagnostics.append({'pdf_page':n,'table':k,'empty_cells':empty,'cells_with_multiple_years':combined,'status':'pending','reason':'Native geometry retained; empty tracks and/or combined year labels require source-level row/column review.'})
 # Source annotation destinations are preserved, but broad label rectangles can include nearby text.
 if '#pdf-page-1"' in t:
  note='> Техническая пометка: среди аннотаций PDF есть назначения на обложку, не согласующиеся с видимой подписью. Эти назначения сохранены как в PDF; смысловая корректность переходов не подтверждена.\n\n'
  t=t.replace('> Служебная информация: ссылки исходного PDF',note+'> Служебная информация: ссылки исходного PDF')
  parts[n-1]=t
s=prefix+''.join(f'<!-- pdf_page: {n} -->'+t for n,t in enumerate(parts,1));(root/'report.md').write_text(s)
(root/'_проверка/corrections.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
(root/'_проверка/table_diagnostics.json').write_text(json.dumps(table_diagnostics,ensure_ascii=False,indent=2))
# Local rendering of the actual saved Markdown, including all original HTML tables.
render=MarkdownIt('commonmark',{'html':True}).render(s)
style='body{font:16px/1.5 Arial,sans-serif;max-width:1100px;margin:30px auto;padding:20px}table{border-collapse:collapse;min-width:600px}td,th{border:1px solid #aaa;padding:8px;vertical-align:top}td p{margin:0 0 5px}img{max-width:100%}blockquote{background:#eee;padding:10px}details{margin:20px 0}'
(root/'_проверка/preview.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><base href="../"><style>'+style+'</style><body>'+render+'</body></html>')
print('Saved extra corrections. Remaining structural flags:',len(table_diagnostics))
