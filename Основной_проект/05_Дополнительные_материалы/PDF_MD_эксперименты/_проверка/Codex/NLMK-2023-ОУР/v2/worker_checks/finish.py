import sys,re,json,html,hashlib,collections
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
from bs4 import BeautifulSoup
import pymupdf
root=Path(__file__).resolve().parents[1];p=root/'_проверка'
src=json.loads((root.parent/'source.json').read_text());pdf=pymupdf.open(src['source_pdf'])
s=(root/'report.md').read_text();parts=re.split(r'<!-- pdf_page: (\d+) -->',s)
log=json.loads((p/'corrections.json').read_text());reg=json.loads((p/'pages.json').read_text())
def get(n):return parts[parts.index(str(n))+1]
def put(n,t):parts[parts.index(str(n))+1]=t
# Retain the source's thousands separators in the two reconstructed cells.
t=get(13).replace('>31515<','>31\u00a0515<').replace('>30114<','>30\u00a0114<');put(13,t)
t=get(1).replace('<h2>Отчет','<p>НЛМК</p>\n\n<h2>Отчет');put(1,t)
# Repair the confirmed interleaving of two independent text columns.
t=get(70)
a=t.index('<p>գ общее собрание');b=t.index('<p>Структура корпоративного управления\u00a0НЛМК</p>',a)
text=[
'общее собрание акционеров – высший орган управления НЛМК, принимающий решения по основным вопросам деятельности Компании;',
'Совет директоров – орган, который осуществляет общее руководство деятельностью Компании, за исключением вопросов, отнесенных Уставом НЛМК к компетенции общего собрания акционеров;',
'комитеты Совета директоров – консультативные органы, сформированные для предварительного рассмотрения наиболее важных вопросов деятельности Компании;',
'Президент (Председатель Правления), Правление – исполнительные органы, которые осуществляют оперативное управление деятельностью и обеспечивают эффективную работу, выполняя поставленные Советом директоров задачи;',
'Корпоративный секретарь, обеспечивающий взаимодействие с акционерами, координацию действий Компании по защите прав и интересов акционеров, а также поддержку работы Совета директоров;',
'внутренний аудит, который контролирует финансово-хозяйственную деятельность Компании.']
t=t[:a]+'<ul>\n'+''.join('<li>'+x+'</li>\n' for x in text)+'</ul>\n\n'+t[b:]
m=re.search(r'<p>1  Устойчивое.*?бизнеса\.</p>',t,re.S)
if m:
 txt=m[0][3:-4];items=re.split(r'\s+[2-8] (?=[А-Я])',txt);items[0]=items[0].removeprefix('1  ')
 assert len(items)==8
 t=t[:m.start()]+'<ol>'+''.join('<li>'+x+'</li>' for x in items)+'</ol>'+t[m.end():]
put(70,t)
log.append({'page':70,'object':'Структура корпоративного управления и 8 принципов','change':'Разведены переплетённые строки двух колонок; восстановлены шесть пунктов структуры и нумерованный список принципов.','basis':'Исходные увеличенные изображения crop_70.png и detail_70.png.','review_status':'checked'})
# Repair a chart legend erroneously detected as a table crossing into the chart.
t=get(14);m=re.search('<table>.*?</table>',t,re.S);rows=BeautifulSoup(m[0],'html.parser').find_all('tr');new=[]
for r in rows[3:]:
 cells=r.find_all('td');new.append((cells[0].decode_contents(),cells[-1].decode_contents()))
table='<table><tr><th>Источник</th><th>Доля, %</th></tr>'+''.join('<tr><td>'+a+'</td><td>'+b+'</td></tr>' for a,b in new)+'</table>'
t=t[:m.start()]+table+t[m.end():];put(14,t)
log.append({'page':14,'object':'Легенда структуры прямой эмиссии','change':'Выделена легенда в два столбца; повторные подписи малых секторов сохранены в исходном изображении, устранён ложный столбец.','basis':'Просмотр исходного изображения и исходных ячеек; вся страница не сверена.','review_status':'pending'})
# The auditor appendix has three real columns; the first was split into empty margins.
t=get(96);m=re.search('<table>.*?</table>',t,re.S);rows=BeautifulSoup(m[0],'html.parser').find_all('tr');header=['Номер раскрытия показателя GRI','Наименование раскрытия показателя GRI','Выбранная информация за год, закончившийся 31 декабря 2023*']
new=['<tr>'+''.join('<th>'+x+'</th>' for x in header)+'</tr>']
for r in rows[4:]:
 cells=r.find_all('td');assert len(cells)==3
 new.append('<tr>'+''.join('<td>'+c.decode_contents()+'</td>' for c in cells)+'</tr>')
t=t[:m.start()]+'<table>'+''.join(new)+'</table>'+t[m.end():];put(96,t)
log.append({'page':96,'object':'Приложение аудитора, шапка таблицы','change':'Восстановлены три реальных столбца; устранены ложные строки шапки и пустые поля первого столбца.','basis':'Увеличенное исходное изображение detail_96.png. Данные тела оставлены из механического кандидата.','review_status':'pending'})
# Move native year headers directly into their tables, using only the printed sequence.
headerlog=[]
for n in range(1,97):
 t=get(n)
 pattern=r'<p>([^<>]*?) ((?:20\d\d ?){2,})</p>\s*((?:<p>[^<]*</p>\s*)?)<table>'
 def attach(m):
  label=m[1];years=m[2].split();heads=[html.escape(label)]+years
  headerlog.append({'page':n,'header':heads})
  section=m[3]
  return '<table>\n<tr>'+''.join('<th>'+x+'</th>' for x in heads)+'</tr>\n'+(('<tr><td colspan="'+str(len(heads))+'">'+re.sub('</?p>','',section).strip()+'</td></tr>\n') if section else '')
 t=re.sub(pattern,attach,t)
 # Known source headers with words rather than years.
 labels={
 'Стандарт GRI Показатель GRI Стр. Комментарий':['Стандарт GRI','Показатель GRI','Стр.','Комментарий'],
 'Страна Доля ВИЭ-электроэнергии<sup>2</sup> Источник Предприятия':['Страна','Доля ВИЭ-электроэнергии<sup>2</sup>','Источник','Предприятия']}
 for label,heads in labels.items():
  pat=r'<p>'+re.escape(label)+r'</p>\s*((?:<p>[^<]*</p>\s*){0,2})<table>'
  def attach_words(m):
   headerlog.append({'page':n,'header':heads});return m[1]+'<table>\n<tr>'+''.join('<th>'+x+'</th>' for x in heads)+'</tr>'
  t=re.sub(pat,attach_words,t)
 put(n,t)
log.append({'pages':sorted(set(x['page'] for x in headerlog)),'change':'Исходные шапки с последовательностями лет и шапки GRI/ВИЭ включены внутрь соответствующих HTML-таблиц без изменения чисел.','basis':'Соседство в механическом кандидате и число полей; семантическая сверка всех таблиц не заявляется.'})
(p/'table_headers.json').write_text(json.dumps(headerlog,ensure_ascii=False,indent=2))
for rec in reg['pages']:
 n=rec['pdf_page'];page=pdf[n-1];w,h=page.rect.width,page.rect.height
 rec['printed_labels']=[x[4].strip() for x in page.get_text('blocks') if x[1]>h*.94 and re.fullmatch(r'\d{1,3}',x[4].strip())]
 rec['content_type']='native_text_with_graphics'+('_tables' if rec['tables'] else '')
 rec['source_text_chars']=len(page.get_text())
 rec['source_image']='../assets/page_'+f'{n:04d}'+'.png'
 rec['native_coverage_scope']='Учёт исходного механического кандидата; после правок не является утверждением посимвольного совпадения итоговой разметки.'
 rec['table_layout_overviewed']=bool(rec['tables'])
 if n in [14,96]:rec['reviewed_objects']=[x for x in log if x.get('page')==n]
 if n==70:rec['reviewed_objects']=[x for x in log if x.get('page')==n]
 if rec['review_status']=='pending':
  note='> Служебная пометка: полная сверка страницы по оригиналу не завершена. Порядок чтения и связи значений диаграмм, подписей и примечаний требуют проверки; исходное изображение сохранено ниже.'
  t=get(n);t=t.replace('<details>','\n'+note+'\n\n<details>',1);put(n,t)
(p/'pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n')
(p/'corrections.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n')
(root/'report.md').write_text(''.join(parts[j] if j%2==0 else '<!-- pdf_page: '+parts[j]+' -->' for j in range(len(parts))))
print('Saved final structure; attached headers:',len(headerlog))
