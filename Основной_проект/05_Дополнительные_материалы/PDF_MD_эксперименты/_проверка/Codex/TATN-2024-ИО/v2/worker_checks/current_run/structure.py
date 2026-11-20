exec(open('result/_проверка/current_run/editorial.py').read().split("s=Path('result/report.md')")[0])
def cleantext(t):return " ".join(t.split())

s=Path('result/report.md').read_text();a=re.split(r'<!-- pdf_page: (\d+) -->',s);doc=pymupdf.open(json.load(open('source.json'))['source_pdf'])
# Remove detector-only empty columns on the visually reviewed separators, then split individual entries.
for n in [3,18,22,30,45,55,83,103,117,125,141,167]:
 soup=BeautifulSoup(a[n*2],'html.parser')
 for table in soup.find_all('table'):
  rows=[]
  for tr in table.find_all('tr'):
   cells=[c for c in tr.find_all('td',recursive=False) if c.get_text(strip=True)]
   if len(cells)!=2:continue
   ts=[cleantext(x) for x in cells[0].get_text('\n').split('\n') if cleantext(x)];ns=[cleantext(x) for x in cells[1].get_text('\n').split('\n') if cleantext(x)]
   merged=[]
   for x in ts:
    if x.startswith(('и расследование','и климатической','культурного и','с коренным','традиционный','Кодекса','об устойчивом','в реализацию')) and merged:merged[-1]+=' '+x
    else:merged.append(x)
   if len(merged)!=len(ns):raise ValueError((n,merged,ns))
   rows.extend(zip(merged,ns))
  if rows:
   new=soup.new_tag('table')
   for title,num in rows:
    tr=soup.new_tag('tr')
    for val in [title,num]:td=soup.new_tag('td');td.string=val;tr.append(td)
    new.append(tr)
   table.replace_with(new)
 a[n*2]=str(soup)
# Two TOC destinations share their text span with their labels.
a[4]=a[4].replace('| Система мотивации членов органов управления 230 |  |','| Система мотивации членов органов управления | 230 |').replace('| Взаимодействие с акционерами и инвесторами 278 |  |','| Взаимодействие с акционерами и инвесторами | 278 |')
# Rebuild only page 178's visually inspected two tables with explicit cell boundaries.
p=doc[177];w,h=p.rect.width,p.rect.height
# Coordinates taken from the viewed 2016 x 1238 reference; use native text in each rectangle.
def cell(x0,y0,x1,y1):
 r=pymupdf.Rect(x0/2016*w,y0/1238*h,x1/2016*w,y1/1238*h)
 t=p.get_textbox(r);return html.escape(t).replace('\n','<br/>')
headers=['№','Принципы корпоративного управления','Критерии оценки соблюдения принципа корпоративного управления','Статус соответствия принципу корпоративного управления','Объяснения отклонения от критериев оценки соблюдения принципа корпоративного управления']
parts=[]
for section,title,cols,rs in [('6.1','Общество и его деятельность являются прозрачными для акционеров, инвесторов и иных заинтересованных лиц',[106,150,328,562,714,935],[(239,680,'6.1.1','частично соблюдается'),(680,967,'6.1.2','частично соблюдается')]),('6.2','Общество своевременно раскрывает полную, актуальную и достоверную информацию об Обществе для обеспечения возможности принятия обоснованных решений акционерами Общества и инвесторами',[1087,1134,1307,1542,1696,1913],[(254,548,'6.2.1','соблюдается'),(548,1053,'6.2.2','частично соблюдается')])]:
 table='<h3>'+section+' '+title+'</h3>\n<table><tr>'+''.join('<th>'+x+'</th>' for x in headers)+'</tr>\n'
 for y0,y1,num,status in rs:
  vals=[num,cell(cols[1],y0,cols[2],y1),cell(cols[2],y0,cols[3],y1),'☑ '+status,cell(cols[4],y0,cols[5],y1)]
  table+='<tr>'+''.join('<td>'+v+'</td>' for v in vals)+'</tr>\n'
 table+='</table>';parts.append(table)
t=a[356];beg=t[:t.index('<table>')];tail=t[t.index('> Служебная информация: ссылки исходного PDF'):];a[356]=beg+'\n\n'.join(parts)+'\n\n'+tail
# Associate all years in the first table on page 67 directly with their columns.
t=a[134];header='<tr><th>Установленные цели</th><th>Показатель</th><th>2021 — базовый год</th><th>2022</th><th>2023</th><th>2024</th><th>2030 — целевой год</th></tr>'
t=t.replace('<table>','<table>\n'+header,1);a[134]=t
# Captions extracted by clipped annotation rectangles can be fragments; replace technical list captions, preserve all actual targets.
for n in range(1,201):
 t=a[n*2]
 if '> Служебная информация: ссылки исходного PDF' in t:
  pre,tail=t.split('> Служебная информация: ссылки исходного PDF',1)
  tail=re.sub(r'(<a href="([^"]+)">).*?(</a>)',lambda m:m[1]+('Переход к PDF-странице '+m[2].split('-')[-1] if m[2].startswith('#pdf-page-') else html.escape(m[2]))+m[3],tail)
  a[n*2]=pre+'> Служебная информация: ссылки исходного PDF'+tail
Path('result/report.md').write_text(a[0]+''.join('<!-- pdf_page: '+a[i]+' -->'+a[i+1] for i in range(1,len(a),2)))
print('Structure saved')
