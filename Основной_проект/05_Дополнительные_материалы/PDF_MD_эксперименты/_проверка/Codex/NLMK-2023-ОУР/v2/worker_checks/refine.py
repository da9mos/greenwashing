import sys,json,re,html,hashlib
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1]
src=json.loads((root.parent/'source.json').read_text())
pdf=pymupdf.open(src['source_pdf'])
reg=json.loads((root/'_проверка/pages.json').read_text())
s=(root/'_проверка/report.native.md').read_text()
parts=re.split(r'<!-- pdf_page: (\d+) -->',s)
log=[]
for i in range(1,len(parts),2):
 n=int(parts[i]);t=parts[i+1];page=pdf[n-1];rec=reg['pages'][n-1]
 # Restore paragraphs using only native PDF block membership, without reordering glyphs.
 native=rec['objects']; tags=list(re.finditer(r'<p>.*?</p>|<table>.*?</table>',t,re.S))
 lines=[]
 for bi,b in enumerate(page.get_text('dict')['blocks']):
  for li,l in enumerate(b.get('lines',[])):
   spans=l['spans'];lines.append((bi,li,l['bbox'],spans))
 out=[];last=0;previous=None;joined=0
 if len(tags)!=len(native): raise ValueError((n,len(tags),len(native)))
 for m,obj in zip(tags,native):
  raw=m.group();prefix=t[last:m.start()];last=m.end()
  key=None;level=None
  if obj['kind']=='text':
   bb=obj['bbox']; candidates=[z for z in lines if abs(z[2][1]-bb[1])<.2 and abs(z[2][3]-bb[3])<.2 and z[2][0]<=bb[0]+.2 and z[2][2]>=bb[2]-.2]
   if len(candidates)==1:
    z=candidates[0];key=z[0];spans=z[3]
    text=html.unescape(re.sub('<[^>]+>','',raw));size=max(x['size'] for x in spans)
    bold=all(x['flags']&16 for x in spans if x['text'].strip())
    if bold and size>=10.4 and sum(c.isalpha() for c in text)>3:
     level=2 if size>=18 else 3
  if key is not None and previous and previous[0]==key and previous[1]==level and re.fullmatch(r'\s*',prefix) and out[-1].endswith('</p>') and raw.startswith('<p>'):
   old=out[-1][:-4];content=raw[3:];separator='<br/>' if old.rstrip().endswith(('-', '\xad')) else ' '
   out[-1]=old+separator+content;joined+=1
  else:out.append(prefix+raw)
  previous=(key,level) if key is not None else None
 out.append(t[last:]);t=''.join(out)
 # Heading promotion is confined to the same source blocks just identified.
 # Match original block text to the coalesced native paragraph, ignoring markup and line spaces.
 heading_blocks=[]
 for b in page.get_text('dict')['blocks']:
  spans=[sp for l in b.get('lines',[]) for sp in l['spans'] if sp['text'].strip()]
  if not spans:continue
  txt=' '.join(sp['text'].strip() for sp in spans)
  if all(sp['flags']&16 for sp in spans) and min(sp['size'] for sp in spans)>=10.4 and sum(c.isalpha() for c in txt)>3:
   heading_blocks.append((''.join(txt.split()),2 if max(sp['size'] for sp in spans)>=18 else 3))
 def heading(m):
  text=''.join(html.unescape(re.sub('<[^>]+>','',m[1])).split())
  for txt,level in heading_blocks:
   if text==txt:return f'<h{level}>{m[1]}</h{level}>'
  return m[0]
 t=re.sub(r'<p>(.*?)</p>',heading,t,flags=re.S)
 t=re.sub(r'<p>\s*</p>\s*','',t)
 if n in [1,9,24,80]:
  t,count=re.subn(r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\.\s*.*?(?=\n> Служебная информация:|\n<details>)','',t,flags=re.S)
  log.append({'page':n,'change':'Удалён отдельный блок ошибочных OCR-дублей; исходный текстовый слой сохранён.','basis':'Просмотр исходной страницы и конфликтов OCR.','blocks':count})
 if n==1:
  t=re.sub(r'<p>Отчет</p>\s*<p>об устойчивом</p>\s*<p>развитии</p>\s*<p>2023</p>','<p>НЛМК</p>',t)
 if n in [19,70,80]:
  t=t.replace('\x08','⚡').replace('\x07','')
  log.append({'page':n,'change':'Исправлены управляющие символы шрифтов: значок мощности заменён на ⚡; невидимые префиксы удалены.','basis':'Увеличенные фрагменты исходных страниц.'})
 parts[i+1]=t
 rec['review_status']='pending';rec['verification_scope']='Механическое извлечение; полная сверка страницы по оригиналу не выполнена.'
 rec['conversion_status']='converted';rec['semantic_source_review_completed']=False
 rec['paragraph_joins']=joined
 rec['issues']=list(rec.get('issues',[]))+['Полная постраничная сверка текста, порядка чтения и связей не выполнена.']
 (root/'_проверка/progress.json').write_text(json.dumps({'last_page':n,'stage':'native_paragraphs'},ensure_ascii=False))
# Targeted table repairs; data cells are taken from the existing native candidate.
def get(n):return parts[parts.index(str(n))+1]
def put(n,t):parts[parts.index(str(n))+1]=t
t=get(13);m=re.search(r'<table>.*?</table>',t,re.S);soup=BeautifulSoup(m[0],'html.parser');rows=soup.find_all('tr');vals=[[c.decode_contents() for c in r.find_all('td')] for r in rows]
new=[]
for j,row in enumerate(vals):
 if j==7:continue
 if j==8:row=row[:6]+['31\u00a0754']
 elif j>=9:row=row[:6]+[''.join(row[6:])]
 new.append(row)
header='<tr><th>Показатель</th><th>2018<sup>1</sup></th>'+''.join(f'<th>{y}</th>' for y in range(2019,2024))+'</tr>'
table='<table>\n'+header+'\n'+'\n'.join('<tr>'+''.join('<td>'+c+'</td>' for c in row)+'</tr>' for row in new)+'\n</table>'
prefix=t[:m.start()];prefix=re.sub(r'<p>Показатель</p>\s*<p>2018<sup>1</sup></p>\s*<p>2019</p>\s*<p>2020</p>\s*<p>2021</p>\s*<p>2022</p>\s*<p>2023</p>\s*$','',prefix)
t=prefix+table+t[m.end():];t=t.replace('\n\n<p>31</p>\n','\n');put(13,t)
log.append({'page':13,'object':'Таблица прямой и косвенной эмиссии','change':'Восстановлено семь столбцов, добавлена исходная шапка, устранена ложная пустая строка и склеены фрагменты чисел 2023 года.','basis':'Все ячейки таблицы сверены с увеличенным изображением crop_13.png.','review_status':'checked'})
t=get(9);m=re.search(r'<table>.*?</table>',t,re.S);soup=BeautifulSoup(m[0],'html.parser');grid=[]
for r in soup.find_all('tr'):
 row=[]
 for c in r.find_all('td'):row += [c.decode_contents()]+['']*(int(c.get('colspan',1))-1)
 grid.append(row)
def cell(start,end,cols):
 return '<br/>'.join(grid[r][c] for r in range(start,end) for c in cols if grid[r][c]).replace('գ','•')
rows=[]
for k,(a,b) in enumerate([(4,12),(12,18),(18,27)]):
 area=cell(4,12,[0]) if k==0 else ''
 goal=['4. КАЧЕСТВЕННОЕ ОБРАЗОВАНИЕ','8. ДОСТОЙНАЯ РАБОТА И ЭКОНОМИЧЕСКИЙ РОСТ','11. УСТОЙЧИВЫЕ ГОРОДА И НАСЕЛЕННЫЕ ПУНКТЫ'][k]
 rows.append('<tr>'+ (f'<td rowspan="3">{area}</td>' if k==0 else '')+f'<td>{goal}<br/>{cell(a,b,[1,2,3])}</td><td>{cell(a,b,[4])}</td><td>{cell(a,b,[5])}</td></tr>')
table='<h3>Развитие сотрудников и регионов присутствия</h3>\n<table><tr><th>Область деятельности</th><th>ЦУР ООН</th><th colspan="2">Вклад Группы НЛМК</th></tr>'+''.join(rows)+'</table>'
t=t[:m.start()]+'<p>О Компании · Охрана окружающей среды</p>\n'+table+t[m.end():];put(9,t)
log.append({'page':9,'object':'Таблица ЦУР','change':'Устранены ложные столбцы и строки; фрагменты исходных ячеек объединены по трём областям ЦУР; добавлены прочитанные подписи значков ЦУР.','basis':'Исходная страница и crop_9.png, сверка текста и числовых показателей таблицы.','review_status':'checked'})
# An invalid URI in the PDF annotation is corrected only because the printed URL is legible.
t=get(18);t=t.replace('ttps://www.eia.gov/totalenergy/data/monthly/pdf/mer.pdf','https://www.eia.gov/totalenergy/data/monthly/pdf/mer.pdf').replace('hhttps://','https://');put(18,t)
log.append({'page':18,'change':'Восстановлена начальная h в напечатанном URL EIA; исходная аннотация PDF содержит ttps://.','basis':'Прочитан адрес в нижнем примечании правой страницы, crop_18.png.'})
# Keep the title ahead of technical notes, as requested by AGENT.md.
parts[0]='# Отчет об устойчивом развитии 2023\n\n> Служебная информация: рабочая версия полной конвертации. Все 96 физических страниц перенесены; полная сверка с оригиналом не выполнена. Статусы и ограничения приведены в `_проверка/pages.json`. Исходные страницы доступны под раскрываемыми блоками.\n\n'
for n in [1,10,69,86]:
 rec=reg['pages'][n-1];rec['review_status']='checked';rec['semantic_source_review_completed']=True;rec['issues']=[];rec['verification_scope']='Весь текст обложки/разделителя сверен с исходным изображением. Графика сохранена.'
for n in [9,13,18,19,24,70,80]:
 rec=reg['pages'][n-1];rec['diagnostics_reviewed']=True;rec['reviewed_objects']=[x for x in log if x['page']==n]
 rec['issues']=['Полная сверка страницы не завершена; проверены только перечисленные объекты.']
 if n in [13,19,70]:rec['issues']+=['Нужна полная проверка связей подписей диаграмм/схем и порядка чтения.']
 if n==24:rec['issues']+=['Мелкие надписи на мониторах внутри фотографии не транскрибированы; они сохранены в исходном изображении. Текст тела доступен в текстовом слое.']
reg['source_pdf_sha256']=hashlib.sha256(Path(src['source_pdf']).read_bytes()).hexdigest()
reg['physical_pages']=len(pdf)
(root/'report.md').write_text(''.join(parts[j] if j%2==0 else '<!-- pdf_page: '+parts[j]+' -->' for j in range(len(parts))))
(root/'_проверка/pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n')
(root/'_проверка/corrections.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n')
print('Saved',len(pdf),'pages; joins',sum(x['paragraph_joins'] for x in reg['pages']))
