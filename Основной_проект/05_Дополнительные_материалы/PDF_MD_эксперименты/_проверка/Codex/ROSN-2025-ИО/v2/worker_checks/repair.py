import sys,json,re,pathlib,html,collections,hashlib
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf as fitz
from bs4 import BeautifulSoup
R=pathlib.Path('result'); Q=R/'_проверка'; s=(Q/'baseline/report.md').read_text(); seg=re.split(r'<!-- pdf_page: (\d+) -->',s); pages={int(seg[i]):seg[i+1] for i in range(1,len(seg),2)}
reg=json.load(open(Q/'baseline/pages.json')); D=fitz.open(json.load(open('source.json'))['source_pdf']); log=[]
def units(n):
 out=[]
 for bi,b in enumerate(D[n-1].get_text('rawdict')['blocks']):
  for li,l in enumerate(b.get('lines',[])):
   for sp in l['spans']:
    for c in sp['chars']:
     out.append(dict(text=c['c'],bbox=c['bbox'],line=(bi,li),seq=len(out),flags=sp['flags']))
 return out
def center(u):
 b=u['bbox'];return ((b[0]+b[2])/2,(b[1]+b[3])/2)
def render(us):
 lines=collections.defaultdict(list)
 for u in us:lines[u['line']].append(u)
 out=[]
 for line in sorted(lines.values(),key=lambda a:(round(min(u['bbox'][1] for u in a),1),min(u['seq'] for u in a))):
  pieces=[]; state=(False,False)
  for u in sorted(line,key=lambda a:a['seq']):
   st=(bool(u['flags']&16),bool(u['flags']&1))
   if st!=state:
    if state[1]:pieces.append('</sup>')
    if state[0]:pieces.append('</strong>')
    if st[0]:pieces.append('<strong>')
    if st[1]:pieces.append('<sup>')
    state=st
   pieces.append(html.escape(u['text']))
  if state[1]:pieces.append('</sup>')
  if state[0]:pieces.append('</strong>')
  out.append(''.join(pieces).strip())
 return '<br/>'.join(out)
def inventory(t):return collections.Counter(c for c in BeautifulSoup(t,'html.parser').get_text() if not c.isspace())
def repair_table(n,xs,ys):
 text=pages[n]; records=reg['pages'][n-1]['objects']; matches=list(re.finditer(r'<p>.*?</p>|<table>.*?</table>',text,re.S)); assert len(matches)==len(records),(n,len(matches),len(records))
 oldbox=next(o['bbox'] for o in records if o['kind']=='table')
 def region(x,y):
  return xs[0]-.5<=x<=xs[-1]+.5 and ys[0]<=y<=ys[-1]
 selected=[i for i,o in enumerate(records) if o['kind']=='table' or region((o['bbox'][0]+o['bbox'][2])/2,(o['bbox'][1]+o['bbox'][3])/2)]
 # The old page-49 detector swallowed neighbouring prose; restore that prose too.
 def swallowed(x,y):return n==49 and oldbox[0]-.1<=x<=oldbox[2]+.1 and oldbox[1]-.1<=y<=oldbox[3]+.1
 us=[u for u in units(n) if region(*center(u)) or swallowed(*center(u))]
 rows=[]; used=[]
 for ri,(a,b) in enumerate(zip(ys,ys[1:])):
  row=[u for u in us if region(*center(u)) and a<=center(u)[1]<b];used+=row
  section=ri>0 and n>=54 and not any(center(u)[0]>=xs[3] for u in row)
  if section: rows.append('<tr><td colspan="5">'+render(row)+'</td></tr>');continue
  cells=[]
  for l,r in zip(xs,xs[1:]):
   v=[u for u in row if l<=center(u)[0]<r];cells.append('<td>'+render(v)+'</td>')
  rows.append('<tr>'+''.join(cells)+'</tr>')
 table='<table>\n'+'\n'.join(rows)+'\n</table>'
 extra=[u for u in us if not region(*center(u))]
 if extra: table='<p>'+render(extra)+'</p>\n\n'+table
 old=''.join(matches[i].group() for i in selected)
 assert inventory(old)==inventory(table),(n,dict(inventory(old)-inventory(table)),dict(inventory(table)-inventory(old)))
 for i in reversed(selected):text=text[:matches[i].start()]+(table if i==selected[0] else '')+text[matches[i].end():]
 pages[n]=text
 log.append(dict(pdf_page=n,object='table',change='Repaired source-defined row and column geometry; preserved native character inventory; preserved source bold selection and superscripts.',rows=len(rows),columns=len(xs)-1))
for n in range(54,67):
 ys=sorted({round(d['rect'][1],3) for d in D[n-1].get_drawings() if abs(d['rect'][0]-80.79)<.1 and abs(d['rect'][2]-257.29)<.1 and d['rect'].height<.1})
 repair_table(n,[56,80.79,257.29,643.46,754.02,1137],[ys[0]-36]+ys)
repair_table(49,[979.8,1056.85,1134.5],[560,592.885,617.703,642.271,676.438,710.606,735.175])
# Page 53 has an entirely fictitious middle column; source shows only label and total.
t=pages[53]; soup=BeautifulSoup(t,'html.parser'); table=soup.find('table'); rows=table.find_all('tr')
for row in rows:
 cells=row.find_all('td',recursive=False);assert len(cells)==3 and not cells[1].get_text(strip=True);cells[1].decompose()
new=str(table);old=re.search(r'<table>.*?</table>',t,re.S).group();assert inventory(old)==inventory(new);pages[53]=t.replace(old,new);log.append(dict(pdf_page=53,change='Removed detector-only empty middle column after source-image inspection.'))
# Remove OCR only on visually inspected pages: all OCR additions are duplicate or decoration.
for n in [2,3,10,12,39]:
 pages[n]=re.sub(r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\..*?(?=> Служебная информация:|<details>)','',pages[n],flags=re.S)
 log.append(dict(pdf_page=n,change='Rejected OCR additions after image inspection: duplicates and decorative graphic noise.'))
# Reorder the financial columns on page 10 using the existing candidate object coordinates.
n=10;text=pages[n]; rec=reg['pages'][n-1]['objects']; ms=list(re.finditer(r'<p>.*?</p>|<table>.*?</table>',text,re.S));assert len(ms)==len(rec)
inds=[i for i,o in enumerate(rec) if o['bbox'][0]>640 and 105<o['bbox'][1]<280]
ordered=sorted(inds,key=lambda i:(0 if rec[i]['bbox'][0]<805 else 1 if rec[i]['bbox'][0]<975 else 2,rec[i]['bbox'][1]))
replacements={i:ms[j].group() for i,j in zip(inds,ordered)}
for i in reversed(inds):text=text[:ms[i].start()]+replacements[i]+text[ms[i].end():]
assert inventory(text)==inventory(pages[n]);pages[n]=text;log.append(dict(pdf_page=10,change='Restored three financial-text columns left to right, with capital-expenditure paragraph continuing in third column.'))
# Cover brand is outlined artwork, absent from the text layer.
pages[1]=pages[1].replace('<p>ЭФФЕКТИВНОСТЬ</p>','<p>РОСНЕФТЬ</p>\n\n<p>ЭФФЕКТИВНОСТЬ</p>')
# Table of contents transcribed from image: damaged leaders are graphical dot leaders, not missing prose.
entries=[('О Компании','2'),('Обращение Главного исполнительного директора, Председателя Правления ПАО «НК «Роснефть» И. И. Сечина','4'),('Основные производственные активы','6'),('Стратегия «Роснефть–2030»','8'),('Структура системы показателей эффективности','10'),('Инвестиционная программа','13'),('Операционные и финансовые показатели','15'),('Развитие розничной сети АЗС','18'),('Устойчивое развитие','20'),('Промышленная безопасность, охрана труда и окружающей среды','22'),('Углеродный менеджмент','32'),('Социальная политика','33'),('Развитие кадрового потенциала Компании и молодежная политика','37'),('Развитие генетики','42'),('Развитие автотуризма в регионах присутствия','44'),('Спонсорская и благотворительная деятельность','46'),('Поддержка спорта','48'),('Волонтерская деятельность','51'),('Корпоративное управление','52'),('Система корпоративного управления','54'),('Общее собрание акционеров','58'),('Совет директоров','60'),('Антикоррупционная политика Компании и мероприятия, направленные на противодействие коррупции и предупреждение конфликтов интересов','62'),('Ревизионная комиссия','65'),('Система управления рисками и внутреннего контроля','66'),('Функция внутреннего аудита','76'),('Работа с акционерами, основные события 2025 года','78'),('Инструменты защиты прав на акции','80'),('Корпоративный секретарь','81'),('Дивидендная политика','82'),('Приложения','84')]
t=pages[2];start=t.index('<p>');end=t.index('> Служебная информация:') if '> Служебная информация:' in t else t.index('<details>')
body='<p>Годовой отчет 2025</p>\n\n<h2>СОДЕРЖАНИЕ</h2>\n\n<table>\n'+''.join('<tr><td>'+a+'</td><td>'+b+'</td></tr>\n' for a,b in entries)+'</table>\n\n'
pages[2]=t[:start]+body+t[end:];log.append(dict(pdf_page=2,change='Replaced corrupt dot leaders, restored 4-column contents as consecutive section entries with printed page numbers; removed duplicate OCR.'))
# Preserve verified annotation targets with readable, restored captions.
targets=[3,4,5,6,7,8,9,11,12,13,18,18,20,23,24,25,26,27,28,29,31,32,33,34,35,40,41,42,42,43,44]
t=pages[2]
links='<ul>'+''.join('<li><a href="#pdf-page-'+str(dest)+'">'+html.escape(label)+'</a></li>' for (label,_),dest in zip(entries,targets))+'</ul>'
a=t.index('<ul>');b=t.index('</ul>',a)+5;pages[2]=t[:a]+links+t[b:]
# The tiny footnote glyphs are separate PDF lines despite being visibly superscript.
t=pages[54]
t=t.replace('<strong>Статус соответствия </strong><br/><strong>1</strong>', '<strong>Статус<sup>1</sup> соответствия </strong>')
t=t.replace('<strong>Объяснения отклонения от критериев оценки  </strong><br/><strong>2</strong>', '<strong>Объяснения<sup>2</sup> отклонения от критериев оценки  </strong>')
assert inventory(t)==inventory(pages[54]);pages[54]=t
log.append(dict(pdf_page=54,change='Restored detached tiny header footnotes as superscripts after their source words, using visual image and glyph coordinates.'))
# Progress and honest scope: checked only pages whose full body was read against image.
checked={1,2,3,10,12,44}; visual={1,2,3,10,12,37,39,44,46,49,53,*range(54,67)}
for r in reg['pages']:
 n=r['pdf_page'];r['conversion_status']='converted';r['review_status']='checked' if n in checked else 'pending';r['diagnostics_reviewed']=True;r['source_image_inspected']=n in visual
 r['issues']=([] if n in checked else ['Полная построчная сверка всей страницы с оригиналом не завершена; порядок чтения и связи требуют проверки.'])
 if n in visual and n not in checked:r['issues'].append('Просмотр исходного изображения и структурная проверка отдельных объектов не равны полной сверке страницы.')
 if n>=54 and n<=66:r['issues'].append('Геометрия таблицы и выделение выбранных статусов восстановлены по PDF; полный текст каждой ячейки ещё не сверен визуально.')
 r['repairs']=[x for x in log if x['pdf_page']==n]
 if n in [2,3,10,12,39]:r['ocr_disposition']='rejected_duplicate_or_decorative_after_visual_inspection'
 if n==2:r['unresolved_unicode_after_review']=0
 # Source printed folios extracted independently from actual header text, never inferred from offset.
 folios=[]
 for u in D[n-1].get_text('dict')['blocks']:
  for l in u.get('lines',[]):
   txt=''.join(sp['text'] for sp in l['spans']).strip()
   if l['bbox'][1]<55 and re.fullmatch(r'\d{1,3}',txt):folios.append(txt)
 r['printed_designation']=sorted(set(folios),key=int)
 r['content_type']='text_and_graphics' if not r['tables'] else 'text_tables_and_graphics'
 if n not in checked:
  pages[n]=pages[n].replace('<a id="pdf-page-'+str(n)+'"></a>','<a id="pdf-page-'+str(n)+'"></a>\n\n> Служебная пометка: converted / pending — полная сверка страницы по оригиналу не завершена.')
header='# ЭФФЕКТИВНОСТЬ В ОСНОВЕ\n\n> Служебная информация: рабочая версия полного переноса 68 физических страниц. Текст и таблицы перенесены из PDF; полная визуальная сверка всего документа не завершена. Статусы по страницам — в `_проверка/pages.json`.\n\n'
report=header+'\n'.join('<!-- pdf_page: '+str(n)+' -->'+pages[n] for n in range(1,69));(R/'report.md').write_text(report)
(Q/'pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2));(Q/'corrections.json').write_text(json.dumps(log,ensure_ascii=False,indent=2));print('Saved',len(report),'characters;',len(log),'repairs; checked',sorted(checked))
