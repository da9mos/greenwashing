import pathlib,json,re,subprocess,html,collections,zipfile
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
O=pathlib.Path('result');A=O/'_проверка';P=A/'pages';s=json.load(open('source.json'));D=pymupdf.open(s['source_pdf']);registry=json.load(open(A/'pages.json'))
# Keep the previous extraction before correcting it.
if not (A/'initial_extraction.zip').exists():
 with zipfile.ZipFile(A/'initial_extraction.zip','w',zipfile.ZIP_DEFLATED) as z:
  z.write(O/'report.md','report.md');z.write(A/'pages.json','pages.json')
  for f in P.glob('*.md'):z.write(f,'pages/'+f.name)
DIGITS={0xf639:'0',0xf6dc:'1',0xf63a:'2',0xf63b:'3',0xf63c:'4',0xf63d:'5',0xf63e:'6',0xf63f:'7',0xf640:'8',0xf641:'9'}
def fix(t):return t.translate(DIGITS).replace('\x07','').replace('\x08','').replace('\ufeff','')
def layout(n,side):
 f=A/f'layout_{n:04}_{side+1}.txt'
 if not f.exists():
  w=595 if D[n-1].rect.width>800 else 596
  t=subprocess.check_output(['pdftotext','-f',str(n),'-l',str(n),'-layout','-x',str(side*595),'-y','65','-W',str(w),'-H','730',s['source_pdf'],'-']).decode()
  f.write_text(t)
 return fix(f.read_text()).replace('\f','').rstrip()

def layout_md(n,side):
 t=layout(n,side)
 return '```text\n'+t+'\n```'

def raw_lines(n,side):
 out=[]
 for b in D[n-1].get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   if side*595.275<=l['bbox'][0]<(side+1)*595.275:
    out.append(l)
 return out

def cell(lines,x0,x1,y0,y1):
 out=[]
 for l in sorted(lines,key=lambda z:(round(z['bbox'][1],1),z['bbox'][0])):
  ss=[]
  for sp in l['spans']:
   x,y,xx,yy=sp['bbox']
   if x0<=x<x1 and y0<=y<y1:
    t=html.escape(fix(sp['text']).strip())
    if sp['size']<6:t='<sup>'+t+'</sup>'
    ss.append(t)
  if ss:out.append(''.join(ss))
 return '<br>'.join(out)

def indicators(n,side,end):
 off=side*595.275;ls=raw_lines(n,side);anchors=[]
 for l in ls:
  x,y,xx,yy=l['bbox'];t=''.join(sp['text'] for sp in l['spans']).strip()
  if not(160<y<end):continue
  if 55<x-off<80 and re.fullmatch(r'\d{1,2}(?:\.\d)?',t):anchors.append((y,'id',t))
  elif 55<x-off<140 and t.startswith('Индикаторы оценки'):anchors.append((y,'group',t))
  elif 115<x-off<140 and t.startswith('•'):anchors.append((y,'sub',t))
 anchors.sort();body=[]
 bounds=[56,110,278,326,382,440,540]
 for j,(y,kind,t) in enumerate(anchors):
  ymax=anchors[j+1][0]-.2 if j+1<len(anchors) else end
  cells=[cell(ls,off+bounds[k],off+bounds[k+1],y-.2,ymax) for k in range(6)]
  if kind=='group':
   body.append('<tr><th colspan="6">'+cell(ls,off+56,off+540,y-.2,ymax)+'</th></tr>')
  elif kind=='id' and t in ['19','29']:
   body.append('<tr><td>'+cells[0]+'</td><td colspan="5">'+cell(ls,off+110,off+540,y-.2,ymax)+'</td></tr>')
  else:body.append('<tr>'+''.join('<td>'+v+'</td>' for v in cells)+'</tr>')
 return '<div style="overflow-x:auto">\n<table>\n<thead><tr><th rowspan="2">Номер индикатора'+('<sup>1</sup>' if n==132 and side==0 else '')+'</th><th rowspan="2">Наименование индикатора</th><th colspan="3">Значение индикатора</th><th rowspan="2">Факторный анализ изменений</th></tr><tr><th>2023</th><th>2024</th><th>Изменение (абсолютное/относительное)</th></tr></thead>\n<tbody>\n'+'\n'.join(body)+'\n</tbody></table>\n</div>'

heading={9:'всегда в движении',18:'научный подход к производству',32:'передовые ит-решения',39:'инновации на службе надежности',45:'долгосрочное партнерство',47:'системная работа с персоналом',55:'на пути к здоровью работников',67:'безопасность — фундамент управленческих решений',73:'отвага, решительность, профессионализм',76:'уверенность в завтрашнем дне',90:'комплексная поддержка регионов присутствия',96:'помощь добрыми делами',104:'экономичность = экологичность',125:'управление энергетической эффективностью'}
# Source uses juxtaposition, no printed dash on this heading.
heading[67]='безопасность\nфундамент управленческих решений'
changes=[]
for n in range(1,151):
 f=P/f'{n:04}.md';t=fix(f.read_text());r=registry['pages'][n-1];orig=t
 # Repair soft word-wrap hyphens using only the source text, never a dictionary.
 raw=D[n-1].get_text()
 count=0
 for m in re.finditer(r'(\w+)\u00ad\s*\n\s*(\w+)',raw):
  a,b=m.groups();pat=re.escape(a)+r'\s*'+re.escape(b)
  t,k=re.subn(pat,a+b,t);count+=k
 # Original hard end-of-line hyphens are retained unless separately checked.
 for m in re.finditer(r'(\w+)-[ \t]*\n[ \t]*(\w+)',raw):
  a,b=m.groups()
  if len(a)>1 and len(b)>1:t=re.sub(re.escape(a)+re.escape(b),a+'-\n'+b,t)
 if n==1:
  start=t.index('<details>');t=t[:t.index('\n\n',t.index('</a>'))]+'\n\nОТЧЕТ О СОЦИАЛЬНОЙ ДЕЯТЕЛЬНОСТИ ГРУППЫ ГАЗПРОМ\n\n# ценен вклад каждого\n\n2024\n\nГазпром\n\n'+t[start:]
  r['reviewed_objects']=['Обложка: название, слоган, год, логотип; сверено по изображению.']
 if n in heading:
  # All these interview spreads begin with one heading, followed by an empty line and body.
  start=t.index('</a>')+4;end=t.index('\n\n',t.index('\n\n',start)+2)
  # Skip all adjacent heading paragraphs before body (e.g. two parts on the energy page).
  body=t[start:].lstrip();m=re.match(r'(?:#{1,6} [^\n]+\n(?:\n|(?=#{1,6} ))*)+',body)
  if m:body=body[m.end():].lstrip()
  t=t[:start]+'\n\n# '+heading[n]+'\n\n'+body
  r.setdefault('reviewed_objects',[]).append('Полный декоративный заголовок восстановлен визуальным чтением; весь текст страницы не сверен.')
 if n==2:
  t=t.replace('\n\nВ Отчете термины','\n\n# ценен вклад каждого\n\nВ Отчете термины',1)
  r.setdefault('reviewed_objects',[]).append('Слоган на левой печатной странице прочитан по изображению.')
 # Keep difficult numeric layouts spatially aligned. This avoids falsely associating values with a different row.
 numeric=len(re.findall(r'\b\d+[.,]?\d*\b',raw))
 positional=(any(0xe000<=ord(c)<=0xf8ff for c in raw) or 129<=n<=143 or numeric>100)
 if positional and not 144<=n<=147:
  tail=t[t.find('<details><summary>Ссылки из аннотаций'): ] if '<details><summary>Ссылки из аннотаций' in t else t[t.index('<details><summary>Оригинал'):]
  head=t[:t.index('</a>')+4]
  contents=[]
  for side in range(2 if D[n-1].rect.width>800 else 1):
   if n in [132,133] or (n==134 and side==0):
    end={(132,0):690,(132,1):720,(133,0):730,(133,1):740,(134,0):320}[(n,side)]
    v=''
    if n==132 and side==0:
     v='# 7.3. Индикаторы оценки достижений Группы Газпром в области устойчивого развития\n\n'
     v+='Индикаторы оценки достижений в области содействия социально-экономическому развитию регионов Российской Федерации\n\n'
    v+=indicators(n,side,end)
    # Notes follow the table. Preserve their actual position and numbering.
    lines=layout(n,side).splitlines(); first=next((j for j,l in enumerate(lines) if re.match(r'^\s*[1-7]\s{2,}\S',l) and j>len(lines)*.65),None)
    if first is not None:v+='\n\n```text\n'+'\n'.join(lines[first:]).strip()+'\n```'
    contents.append(v)
   else:contents.append(layout_md(n,side))
  t=head+'\n\n> **Техническое примечание:** сложная табличная или графическая верстка. В моноширинных блоках сохранено взаимное положение текста и значений; в HTML-таблицах восстановлены колонки. Полная сверка строк, ячеек, сносок и рядов диаграмм ещё не завершена. Цветовые связи диаграмм следует читать по сохранённому оригиналу этой страницы.\n\n'+'\n\n'.join(contents)+'\n\n'+tail
  r['content_type']=list(dict.fromkeys(r['content_type']+['tables_or_charts']))
  r['method']+='; pdftotext -layout by logical half; PUA digit mapping'
  r['issues'].append('Таблицы/диаграммы: требуется полная проверка связей строк, периодов, единиц, легенд и сносок; геометрическая текстовая раскладка сохранена.')
  r.pop('unmatched_native_blocks',None)
  r['issues']=[z for z in r['issues'] if not z.startswith('Фрагменты текстового')]
 if t!=orig:changes.append({'pdf_page':n,'soft_hyphen_joins':count,'numeric_layout':positional,'digit_fix':any(c in raw for c in map(chr,DIGITS))})
 f.write_text(t)
(A/'pages.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2))
(A/'corrections.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
