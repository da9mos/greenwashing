import sys,json,re,hashlib,collections,html
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf as f
from markdown_it import MarkdownIt
R=Path('result');A=R/'_проверка'; source=json.load(open('source.json'));doc=f.open(source['source_pdf'])
# Definitions used solely for coordinate rendering; conversion loops are not rerun.
code=(A/'convert.py').read_text().split('\nrecords=[]')[0]
exec(compile(code,'result/_проверка/convert.py','exec'))
records=json.loads((A/'pages.json').read_text())
rep={p['pdf_page']:p for p in json.loads((A/'repair-pages.json').read_text())}
chunks=[];changes=[]

def cell(p,rect):
 ls=[]
 for b in p.get_text('dict',clip=rect)['blocks']:
  for l in b.get('lines',[]):
   if abs(l['dir'][1])<.1:ls.append((l['bbox'][1],l['bbox'][0],''.join(s['text'] for s in l['spans'])))
 t='\n'.join(t.strip() for y,x,t in sorted(ls));t=t.replace('\u00ad\n','').replace('\u00ad','');t=clean(t)
 return html.escape(t).replace('|','&#124;').replace('\n','<br>')

def wide_table(n):
 p=doc[n-1];edges=[62.4,160.1,279.1,414.7,650.4,773.7,912.6,1133.0]
 ys=[]
 for d in p.get_drawings():
  r=d['rect']
  if r.height<1 and 60<r.x0<65 and 159<r.x1<162:ys.append(round(r.y0,1))
 ys=sorted(set(ys)); start=150.8 if n==108 else 81.2
 rows=[[cell(p,f.Rect(edges[j],start,edges[j+1],ys[0])) for j in range(7)]]
 for y0,y1 in zip(ys,ys[1:]):rows.append([cell(p,f.Rect(edges[j],y0+.1,edges[j+1],y1)) for j in range(7)])
 top=positional(p,f.Rect(35,0,1190,start-1))
 tail=positional(p,f.Rect(35,ys[-1]+1,1190,p.rect.height))
 t=fenced(top)+'\n| '+' | '.join(rows[0])+' |\n| '+' | '.join(['---']*7)+' |\n'
 for row in rows[1:]:t+='| '+' | '.join(row)+' |\n'
 if tail.strip():t+=fenced(tail)
 return t

for n in range(1,137):
 path=A/'repaired'/f'{n:03d}.md'
 if not path.exists():path=A/'pages'/f'{n:03d}.md'
 t=path.read_text();rec=rep.get(n,records['pages'][n-1]);records['pages'][n-1]=rec
 if n==1:
  t='<!-- pdf_page: 1 -->\n<a id="pdf-page-1"></a>\n\n# ВРЕМЯ быть ВМЕСТЕ\n\nГазпром\n\n‘23\n\nОтчет о социальной деятельности Группы Газпром\n\n> Техническая пометка: рабочая версия конвертации. Статусы извлечения и сверки каждой физической страницы приведены в `_проверка/pages.json`. Изображения страниц служат визуальной опорой. Таблицы с непроверенной структурой сохранены в координатном текстовом представлении.\n\n[Изображение физической страницы 1](assets/page-001.png)\n'
  rec['review_status']='checked';rec['issues']=[];rec['review_scope']='Вся обложка визуально сверена с исходным изображением.'
  changes.append({'page':1,'object':'обложка','change':'Восстановлено слово «БЫТЬ», прочитанное по изображению; период ‘23 сохранён отдельно от названия отчёта.'})
 if n in (6,7,68,76) or 108<=n<=113:
  first=t.split('> Техническая пометка:')[0]
  end=t[t.index('[Изображение физической страницы'):]
  body=wide_table(n) if 108<=n<=113 else fenced(positional(doc[n-1],doc[n-1].rect))
  t=first+'> Техническая пометка: полная визуальная сверка страницы ожидается.\n\n'+body+'\n\n'+end
  rec['extraction_methods']=['geometric_markdown_table' if 108<=n<=113 else 'full_spread_coordinate_text']
  rec['issues']=['Текст извлечён по всей площади разворота; полнота и связи блоков/ячеек требуют полной визуальной сверки.']
  changes.append({'page':n,'object':'разворот','change':'Устранено разрезание непрерывного содержимого по центру; для семиколоночных таблиц восстановлены строки и столбцы по координатам оригинала.'})
 if n==135:
  p=doc[n-1];parts=[]
  for r in [f.Rect(35,0,595,842),f.Rect(595,0,1190,842)]:
   bs=[b for b in p.get_text('blocks',clip=r) if b[1]>65]
   title=[b for b in bs if b[4].startswith('6.11.')]
   for b in title:parts.append('## '+clean(b[4]).replace('\n',' '))
   rows=[]
   for b in sorted(bs,key=lambda b:b[1]):
    if b in title:continue
    lines=b[4].strip().splitlines()
    if len(lines)>1:rows.append([clean(lines[0]),clean(' '.join(lines[1:]))])
   if rows:
    parts.append('| Сокращение | Наименование |\n|---|---|\n'+'\n'.join('| '+x.replace('|','\\|')+' | '+y.replace('|','\\|')+' |' for x,y in rows))
  if len(rows)>10:
   end=t[t.index('[Изображение физической страницы'):];t=t.split('> Техническая пометка:')[0]+'> Техническая пометка: полная визуальная сверка страницы ожидается.\n\n'+'\n\n'.join(parts)+'\n\n'+end
   rec['extraction_methods']=['geometric_glossary_table'];rec['issues']=['Глоссарий восстановлен по блокам текстового слоя; требуется визуальная сверка всех строк.']
 if n==12:
  blocks=list(re.finditer(r"```text\n.*?\n```",t,re.S))
  tables=[
   "| Показатель | 2021 | 2022 | 2023 | Изменение 2023/2022 |\n|---|---|---|---|---|\n| Доля Группы Газпром в валовом внутреннем продукте (ВВП) Российской Федерации, %<sup>1</sup> | 4,5 | 5,1 | 2,9 | –2,2 п. п. |\n| Выручка от продаж, млрд руб. | 10 241,4 | 11 674,0 | 8 541,8 | –26,8 % |\n| Социальные расходы, млрд руб. | 38,5 | 38,8 | 50,9 | +31,2 % |\n| Оплата труда, млрд руб. | 840,2 | 953,7 | 1 096,7 | +15,0 % |",
   "| Наименование | 2021 | 2022 | 2023 | Изменение 2023/2022, % |\n|---|---|---|---|---|\n| Налоги и сборы, страховые взносы | 6 797 073 | 9 728 521 | 8 195 232 | –15,8 |\n| Иные обязательные платежи | 4 797 | 3 074 | 4 673 | +52,0 |",
   "| Наименование | 2021 | 2022 | 2023 | Изменение 2023/2022, % |\n|---|---|---|---|---|\n| Налоги и сборы, страховые взносы | 3 309 720 | 5 380 536 | 3 523 989 | –34,5 |\n| Иные обязательные платежи | 3 174 | 3 294 | 3 585 | +8,8 |"]
  if len(blocks)==3:
   for block,table in reversed(list(zip(blocks,tables))):t=t[:block.start()]+table+t[block.end():]
  right=t.index('Один из крупнейших налогоплательщиков в России')
  tail=t[t.index('[Изображение физической страницы'):]
  t=t[:right]+(A/'page12-right.md').read_text()+'\n\n'+tail
  t=t.replace('сотрудничать с отечественными производителями, малым и средним бизнесом,\n\n\n\nразрабатывать','сотрудничать с отечественными производителями, малым и средним бизнесом, разрабатывать')
  t=t.replace('Вклад в развитие российской экономики','## Вклад в развитие российской экономики',1)
  rec['issues']=['Три числовые таблицы и порядок основных блоков сверены визуально и исправлены. Полная построчная сверка остального текста не заявлена.']
  rec['review_status']='pending';rec['review_scope']='Три таблицы: все заголовки, значения и знаки; порядок налоговых принципов; граница двухколоночного абзаца.'
  changes.append({'page':12,'object':'таблицы и колонки','change':'Три таблицы переведены в Markdown по изображению; знак сноски 1 отделён от единицы; восстановлено продолжение абзаца между колонками.'})
 if n==132:
  t=t.replace('PBK','ФБК').replace('специалиста ло заданию.','специалиста по заданию,').replace('2из3','2 из 3')
  t=re.sub(r'(?m)^[eе©»®] ', '- ',t)
  changes.append({'page':132,'object':'OCR','change':'Логотип ФБК и отдельные ошибочно распознанные маркеры/колонтитул исправлены по изображениям. Остальной OCR не считается полностью проверенным.'})
 if n==133:
  start=t.index('Российский союз промышленников и предпринимателей')
  end=t.index('[Изображение физической страницы')
  t=t[:start]+(A/'certificate.md').read_text()+'\n\n'+t[end:]
  t=t.replace('на основании доверенности № 130/21 от 09 сент','на основании доверенности № 130/21 от 09 сентября 2021 года')
  t=t.replace('Зиз3','3 из 3')
  rec['review_scope']='Свидетельство РСПП: прочитаны текст, регистрационный номер, должность, имя и место/год; проверена строка доверенности на левой части.'
  rec['issues']=['OCR тела левой части выполнен; полная посимвольная сверка всего заключения и мелких надписей печатей не заявлена. Свидетельство справа исправлено по изображению.']
  changes.append({'page':133,'object':'OCR свидетельства и заключения','change':'Восстановлены пропущенные OCR подпись должности/имени и Москва, 2024; исправлены слова в абзаце свидетельства и строка доверенности.'})
 # Preserve source images as actual embedded assets, inside collapsible technical support.
 t=re.sub(r'\[Изображение физической страницы (\d+)\]\((assets/[^)]+)\)',r'<details>\n<summary>Изображение физической страницы \1 — визуальная опора</summary>\n\n![Физическая страница \1](\2)\n\n</details>',t)
 # Promote typography-confirmed text headings only outside coordinate representations.
  # Existing coordinate blocks retain their exact line layout.
 if n not in (1,12):
  candidates=[]
  for block in doc[n-1].get_text('dict')['blocks']:
   ls=[l for l in block.get('lines',[]) if abs(l['dir'][1])<.1]
   spans=[s for l in ls for s in l['spans'] if s['text'].strip()]
   if spans and min(s['size'] for s in spans)>=13:
    label=clean(' '.join(s['text'] for s in spans));label=' '.join(label.split())
    if len(re.findall('[А-Яа-яA-Za-z]',label))>=5 and len(label)<230:candidates.append(label)
  segments=t.split('```')
  for k in range(0,len(segments),2):
   for label in candidates:
    pattern=r'(?m)^'+r'\s+'.join(re.escape(w) for w in label.split())+r'[ \t]*$'
    segments[k]=re.sub(pattern,'## '+label,segments[k])
  t='```'.join(segments)
 # Unclosed underline wrappers around links from automatic extraction are removed; text and URLs remain.
 t=t.replace('<u>','').replace('</u>','')
 t=re.sub(r'\n{4,}','\n\n\n',t)
 rec['text_chars']=len(t);rec['printed_label']=rec.get('printed_label')
 labels=[]
 for block in doc[n-1].get_text('blocks'):
  if block[1]<45 and re.fullmatch(r'\s*\d+\s*(?:[–−-]\s*\d+)?\s*',block[4]):labels.append(block[4].strip())
 rec['printed_label']=labels or None
 rec['annotation_links']=[]
 for l in doc[n-1].get_links():
  dest=l.get('uri') or ('#pdf-page-'+str(l['page']+1) if l.get('page',-1)>=0 else None)
  rec['annotation_links'].append({'bbox':list(l['from']),'destination':dest,'kind':l['kind']})
 if n!=1 and rec['review_status']!='checked':rec['review_status']='pending'
 chunks.append(t)
records['pages']=records['pages'][:136]
records['note']='converted означает извлечение текста; pending означает, что полная визуальная сверка страницы не завершена. Обзор миниатюр не является полной сверкой.'
(A/'pages.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
(R/'report.md').write_text('\n\n'.join(chunks))
(A/'corrections.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
md=MarkdownIt('commonmark',{'html':True}).enable('table')
body=md.render((R/'report.md').read_text())
css='body{font:16px/1.55 system-ui;margin:32px;max-width:1500px}pre{white-space:pre;overflow:auto;background:#f5f6f7;padding:16px;font:13px/1.4 monospace}table{display:block;overflow:auto;border-collapse:collapse;max-width:100%}td,th{border:1px solid #ccc;padding:8px;min-width:120px;vertical-align:top}details img{max-width:100%;height:auto}blockquote{background:#fff4dc;padding:8px 16px}h1,h2,h3{line-height:1.2}'
# This is a technical preview, not a replacement deliverable.
(A/'preview.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><base href="../"><title>Конвертация — проверка отображения</title><style>'+css+'</style><body>'+body+'</body></html>')
print('assembled',len(chunks),'pages',len(body),'html chars')
