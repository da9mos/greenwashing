from pathlib import Path
import pymupdf,json,csv,re
import argparse
ap=argparse.ArgumentParser();ap.add_argument('social_pdf',type=Path);ap.add_argument('output',type=Path);args=ap.parse_args();o=args.output;d=pymupdf.open(args.social_pdf);pg=d[114];w=pg.rect.width/2
changes=[]
# Case-specific table reconstruction from source geometry; no service results are read.
def source_table(offset):
 ys=[]
 for dr in pg.get_drawings():
  for it in dr['items']:
   if it[0]=='l':
    a,b=it[1],it[2]
    if abs(a.y-b.y)<.1 and abs(min(a.x,b.x)-(87.9+offset))<1 and abs(max(a.x,b.x)-(265.9+offset))<1 and 140<a.y<735:ys.append(round(a.y,2))
 ys=sorted(set(ys));bounds=[62,87.9,265.9,309.5,352,423.6,552.8];rows=[]
 words=pg.get_text('words')
 for y1,y2 in zip(ys,ys[1:]):
  row=[]
  for x1,x2 in zip(bounds,bounds[1:]):
   found=[v for v in words if x1+offset<=(v[0]+v[2])/2<x2+offset and y1<=(v[1]+v[3])/2<y2]
   found.sort(key=lambda v:(round(v[1]/3),v[0]));row.append(' '.join(v[4]for v in found))
  if any(row):
   row=[v.replace('26 882,575','26 882,57<sup>5</sup>').replace('17 806,485','17 806,48<sup>5</sup>')for v in row]
   if not any(re.match(r'^[+−–-]?\d',v)for v in row[2:4]):
    fw=[v for v in words if 87.9+offset<=(v[0]+v[2])/2<552.8+offset and y1<=(v[1]+v[3])/2<y2];fw.sort(key=lambda v:(round(v[1]/3),v[0]));row=[row[0], ' '.join(v[4]for v in fw), '', '', '', '']
   rows.append(row)
 return rows
parts=[];tabledata=[]
for i,offset in enumerate([0,w]):
 rows=source_table(offset);tabledata.append({'region':'left'if i==0 else'right','columns':[v+offset for v in [62,87.9,265.9,309.5,352,423.6,552.8]],'rows':rows,'source_pdf_page':115})
 headers=['Номер индикатора','Наименование индикатора','2022','2023','Изменение (абсолютное/относительное)','Факторный анализ изменений']
 parts.append('### '+('Левая'if i==0 else'Правая')+' печатная страница\n\n'+'| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*6)+' |\n'+'\n'.join('| '+' | '.join(v.replace('|','\\|')for v in row)+' |'for row in rows))
(o/'social_final/tables/115_source_geometry.json').write_text(json.dumps(tabledata,ensure_ascii=False,indent=2))
# Footnotes retained separately from original text, not rebuilt from a normalized parser.
foot=[]
for off in [0,w]:
 text=pg.get_text('text',clip=pymupdf.Rect(58+off,735,560+off,805));foot.append(text)
(o/'social_final/pages/115_reviewed.md').write_text('\n\n'.join(parts)+'\n\n### Примечания из исходной страницы\n\n'+'\n\n'.join(foot))
changes.append({'report':'social','pdf_page':115,'change':'Reconstruct two six-column tables using visually checked source coordinate boundaries; retain notes','basis':'source page geometry and image','status':'targeted_review'})
def source_paragraph(n,boxes):
 pg=d[n-1];ss=[]
 for box in boxes:
  v=pg.get_text('text',clip=pymupdf.Rect(box));v=v.replace('\xad\n','').replace('\xad','').replace('\xa0',' ');ss.append(' '.join(v.split()))
 return ' '.join(ss)
for n in [57,130]:
 s=(o/'social_final/pages'/f'{n:03d}_layout.md').read_text()
 if n==57:
  para=source_paragraph(n,[(62,284,235,332),(257,284,435,332)])
  s=re.sub(r'(?m)^Коэффициент частоты травматизма[^\n]*',lambda m:para,s,count=1)
  para=source_paragraph(n,[(62,636,235,674),(257,636,450,674)])
  s=re.sub(r'(?m)^Рост количества пострадавших[^\n]*',lambda m:para,s,count=1)
 else:
  para=source_paragraph(n,[(62,470,280,508),(306,404,530,465)])
  start=s.index('Федерации)');end=s.index('256',start);s=s[:start]+para+'\n\n'+s[end:]
 (o/'social_final/pages'/f'{n:03d}_reviewed.md').write_text(s)
 changes.append({'report':'social','pdf_page':n,'change':'Keep local layout tables; repair narrative order from original clipped text columns','basis':'source page geometry, no external parse','status':'targeted_review'})
for report in ['social_final','environment_final']:
 root=o/report;manifest=json.loads((root/'manifest.json').read_text());parts=[]
 for n in range(1,manifest['pdf_pages']+1):
  f=root/'pages'/f'{n:03d}_reviewed.md';md=(f if f.exists()else root/'pages'/f'{n:03d}.md').read_text();parts.append(f'<!-- pdf_page: {n}; review: pending_or_targeted -->\n## PDF-страница {n}\n\n'+md)
 (root/'document_working.md').write_text('# Газпром 2023: полностью локальное извлечение\n\nРабочая версия; адресные исправления записаны в corrections.csv, непросмотренные блоки pending.\n\n'+'\n\n'.join(parts))
with(o/'corrections.csv').open('w',encoding='utf-8-sig',newline='')as f:
 z=csv.DictWriter(f,fieldnames=list(changes[0]),delimiter=';');z.writeheader();z.writerows(changes)
print('Source table rows:',[len(v['rows'])for v in tabledata]);print('first values:',tabledata[0]['rows'][2:5])
