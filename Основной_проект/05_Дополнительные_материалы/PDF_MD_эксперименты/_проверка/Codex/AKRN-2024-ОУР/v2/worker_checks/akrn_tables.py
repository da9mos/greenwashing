from pathlib import Path
import fitz,json,re,html
D=fitz.open(json.load(open('source.json'))['source_pdf']);p=Path('result/report.md');s=p.read_text();sp=re.split(r'<!-- pdf_page: (\d+) -->',s);P={int(sp[i]):sp[i+1] for i in range(1,len(sp),2)}
logs=[]
def cell(n,x0,y0,x1,y1):
 lines=[]
 for b in D[n-1].get_text('rawdict')['blocks']:
  for l in b.get('lines',[]):
   chars=[]
   for ss in l['spans']:
    for c in ss['chars']:
     a,b,cx,d=c['bbox'];x=(a+cx)/2;y=(b+d)/2
     if x0<=x<x1 and y0<=y<y1:chars.append(c['c'])
   if chars:lines.append((l['bbox'][1],l['bbox'][0],''.join(chars).strip()))
 return '<br/>'.join(html.escape(t) for y,x,t in sorted(lines) if t)
def manual(n,xs,bands,headers):
 out='<table>\n<tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr>\n'
 for y0,y1 in bands:out+='<tr>'+''.join('<td>'+cell(n,xs[j],y0,xs[j+1],y1)+'</td>' for j in range(len(xs)-1))+'</tr>\n'
 return out+'</table>'
# Specific repair: two independent trend tables, not one page-wide table.
a=manual(11,[42,143,412,555],[(114,273),(273,358),(443,561),(646,790)],['Тренд','Описание','Уровень значимости для Группы'])
b=manual(11,[638,739,1008,1150],[(112,240),(325,439),(439,543),(543,671)],['Тренд','Описание','Уровень значимости для Группы'])
P[11]=re.sub(r'<table>.*?</table>',a+'\n\n'+b,P[11],count=1,flags=re.S)
# Risk map plus separate risk table.
a='### Карта рисков\n\n<table><tr><th>Влияние / Вероятность</th><th>Низкая</th><th>Средняя</th><th>Высокая</th></tr><tr><td>Высокое</td><td>7</td><td></td><td></td></tr><tr><td>Среднее</td><td></td><td></td><td></td></tr><tr><td>Низкое</td><td>2, 5</td><td>3, 4, 6</td><td>1, 8</td></tr></table>\n\n### Список рисков\n\n'
for idx,name in enumerate(['Климатический','Геологический','Экологический','Кадровый','Нормативно-правовой','Информационная безопасность','Промышленная безопасность','Вред здоровью'],1):a+=f'{idx}. {name}\n'
a+='\n'+manual(15,[638,666,765,900,1153],[(114,200),(200,548.8),(548.8,793.3)],['№','Риск','Описание','Управление риском'])
P[15]=re.sub(r'<table>.*?</table>',a,P[15],count=1,flags=re.S)
# Remove only wholly empty artificial rows/columns from expenditure table.
tab=re.search(r'<table>.*?</table>',P[19],re.S).group();new=re.sub(r'<td[^>]*>\s*</td>','',tab);new=re.sub(r'<tr>\s*</tr>\n?','',new);P[19]=P[19].replace(tab,new)
def ruled(n,xs,ymin,ymax,desc_start):
 # Use source horizontal rules to recover row boundaries; a missing rule in the
 # last column is retained as a source rowspan, not replaced by a guessed value.
 lines=[]
 for dr in D[n-1].get_drawings():
  r=dr['rect']
  if r.height<.15 and r.width>100 and ymin-.2<=r.y0<=ymax+.2:lines.append(r)
 ys=sorted(set([round(ymin,1),round(ymax,1)]+[round(r.y0,1) for r in lines if abs(r.x0-desc_start)<2]))
 out='<table>\n';occupied={};count=0
 for i,(lo,hi) in enumerate(zip(ys,ys[1:])):
  out+='<tr>'
  for col in range(len(xs)-1):
   if occupied.get(col,0)>i:continue
   end=i+1
   if col==len(xs)-2:
    # Only right-column rules determine the end of merged comment cells.
    while end<len(ys)-1 and not any(abs(r.y0-ys[end])<.3 and r.x0<=xs[col]+2 and r.x1>=xs[col+1]-2 for r in lines):end+=1
   val=cell(n,xs[col],lo,xs[col+1],ys[end]);out+=f'<td rowspan="{end-i}">'+val+'</td>';occupied[col]=end
  out+='</tr>\n';count+=1
 out+='</table>';logs.append({'page':n,'bounds':[xs,ymin,ymax],'rows':count});return out
for n,configs in {61:[([638,991.3,1148.2],191.4,737.1,687.9)],62:[([42,396,553],97,800.9,92.6),([638,991.3,1148.2],97,800.9,687.9)],63:[([42,396,553],97,494.9,92.6),([638,950.2,1103.3,1148.2],199.1,801,712.1)],64:[([42,396,553],191.4,800.2,92.6),([638,991.3,1148.2],191.4,800.2,687.9)]}.items():
 replacements=[ruled(n,*c) for c in configs];it=iter(replacements);P[n]=re.sub(r'<table>.*?</table>',lambda m:next(it),P[n],flags=re.S)
 if n==63:
  # Last SASB row used to sit outside the detected table. It is now inside.
  a=P[n].index('<p>Управление нормативно-правовой средой</p>');b=P[n].index('<p>125</p>',a);P[n]=P[n][:a]+P[n][b:]
# Mark source-verification scope adjacent to every not fully reviewed page.
for n in range(1,66):
 if n not in [1,2]:P[n]=P[n].replace(f'<a id="pdf-page-{n}"></a>',f'<a id="pdf-page-{n}"></a>\n\n> Служебная пометка: полная сверка этой физической страницы по оригиналу не завершена (review_status: pending).')
p.write_text(sp[0]+''.join(f'<!-- pdf_page: {n} -->'+P[n] for n in range(1,66)))
Path('result/_проверка/table_repairs.json').write_text(json.dumps(logs,ensure_ascii=False,indent=2))
