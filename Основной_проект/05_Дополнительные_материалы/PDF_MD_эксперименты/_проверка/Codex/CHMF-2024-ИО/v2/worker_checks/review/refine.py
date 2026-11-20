import sys,importlib.util,pathlib,json,re,html,hashlib,collections
sys.path.insert(0,'/private/tmp/sber-diff-libs')
import pymupdf
root=pathlib.Path('result'); checks=root/'_проверка'; review=checks/'review'
source=json.load(open('source.json'));pdf=pymupdf.open(source['source_pdf'])
spec=importlib.util.spec_from_file_location('native',pathlib.Path(source['source_pdf']).parent.parent/'tools/native_candidate.py');native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
s=(checks/'report.native.md').read_text(); sections={int(m.group(1)):m.group(0) for m in re.finditer(r'<!-- pdf_page: (\d+) -->.*?(?=<!-- pdf_page:|\Z)',s,re.S)}
log=[]
def note(n,action,basis):log.append({'pdf_page':n,'action':action,'basis':basis})
def units(n):
 out=[]
 for bi,b in enumerate(pdf[n-1].get_text('rawdict')['blocks']):
  for li,l in enumerate(b.get('lines',[])):
   for sp in l['spans']:
    for c in sp['chars']:out.append(dict(text=c['c'],bbox=c['bbox'],line=(bi,li),sequence=len(out),flags=sp['flags']))
 return out
def region(us,box):
 x0,y0,x1,y1=box
 selected=[u.copy() for u in us if x0<=(u['bbox'][0]+u['bbox'][2])/2<x1 and y0<=(u['bbox'][1]+u['bbox'][3])/2<y1]
 # This region is an explicitly identified single cell or single column, not a whole spread.
 grouped=collections.defaultdict(list)
 for u in selected:grouped[u['line']].append(u)
 ordered=sorted(grouped.values(),key=lambda line:(min(u['bbox'][1] for u in line),min(u['bbox'][0] for u in line)))
 selected=[]
 for line in ordered:
  for u in sorted(line,key=lambda u:u['bbox'][0]):u['sequence']=len(selected);selected.append(u)
 return native.render_glyphs(selected)
def norm(t):return t.replace('\uf0fc','✓').replace('\uf0b7','•').replace('\x07','')
def source_tail(n):return sections[n][sections[n].index('> Служебная информация: ссылки исходного PDF'):] if '> Служебная информация: ссылки исходного PDF' in sections[n] else sections[n][sections[n].index('<details>'):]
# Cover and divider text were read against source images.
sections[1]=re.sub(r'<p>Новая стратегия</p>.*?(?=<details>)','<p>Северсталь</p>\n\n# Новая стратегия для устойчивой металлургии будущего\n\n<p>2024</p>\n\n<p>Интегрированный отчет</p>\n\n',sections[1],flags=re.S)
note(1,'Добавлены логотип-название, 2024, подпись; заглавие собрано без изменения слов.','Полное исходное изображение page_0001.png')
coverpages=[4,7,13,16,35,43,53,83,122]
for n in coverpages:
 sections[n]=re.sub(r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\..*?(?=> Служебная информация:|<details>)','',sections[n],flags=re.S)
 note(n,'Удалены OCR-дубли и шум на фотографии; сохранён проверенный текстовый слой разделителя.','Контактные листы contact_0–1; заголовок и подпись видны целиком.')
# False OCR additions on otherwise native pages are not substitutes for body text.
for n in [29,56,82]:
 sections[n]=re.sub(r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\..*?(?=> Служебная информация:|<details>)','',sections[n],flags=re.S)
 note(n,'Удалён дополнительный OCR-шум, перекрывающий существующий текстовый слой; проверка всего текста страницы остаётся pending.','Контактные листы: текст тела присутствует в native-кандидате; содержательная страница, не скан.')
# Addressed reconstruction of the malformed table on physical page 9, using original glyphs.
u=units(9)
p9=['<!-- pdf_page: 9 -->','<a id="pdf-page-9"></a>', '<p>'+region(u,(0,0,595,98))+'</p>','<table>']
xs=[34,251,428,562];ys=[132,246,362,477,592,708]
p9.append('<tr>'+''.join('<th>'+region(u,(xs[c],99,xs[c+1],130))+'</th>' for c in range(3))+'</tr>')
financial=region(u,(428,132,562,708))
for r in range(5):
 p9.append('<tr>'+''.join('<td>'+region(u,(xs[c],ys[r],xs[c+1],ys[r+1]))+'</td>' for c in range(2))+('<td rowspan="5">'+financial+'</td>' if r==0 else '')+'</tr>')
p9.extend(['</table>','<p>'+region(u,(0,709,595,790))+'</p>','<h2>'+region(u,(595,0,1190,80))+'</h2>','<p>'+region(u,(595,80,1190,153))+'</p>'])
# Map retains the geographic positions; matching legend transcribed explicitly.
map_path=root/'assets/page_0009_map.png'; pdf[8].get_pixmap(matrix=pymupdf.Matrix(2,2),clip=pymupdf.Rect(629,155,1157,405)).save(map_path)
p9.append('![Карта активов и условные обозначения](assets/page_0009_map.png)')
p9.append('<table><tr><th>Дивизион</th><th>Обозначение</th><th>Актив</th></tr>')
for div,entries in [('«Северсталь Ресурс»',['«Олкон», Мурманская обл.','«Карельский окатыш», Карелия','Яковлевский ГОК, Белгородская обл.']),('«Северсталь Российская сталь»',['ЧерМК, Вологодская обл., Череповец','Ижорский ТЗ, Санкт-Петербург','«Северсталь-метиз», Череповец','«Северсталь-метиз», Орел','«Северсталь-метиз», Волгоград'])]:
 for i,t in enumerate(entries,1):p9.append(f'<tr><td>{div}</td><td>{i:02d}</td><td>{t}</td></tr>')
p9.extend(['</table>','<p>'+region(u,(595,405,1190,532))+'</p>','<table>'])
rx=[629,747,982,1157];ry=[555,624,693,761]
p9.append('<tr>'+''.join('<th>'+region(u,(rx[c],533,rx[c+1],555))+'</th>' for c in range(3))+'</tr>')
for r in range(3):p9.append('<tr>'+''.join('<td>'+region(u,(rx[c],ry[r],rx[c+1],ry[r+1]))+'</td>' for c in range(3))+'</tr>')
p9.extend(['</table>','<p>'+region(u,(595,762,1190,790))+'</p>',source_tail(9)])
sections[9]='\n\n'.join(p9)
note(9,'Восстановлены 5 строк × 2 поля, общая финансовая цель rowspan=5, легенда карты и 3 строки активов; удалена нижняя навигация.','Полное исходное изображение; текст и числа ячеек перенесены исходными глифами по заданным границам.')
# Contents: each printed page number terminates its entry; keep wrapped titles together.
u2=units(2); entries=[]
for x0,x1,nx in [(668,855,860),(943,1135,1128)]:
 nums=[]
 for word in pdf[1].get_text('words'):
  if word[0]>=nx and word[2]<x1+22 and 90<word[1]<750 and re.fullmatch(r'\d+',word[4]):nums.append(word)
 last=90
 for word in sorted(nums,key=lambda w:w[1]):
  cy=(word[1]+word[3])/2
  title=region(u2,(x0,last,x1,cy+3))
  entries.append((title,word[4]));last=cy+3
sections[2]='<!-- pdf_page: 2 -->\n<a id="pdf-page-2"></a>\n\n<h1>Содержание</h1>\n<table>\n'+'\n'.join('<tr><td>'+t+'</td><td>'+num+'</td></tr>' for t,num in entries)+'\n</table>\n\n'+source_tail(2)
note(2,'Строки содержания объединены с соответствующими печатными номерами; фиктивные пустые строки удалены.','Полное исходное изображение; исходные глифы выбирались по двум колонкам и базовым линиям печатных номеров. Назначения трёх неисправных PDF-ссылок не угадывались.')

# Scan/mixed annexes: OCR entire body, left side then right, no confidence filtering.
for n in range(141,147):
 prefix=sections[n].split('> Служебная пометка:')[0]
 if n==141:
  # Keep source table on the left, remove native duplicate raster heading; append right-side OCR.
  prefix=prefix.replace('<p>Приложение 6. Отчет независимого аудитора</p>','')
 else:
  # Native objects are navigation except the scanned-section title (143) and financial cover (146).
  if n==146:
   us=units(n);prefix='<!-- pdf_page: 146 -->\n<a id="pdf-page-146"></a>\n'
  else:prefix=f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n'
 sides=['right'] if n==141 else ['left'] if n==146 else ['left','right']
 texts=[]
 for side in sides:
  text=(review/f'ocr_{n}_{side}.txt').read_text()
  if n==141:
   text=text.replace('Т$АТР','TSATR').replace('MAH T','млн т').replace('млнт','млн т').replace('СО?','CO₂').replace('M3','м³')
   text=text.replace('символом «С»','символом «[графический знак заверения — см. исходное изображение]»')
  if n==143 and side=='left':text=text.replace('\nРЗ\n','\n[Графическая подпись — см. исходное изображение]\n')
  texts.append('<div class="ocr-body">\n'+html.escape(text).replace('\n','<br/>\n')+'\n</div>')
 if n==146:texts.append('<p>'+region(units(n),(595,0,1190,790))+'</p>')
 sections[n]=prefix+'\n\n> Служебная пометка: текст тела получен локальным OCR по отдельным сторонам разворота. Полная пословная сверка не завершена; возможны ошибки знаков, чисел и структуры.\n\n'+'\n\n'.join(texts)+'\n\n'+source_tail(n)
 note(n,'Текст тела заменён повторным OCR отдельных сторон разворота, без отсечения слов по confidence; исходный OCR сохранён в версии native.','Локальный Tesseract rus+eng, масштаб 3; источник изображений — исходный PDF. Статус текста pending.')
# Normalize only verified symbol-font encodings, preserving an audit trail.
for n,sec in sections.items():
 counts={repr(c):sec.count(c) for c in '\x07\uf0fc\uf0b7' if c in sec}
 if counts:note(n,'Нормализация знаков '+str(counts),'unicode_locations.json + unicode_0–3.jpg: U+F0FC Wingdings = ✓; U+F0B7 Symbol = •; U+0007 не имеет видимого знака. Выборочная сверка класса на каждой затронутой странице, не всех вхождений.')
 sections[n]=norm(sec)
header='# Новая стратегия для устойчивой металлургии будущего\n\n> Служебная информация: рабочая полная конвертация 167 физических страниц. Полная сверка текста и таблиц не завершена. Статусы по страницам — `_проверка/pages.json`; исходные изображения сохранены как визуальная опора.\n\n'
report=header+'\n\n'.join(sections[n].rstrip() for n in range(1,168))+'\n'
(root/'report.md').write_text(report)
(checks/'corrections.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n')
print('saved',len(report),'characters;',len(log),'log records')
