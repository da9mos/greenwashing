import re,json,sys
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs');from bs4 import BeautifulSoup
r=Path(__file__).resolve().parents[1];s=(r/'report.md').read_text();parts=re.split(r'<!-- pdf_page: (\d+) -->',s)
labels={
5:[('№ Тема Ссылка на\u00a0раздел Отчета',['№','Тема','Ссылка на раздел Отчета'])],
7:[('Ценности Описание',['Ценности','Описание'])],
15:[('Сокращение эмиссии ПГ Охват 1 Охват 2 Охват 3 Охваты 1 + 2 Охваты 1 + 2 + 3',['Сокращение эмиссии ПГ','Охват 1','Охват 2','Охват 3','Охваты 1 + 2','Охваты 1 + 2 + 3'])],
77:[('Участник Ключевые функции',['Участник','Ключевые функции'])],
87:[('Ассоциация/инициатива Статус Группы НЛМК',['Ассоциация/инициатива','Статус Группы НЛМК'])],
93:[('Показатель Ссылка/комментарий Страница',['Показатель','Ссылка/комментарий','Страница'])],
94:[('№ Показатель Комментарий',['№','Показатель','Комментарий'])]}
for i in range(1,len(parts),2):
 n=int(parts[i]);t=parts[i+1]
 for label,heads in labels.get(n,[]):
  pat=r'<p>'+re.escape(label)+r'</p>\s*((?:<p>[^<]*</p>\s*){0,2})<table>'
  t=re.sub(pat,lambda m:m[1]+'<table>\n<tr>'+''.join('<th>'+x+'</th>' for x in heads)+'</tr>',t)
 if n in [38,45,66,92]:
  tables=list(re.finditer('<table>.*?</table>',t,re.S))
  for m in reversed(tables):
   table=m[0];soup=BeautifulSoup(table,'html.parser');row=soup.find('tr');texts=[x.get_text(' ',strip=True) for x in row.find_all('td')]
   expected={38:['Показатель'],45:['Основной принцип','Направления деятельности'],66:['Мероприятие','Описание мероприятия'],92:['Рекомендация TCFD']}.get(n)
   if texts and all(x in texts for x in expected):
    for cell in row.find_all('td'):cell.name='th'
    t=t[:m.start()]+str(soup)+t[m.end():]
 parts[i+1]=t
(r/'report.md').write_text(''.join(parts[j] if j%2==0 else '<!-- pdf_page: '+parts[j]+' -->' for j in range(len(parts))))
