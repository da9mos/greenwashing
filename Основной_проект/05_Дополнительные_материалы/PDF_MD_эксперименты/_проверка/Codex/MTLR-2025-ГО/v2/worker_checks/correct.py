import fitz,json,re,html,hashlib
from pathlib import Path
root=Path('result'); src=json.load(open('source.json')); doc=fitz.open(src['source_pdf'])
s=(root/'_проверка/report.native.md').read_text(); parts=re.split(r'<!-- pdf_page: (\d+) -->',s); pages={int(parts[i]):parts[i+1] for i in range(1,len(parts),2)}
log=[]
# OCR supplements are retained in the versioned candidate; replace confirmed artifacts separately.
for n,t in pages.items():
 if n!=7 and '> Служебная пометка: распознанный' in t:
  pages[n]=re.sub(r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\.\n\n.*?(?=> Служебная информация: ссылки|<details>)','',t,flags=re.S)
  log.append({'page':n,'change':'Удалено отдельное дополнение OCR: повторные обрывки текстового слоя/декора. Исходное дополнение сохранено в report.native.md.','scope':'OCR supplement only; body not certified'})
# Recover independent appendix halves, rows and columns from source coordinates.
headers=['№','Принципы корпоративного управления','Критерии оценки соблюдения принципа корпоративного управления','Статус соответствия принципу корпоративного управления','Объяснения отклонения от критериев оценки соблюдения принципа корпоративного управления']
counts={}
for n in range(53,67):
 p=doc[n-1];lines=[]
 for b in p.get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   spans=l['spans']; text=''.join(z['text'] for z in spans)
   if not text.strip():continue
   lines.append({'x':l['bbox'][0],'y':l['bbox'][1],'t':text,'spans':spans})
 out=[];records=[]
 for half in [0,1]:
  lo,hi=(35,650) if half==0 and n==60 else ((670,1150) if half==1 and n==60 else ((35,590) if half==0 else (600,1150)))
  ls=[l for l in lines if lo<=l['x']<hi and 68<=l['y']<625]
  # Page 53 has explicit full headers above numbered header at y=107.
  if n==53 and half==0:ls=[l for l in ls if l['y']>=122] # right half starts continuation at 123
  nums=[l for l in ls if l['x']<lo+40 and re.fullmatch(r'\d+(?:\.\d+){1,2}',l['t'].strip())]
  nums.sort(key=lambda l:l['y'])
  # Right page 53 starts at 123? inspect numbers below; bounds use actual starts.
  bounds=[(l['y']-7,l['t'].strip()) for l in nums]
  if not bounds: raise RuntimeError((n,half,'no rows'))
  table=['<table>','<tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr>']
  cutmap={
 53:[[74,192,414,510],[650,805,995,1085]],
 54:[[74,200,343,437],[640,766,909,1003]],
 55:[[74,200,340,437],[636,762,906,999]],
 56:[[74,200,340,437],[636,762,906,999]],
 57:[[74,200,343,437],[636,762,902,999]],
 58:[[74,200,347,437],[636,762,906,999]],
 59:[[74,200,406,495],[636,762,909,999]],
 60:[[74,178,411,498],[707,833,1009,1087]],
 61:[[74,200,440,525],[640,807,1014,1095]],
 62:[[74,200,423,512],[640,780,938,1020]],
 63:[[74,200,427,512],[640,780,946,1020]],
 64:[[74,210,339,420],[636,769,898,980]],
 65:[[74,210,362,455],[636,769,902,980]],
 66:[[74,207,340,420],[638,771,900,982]]}
  cuts=cutmap[n][half]
  # actual left cuts 75,205,335,420; right 635,765,898,979
  for idx,(y,num) in enumerate(bounds):
   end=bounds[idx+1][0] if idx+1<len(bounds) else 625
   row=[l for l in ls if y<=l['y']<end]
   if num.count('.')==1:
    body=[l for l in row if l not in nums];body.sort(key=lambda l:(l['y'],l['x']))
    table.append('<tr><td>'+num+'</td><td colspan="4">'+'<br/>'.join(html.escape(l['t']) for l in body)+'</td></tr>');continue
   cells=[[] for _ in range(5)]
   for l in row:
    c=sum(l['x']>=v for v in cuts)
    if l['t'].strip()=='X':
     z=l['spans'][0];l=dict(l);l['t']='☒' if z.get('alpha',255)==0 else '☐'
    cells[c].append(l)
   txt=[]
   for c in cells:
    c.sort(key=lambda l:(round(l['y'],1),l['x']))
    if c is cells[3]:
     checks=[l for l in c if l['t'] in ['☒','☐']]
     if len(checks)!=3: raise RuntimeError((n,num,'checkbox count',len(checks)))
     txt.append('<br/>'.join(l['t']+' '+label for l,label in zip(checks,['соблюдается','частично соблюдается','не соблюдается'])))
    else: txt.append('<br/>'.join(html.escape(l['t']) for l in c))
   table.append('<tr>'+''.join('<td>'+t+'</td>' for t in txt)+'</tr>')
   records.append({'number':num,'half':half,'y0':y,'y1':end,'columns':txt})
  table.append('</table>');out.append('\n'.join(table))
 # Keep source page image and annotation links verbatim.
 old=pages[n];tail=old[old.index('> Служебная информация: ссылки'): ] if '> Служебная информация: ссылки' in old else old[old.index('<details>'):]
 pages[n]='\n<a id="pdf-page-%d"></a>\n\n'%n+'\n\n'.join(out)+'\n\n'+tail
 counts[n]=len(records)
 (root/f'_проверка/table_rows_{n}.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
 log.append({'page':n,'change':'Две независимые половины приложения восстановлены из исходных строк PDF в отдельные таблицы с пятью столбцами; строки разделены по номерам принципов. Отметки ☒/☐ восстановлены по параметрам исходных объектов X и проверяемому изображению.','scope':'structural correction, full semantic review pending'})
(root/'_проверка/corrections.json').write_text(json.dumps(log,ensure_ascii=False,indent=2))
(root/'_проверка/table_counts.json').write_text(json.dumps(counts))
# Save progress for further manual corrections.
(root/'report.md').write_text('# ГОДОВОЙ ОТЧЁТ 2025\n\n> Служебная информация: рабочая конвертация. Полная постраничная сверка по оригиналу не завершена; статусы и ограничения — в `_проверка/pages.json`.\n\n'+''.join(f'<!-- pdf_page: {n} -->'+pages[n] for n in range(1,70)))
