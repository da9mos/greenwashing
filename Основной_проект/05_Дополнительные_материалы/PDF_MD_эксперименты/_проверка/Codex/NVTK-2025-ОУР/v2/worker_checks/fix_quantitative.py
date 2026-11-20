exec(open('result/_проверка/reconstruct.py').read().split('for n,p in enumerate(doc,1):')[0])
bands={97:[(80,546,1282),(1494,264,681),(1494,751,1009),(1494,1074,1282)],98:[(80,314,1305),(1494,314,978),(1494,1036,1446)],99:[(80,266,1208),(80,1274,1666),(1494,266,733),(1494,794,1100),(1494,1166,1438)],100:[(80,266,668),(80,734,1300),(1494,266,590),(1494,674,815),(1494,878,1183)]}
for n,regions in bands.items():
 p=doc[n-1];chars=[];blocks=[]
 for bi,b in enumerate(p.get_text('rawdict')['blocks']):
  if b['type']!=0:continue
  bc=[]
  for li,l in enumerate(b['lines']):
   for sp in l['spans']:
    for c in sp['chars']:
     box=c['bbox'];v=dict(c=c['c'],bbox=box,center=((box[0]+box[2])/2,(box[1]+box[3])/2),size=sp['size'],sup=bool(sp['flags']&1),idx=len(chars),block=bi,line=(bi,li));chars.append(v);bc.append(v)
  blocks.append((bi,b['bbox'],bc))
 objects=[];claimed=set();shapes=[]
 for x,y0,y1 in regions:
  xs=[x,x+611,x+810.6,x+959.6,x+1110.8,x+1261];bbox=(x,y0,x+1261,y1);tc=[c for c in chars if inside(c,bbox)]
  starts=sorted(b[1] for bi,b,bc in blocks if x<=b[0]<x+1261 and y0<=b[1]<y1)
  grouped=[]
  for y in starts:
   if not grouped or y-grouped[-1]>10:grouped.append(y)
  ys=[y0]+[(a+b)/2 for a,b in zip(grouped,grouped[1:])]+[y1]
  # Use next block start minus a small margin: multi-line labels must stay with their first-line numeric values.
  ys=[y0]+[v-4 for v in grouped[1:]]+[y1]
  rows=[];used=set()
  for a,b in zip(ys,ys[1:]):
   cells=[]
   row=[c for c in tc if a<=c['center'][1]<b]
   if not row:continue
   for l,r in zip(xs,xs[1:]):
    cc=[c for c in row if l<=c['center'][0]<r];used|={c['idx'] for c in cc};cells.append('<td>'+esc(textof(cc)).replace('\n','<br>')+'</td>')
   rows.append('<tr>'+''.join(cells)+'</tr>')
  assert used=={c['idx'] for c in tc},n
  claimed|=used;objects.append({'index':min(used),'text':'<table>\n'+'\n'.join(rows)+'\n</table>'});shapes.append({'rows':len(rows),'columns':5})
 removed={c['idx'] for c in chars if c['center'][1]<80}
 for bi,b,bc in blocks:
  cc=[c for c in bc if c['idx'] not in claimed|removed]
  if not cc:continue
  t=textof(cc);prefix='## ' if max(c['size'] for c in cc)>=32 and len(t)<450 else '';objects.append({'index':min(c['idx'] for c in cc),'text':prefix+esc(t).replace('\n','  \n')})
 objects.sort(key=lambda o:o['index']);(dest/f'{n:04}.md').write_text('\n\n'.join(o['text'] for o in objects)+'\n')
 e=registry['pages'][n-1];e['tables']=len(regions);e['table_shapes']=shapes;e['issues'].append('Исправлен обрыв таблиц: табличные полосы приложения восстановлены целиком по координатам строк и колонок; полная визуальная сверка всех значений не выполнена.');e['corrections']=['Восстановлены все строки количественных таблиц под исходными колонками единиц и годов.']
(check/'pages.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2))
print('fixed',list(bands))
