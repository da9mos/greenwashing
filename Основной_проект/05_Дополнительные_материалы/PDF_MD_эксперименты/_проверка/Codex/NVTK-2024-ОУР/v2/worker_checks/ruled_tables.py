import html,re
import pymupdf

def tables(p):
 lines=[l for b in p.get_text('dict')['blocks'] if b['type']==0 for l in b['lines']]
 def txt(l):return ''.join(s['text'] for s in l['spans']).strip()
 drawings=p.get_drawings();result=[]
 zones=[(40,1145)] if p.number+1 in (104,105) else [(40,590),(595,1145)]
 for left,right in zones:
  ls=[l for l in lines if left<=l['bbox'][0]<right and l['bbox'][1]>42]
  # Each header signature comes directly from visible source wording.
  starts=[l for l in ls if txt(l) in ('Номер','Стандарт','Ед. изм.','Раздел','Принцип','Риск/Критичность/Влияние на цели','Ключевые темы в\xa02024\xa0году')]
  for start in starts[:1]:
   y0=start['bbox'][1]-2
   if txt(start)=='Раздел':
    keys=['Раздел','Элемент отчетности','Информация и'];label=True
   elif txt(start)=='Принцип':
    keys=['Принцип','Описание'];label=True
   elif txt(start).startswith('Риск/'):
    keys=['Риск/','Статус риска/'];label=True
   elif txt(start).startswith('Ключевые темы'):
    keys=['Ключевые темы','Основные мероприятия','Формы взаимодействия','Взаимодействие на'];label=True
   elif txt(start)=='Ед. изм.':
    keys=['Ед. изм.','2022','2023','2024']; label=False
   elif txt(start)=='Номер': keys=['Номер','Показатель','Расположение в тексте Отчета / Комментарии','Границы'];label=True
   else:keys=['Стандарт','Показатель','Расположение в тексте Отчета / Комментарии','Границы','Внешнее'];label=True
   hs=[]
   for key in keys:
    found=[l for l in ls if txt(l).startswith(key) and abs(l['bbox'][1]-start['bbox'][1])<(25 if txt(start)=='Стандарт' else 5)]
    if not found:break
    hs.append(found[0])
   if len(hs)!=len(keys):continue
   # Source drawing segment endpoints define horizontal row limits.
   ys=[];xs=[]
   for dr in drawings:
    for it in dr['items']:
     if it[0]=='l':
      a,b=it[1:3]
      if abs(a.y-b.y)<.2 and abs(a.x-b.x)>35 and left-3<=min(a.x,b.x)<right and max(a.x,b.x)<=right+3 and a.y>y0:
       ys.append(a.y);xs.extend([a.x,b.x])
     elif it[0]=='re':
      r=it[1]
      if left-3<=r.x0<right and r.x1<=right+3 and r.width>200 and r.y0>y0:
       ys.extend([r.y0,r.y1]);xs.extend([r.x0,r.x1])
   ys=sorted(set(round(y,1) for y in ys))
   if not ys:continue
   # Ignore unrelated strokes above table header, keep all actual ruled rows.
   yhead=max(l['bbox'][3] for l in ls if abs(l['bbox'][1]-start['bbox'][1])<20)
   ys=[y for y in ys if y>=yhead-1]
   if not ys:continue
   x0=min(xs);x1=max(xs)
   boundaries=[x0]+[l['bbox'][0]-3 for l in hs[1:] ]+[x1] if label else [x0]+[l['bbox'][0]-3 for l in hs]+[x1]
   if any(b<=a for a,b in zip(boundaries,boundaries[1:])):continue
   # Numerical headers are right aligned: boundaries between adjacent numeric
   # columns are midpoints between preceding right edge and next left edge.
   if not label:
    boundaries=[x0,hs[0]['bbox'][0]-3]+[(hs[j-1]['bbox'][2]+hs[j]['bbox'][0])/2 for j in range(1,len(hs))]+[x1]
   header_end=round(start['bbox'][1]+(48 if txt(start)=='Стандарт' else 21 if txt(start)=='Номер' else 12),1)
   edges=sorted(set([y0]+([header_end] if not any(abs(y-header_end)<4 for y in ys) else [])+ys))
   table=[]
   for ri,(a,b) in enumerate(zip(edges,edges[1:])):
    row=[]
    for xa,xb in zip(boundaries,boundaries[1:]):
     cell=[]
     for l in ls:
      r=pymupdf.Rect(l['bbox']);cy=(r.y0+r.y1)/2;cx=(r.x0+r.x1)/2
      if a<=cy<b and xa<=cx<xb:
       cell.append((r.y0,r.x0,txt(l)))
     cell.sort();val=' '.join(c[2] for c in cell)
     val=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',val)
     row.append(html.escape(val))
    if any(row):table.append(row)
   if not table:continue
   content='<table>\n'+''.join('<tr>'+''.join(('<th>' if i==0 else '<td>')+c+('</th>' if i==0 else '</td>') for c in row)+'</tr>\n' for i,row in enumerate(table))+'</table>'
   result.append({'bbox':(x0,y0,x1,ys[-1]+.1),'text':content,'rows':len(table),'columns':len(boundaries)-1,'method':'native lines assigned to ruled rows and header columns'})
 return result
