import sys,json,re,hashlib,collections
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1];p=root/'_проверка';s=(root/'report.md').read_text();parts=re.split(r'<!-- pdf_page: (\d+) -->',s)
log=json.loads((p/'corrections.json').read_text());reg=json.loads((p/'pages.json').read_text());tin=[]
for i in range(1,len(parts),2):
 n=int(parts[i]);t=parts[i+1];rec=reg['pages'][n-1]
 if n==13:t=re.sub(r'<p>Показатель 2018<sup>1</sup> 2019 2020 2021 2022 2023</p>\s*','',t,count=1)
 bullets=t.count('գ');icons=t.count('㈭')
 t=t.replace('գ','•').replace('㈭','<img src="assets/source_link_icon.png" alt="Значок ссылки" width="12" height="12"/>')
 if bullets or icons:rec['font_mapping_repairs']={'list_bullets':bullets,'link_icons':icons}
 soup=BeautifulSoup(t,'html.parser');page_tables=[]
 for j,table in enumerate(soup.find_all('table'),1):
  active={};widths=[]
  for ri,row in enumerate(table.find_all('tr')):
   col=0
   for cell in row.find_all(['td','th'],recursive=False):
    while active.get(col,0)>ri:col+=1
    cs=int(cell.get('colspan',1));rs=int(cell.get('rowspan',1))
    for k in range(cs):active[col+k]=ri+rs
    col+=cs
   widths.append(max([c+1 for c,e in active.items() if e>ri],default=0))
  entry={'table':j,'rows':len(widths),'widths':widths,'has_header_cells':bool(table.find('th')),'full_source_review':n==9 or (n==13 and j==1)}
  page_tables.append(entry)
  if len(set(widths))>1:rec['issues'].append(f'Таблица {j}: непостоянное число столбцов сетки; требуется сверка объединений.')
  if not entry['has_header_cells']:rec['issues'].append(f'Таблица {j}: шапка/заголовок частично вне HTML-таблицы; требуется проверка связи.')
 tin.append({'pdf_page':n,'tables':page_tables})
 parts[i+1]=t
s=''.join(parts[j] if j%2==0 else '<!-- pdf_page: '+parts[j]+' -->' for j in range(len(parts)))
(root/'report.md').write_text(s)
log.append({'pages':'Все совпадения в шрифте InterV / SFProText-Regular','change':'Ошибочно отображаемые գ заменены маркерами •; ㈭ заменены исходным растровым значком ссылки.','basis':'Шрифт всех маркеров установлен по PDF; вид маркера сверён на страницах 9, 19, 70; значок ссылки извлечён из PDF страницы 70 и визуально просмотрен.','scope':'Исправление отображения шрифта не означает сверку текста всех страниц.'})
(p/'corrections.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n');(p/'pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n');(p/'table_structure.json').write_text(json.dumps(tin,ensure_ascii=False,indent=2)+'\n')
print('Tables',sum(len(x['tables']) for x in tin))
print('Nonuniform tables',[(x['pdf_page'],y['table'],y['widths']) for x in tin for y in x['tables'] if len(set(y['widths']))>1])
print('No headers',[(x['pdf_page'],y['table']) for x in tin for y in x['tables'] if not y['has_header_cells']])
