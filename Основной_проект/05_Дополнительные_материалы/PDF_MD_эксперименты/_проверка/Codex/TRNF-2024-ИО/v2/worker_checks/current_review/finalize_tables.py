import sys,re,json
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
p=Path('result/report.md');text=p.read_text();parts=re.split(r'(?=<!-- pdf_page: \d+ -->)',text);prefix=parts.pop(0);chunks={int(re.search(r'pdf_page: (\d+)',c)[1]):BeautifulSoup(c,'html.parser') for c in parts}
def header(n,ti,labels):
 soup=chunks[n];t=soup.find_all('table')[ti];row=t.find('tr');new=soup.new_tag('tr')
 for label in labels:
  cell=soup.new_tag('th');cell.string=label;new.append(cell)
 row.replace_with(new)
fin=['Наименование','Год, закончившийся 31 декабря 2024 года','Год, закончившийся 31 декабря 2023 года','Абсолютное изменение','Изменение, %','Год, закончившийся 31 декабря 2022 года']
for n,ti in [(67,1),(68,0),(68,1),(69,1)]:header(n,ti,fin)
for ti,year,years in [(0,2024,['2025','2026','2027','2028','2029']),(1,2023,['2024','2025','2026','2027','2028'])]:
 header(70,ti,[f'31 декабря {year} года','Балансовая стоимость','Поток денежных средств по погашению финансовых обязательств — Всего']+years+['Более 5 лет'])
header(103,0,['Показатель','2024 — План','2024 — Факт','2025 — План'])
header(144,0,['Федеральный округ']+[f'Среднесписочная численность {y} — {c}' for y in [2022,2023,2024] for c in ['ВСЕГО','в том числе руководители, специалисты, служащие','в том числе рабочие']])
for n in [184,185]:header(n,0,['Принципы корпоративного управления','Принципы, рекомендованные ККУ']+[f'{y} — {c}' for y in [2022,2023,2024] for c in ['Соблюдается','Частично соблюдается','Не соблюдается']])
header(194,0,['Члены Совета директоров','Очные заседания Совета директоров (3 заседания)','Заочные заседания Совета директоров (20 заседаний)','Комитет по стратегии, инвестициям и инновациям (12 заседаний)','Комитет по аудиту (18 заседаний)','Комитет по кадрам и вознаграждениям (7 заседаний)'])
# p53 source subtotal labels span first two columns.
soup=chunks[53];rows=soup.find('table').find_all('tr')
for ri,label in [(1,'Всего по Программе развития, в т.ч.:'),(4,'Всего по инвестиционным проектам, в т.ч.:'),(7,'Всего по Программе технического перевооружения и реконструкции (ТПР), в т.ч.:')]:
 cells=rows[ri].find_all('td');cells[0].string=label;cells[0]['colspan']='2';cells[1].decompose()
# p185 label spans two rows.
soup=chunks[185];rows=soup.find('table').find_all('tr');rows[2].find('td').string='Общая оценка';rows[2].find('td')['rowspan']='2';rows[3].find('td').decompose()
# p194 Director 1 explicitly does not belong to committees.
soup=chunks[194];row=soup.find('table').find_all('tr')[1];cells=row.find_all('td');cells[3].string='не входит в состав Комитетов';cells[3]['colspan']='3';cells[4].decompose();cells[5].decompose()
# p70 revenue header restored with six real columns and source missing border preserved.
soup=chunks[70];t=soup.find_all('table')[2];rows=t.find_all('tr');rows[0].decompose();rows[1].decompose();new=soup.new_tag('tr')
for label in ['Наименование показателя','2024','2023','Изменение 2024/2023, млн руб.','Изменение 2024/2023, %','2022']:
 cell=soup.new_tag('th');cell.string=label;new.append(cell)
t.insert(0,new);last=rows[-1];cell=soup.new_tag('td');cell.string='в том числе:';last.insert(0,cell)
# p66 source-wide section row.
soup=chunks[66];t=soup.find_all('table')[1]
for row in t.find_all('tr'):
 cells=row.find_all('td',recursive=False)
 if cells and cells[0].get_text(strip=True)=='Корректировки:':
  cells[0]['colspan']='6'
  for cell in cells[1:]:cell.decompose()
p.write_text(prefix+''.join(str(chunks[n]) for n in range(1,304)))
print('headers finalized')
