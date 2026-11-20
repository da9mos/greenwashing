from pathlib import Path
import sys,json,re,importlib.util,cv2,numpy as np
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
sp=importlib.util.spec_from_file_location('nc',str(BASE/'_проверка/native_candidate_baseline.py')); nc=importlib.util.module_from_spec(sp);sp.loader.exec_module(nc)
D=nc.fitz.open(json.load(open(BASE.parent/'source.json'))['source_pdf'])
initial=(BASE/'_проверка/initial/report.md').read_text()
parts={int(m[1]):m[2] for m in re.finditer(r'<!-- pdf_page: (\d+) -->(.*?)(?=<!-- pdf_page:|\Z)',initial,re.S)}
changes=[]
def lines_for(n):
 p=D[n-1]; im=cv2.imread(str(BASE/f'assets/page_{n:04}.png')); h,w=im.shape[:2]; gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
 mask=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_MEAN_C,cv2.THRESH_BINARY_INV,15,2)
 lines=[]
 for axis,ker in [('h',(45,1)),('v',(1,15))]:
  a=cv2.morphologyEx(mask,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,ker))
  contours,_=cv2.findContours(a,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
  for c in contours:
   x,y,cw,ch=cv2.boundingRect(c)
   if y<80:continue
   if axis=='h' and cw>45:a=(x,y+ch/2);z=(x+cw,y+ch/2)
   elif axis=='v' and ch>15:a=(x+cw/2,y);z=(x+cw/2,y+ch)
   else:continue
   lines.append(((a[0]/w*p.rect.width,a[1]/h*p.rect.height),(z[0]/w*p.rect.width,z[1]/h*p.rect.height)))
 return lines
from types import SimpleNamespace

def manual_table(xs,ys,merges=(),scale=1):
 xs=[v*scale for v in xs];ys=[v*scale for v in ys]
 cells=[[None for _ in xs[:-1]] for _ in ys[:-1]]
 covered=set()
 for r0,r1,c0,c1 in merges:
  rect=(xs[c0],ys[r0],xs[c1],ys[r1]);cells[r0][c0]=rect
  covered.update((r,c) for r in range(r0,r1) for c in range(c0,c1))
 for r in range(len(ys)-1):
  for c in range(len(xs)-1):
   if (r,c) not in covered:cells[r][c]=(xs[c],ys[r],xs[c+1],ys[r+1])
 return SimpleNamespace(bbox=(xs[0],ys[0],xs[-1],ys[-1]),rows=[SimpleNamespace(cells=r) for r in cells])

def fixed_tables(n):
 if n==16:
  return [manual_table([73,390,946,1502,1975],[179,228,441,681,854,995],[(1,5,2,3)],D[n-1].rect.width/2048)]
 if n==128:
  scale=D[n-1].rect.width/2048
  ys=[121.7,141,160.8,287.2,306.9,384.8,428.6,472.5,516.3,560.6,604,648.3,701.6,740.7,779.8,818.5,838.3,857.6,920.8,959.9,979.3,1018.8]
  merges=[(r,r+1,0,6) for r in [0,3,15]]+[(2,3,4,6),(17,18,4,6)]+[(19,21,c,c+1) for c in range(4)]+[(20,21,4,6)]
  # Last row has an internal split in the disclosure field, handled as a multiline cell.
  left=manual_table([73,148,392,524,656,909,972],ys,merges,scale)
  # Right side: table with sectorial topics uses three columns, separate from GRI index.
  ys2=[121.7,141,160.8,224,263.1,282.4,311.7,355.5,374.9,404.1,457.8,477.2,530.9,560.6]
  merges2=[(r,r+1,0,6) for r in [0,4,7,10]]+[(3,4,4,6),(6,7,4,6),(9,10,4,6),(12,13,4,6)]
  right=manual_table([1073,1149,1392,1522,1656,1909,1973],ys2,merges2,scale)
  ys3=[560.6,579.5,609.2,653,682.2,701.6,721.4,750.6,769.9,799.2,838.3,867.5,896.8,916.1,935.4,964.7,993.9]
  merges3=[(0,1,0,3),(7,8,0,3),(4,6,2,3),(12,14,2,3)]
  bottom=manual_table([1073,1149,1524,1973],ys3,merges3,scale)
  return [left,right,bottom]
 return None

class Proxy:
 def __init__(self,page,lines,n):self.page,self.lines,self.n=page,lines,n
 def __getattr__(self,k):return getattr(self.page,k)
 def find_tables(self,**kwargs):return SimpleNamespace(tables=fixed_tables(self.n)) if fixed_tables(self.n) else self.page.find_tables(add_lines=self.lines,**kwargs)
# Source-image grid supplements the existing converter; glyph renderer and inventory checks unchanged.
refined={}
for n in [15,16,31,71,98,99,113,121,127,128,129,130]:
 p=D[n-1];lines=lines_for(n)
 # Borderless body tables: source horizontal rules and visually established column boundaries.
 custom={15:([42.52,226.77,549.92,873.07,1148.03],103.29,513.34),16:([42.52,226.77,549.92,873.07,1148.03],103.9,578.5),31:([42.52,153.1,392.2],222,612),71:([43.7,250.8,647.5],127,571),98:([42.52,185.2,356.5,1148.03],91.6,629.8),99:([42.52,185.2,390.0,1148.03],91.6,636.0),113:([42.52,205.0,603.5,725.0,773.5],97,615.5)}
 if n in custom:
  xs,y0,y1=custom[n];lines += [((x,y0),(x,y1)) for x in xs]
 body,info=nc.convert_page(Proxy(p,lines,n))
 refined[n]=info
 old=parts[n]
 tail=old[old.index('> Служебная информация: ссылки исходного PDF'):] if '> Служебная информация: ссылки исходного PDF' in old else old[old.index('<details>'):]
 parts[n]=f'\n<a id="pdf-page-{n}"></a>\n\n'+body+'\n\n'+tail
 changes.append({'page':n,'action':'Refined table geometry using source image ruling and established boundaries; reused native_candidate glyph assignment and inventory checks','tables':info['tables']})
# Every OCR supplement is saved in initial. It contains duplicate native text / artifacts; real raster body is transcribed separately below.
for n,t in parts.items():
 parts[n]=re.sub(r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\.\n\n.*?(?=> Служебная информация: ссылки исходного PDF|<details>)','',t,flags=re.S)
# Source-faithful title on cover.
parts[1]=re.sub(r'<p>Отчёт</p>\s*<p>об устойчивом</p>\s*<p>развитии</p>\s*<p>2024</p>','# Отчёт об устойчивом развитии 2024',parts[1])
def add(n,s):
 t=parts[n]; k=t.find('> Служебная информация: ссылки исходного PDF');k=k if k>=0 else t.index('<details>');parts[n]=t[:k]+s+'\n\n'+t[k:]
add(6,'''### География бизнеса — подписи карты

| Направление (по условным обозначениям карты) | Предприятия / обозначения |
| --- | --- |
| Металлургия | Вяртсильский метизный завод; «Ижсталь»; Белорецкий металлургический комбинат; Челябинский металлургический комбинат; «Уральская кузница»; Гурьевский филиал ПАО «ЧМК» |
| Горная добыча | «Москокс»; «Мечел-Кокс»; «Южный Кузбасс»; Якутская рудная компания; «Якутуголь»; Коршуновский ГОК; Братский завод ферросплавов |
| Энергетика | «Кузбассэнергосбыт»; Южно-Кузбасская ГРЭС |
| Порты | «Порт Мечел-Темрюк»; «Торговый порт Посьет» |
| Головной офис сбытовой сети | «Мечел-Сервис Бел»; «Мечел-Сервис» |

> Служебная пометка: названия и условные обозначения прочитаны по карте; географическое расположение сохранено в изображении страницы.''')
add(39,'''Легенда карты: лесные пожары; наводнения; грозы; осадки; экстремальное изменение среднегодовых температур (аномальная жара или аномальный холод); таяние многолетнемерзлых пород (ММП); сильные ветра; гололед.''')
# Retain original legend native text; add missing associations encoded only by pictograms.
add(39,'''### Карта климатических рисков — связи городов и условных обозначений

| Город | Факторы, приводящие к наступлению физических рисков, выявленные в 2014–2024 годах |
| --- | --- |
| Санкт-Петербург | Экстремальное изменение среднегодовых температур; осадки; грозы |
| Москва | Гололед; лесные пожары; экстремальное изменение среднегодовых температур; осадки; грозы |
| Ижевск | Наводнения; экстремальное изменение среднегодовых температур; осадки |
| Темрюк | Сильные ветра; осадки |
| Белорецк | Наводнения; сильные ветра; грозы; осадки |
| Якутск | Лесные пожары; экстремальное изменение среднегодовых температур; таяние многолетнемерзлых пород (ММП) |
| Междуреченск | Сильные ветра; экстремальное изменение среднегодовых температур; осадки |
| Посьет | Сильные ветра |

> Служебная пометка: связи прочитаны по пиктограммам исходной карты; полная формулировка температурного фактора — в легенде оригинала.''')
add(86,'''Цели устойчивого развития, обозначенные на странице:

- 8. Достойная работа и экономический рост.
- 9. Индустриализация, инновации и инфраструктура.
- 12. Ответственное потребление и производство.''')
# Logo labels that raster OCR failed to transfer.
add(17,'''Логотипы организаций в блоке рейтингов (сверху вниз): Российский союз промышленников и предпринимателей (РСПП); НКР; ДаСтратегия.''')
# Transcription of visible body on the raster cards, read from an enlarged source crop.
add(46,'''### Карточки «Производственная система» на фотографии

**ПАО «Уралкуз». Проблема:** Настройка станка на каждый резец производится индивидуально. Для фрезерования углов в плане и задних углов затрачивается много времени.

> Служебная пометка: остальная часть этой карточки перекрыта двумя передними карточками в самом PDF.

**АО ХК «Якутуголь». Автор идеи: Сергей СИДОРЕНКО.**

**Проблема:** В процессе эксплуатации ленточных фильтр-прессов возникали различные сбои оборудования. Некоторые причины остановки не удавалось определить оперативно, что приводило к многочасовому простою фильтр-прессов.

**Решение:** Сергей Сидоренко предложил внести в схему управления реле времени для контроля рабочего давления в процессе работы и устранения потери от ложных срабатываний, а также вывести на лицевую панель шкафа управления световую сигнализацию, непосредственно указывающую аварию.

**Мнение:** «Поданное предложение существенно снизило простои фильтр-прессов отделения флотации и фильтрации, что повлияло на снижение содержания твердого продукта в водно-шламовой схеме фабрики».

**Результат:** Повышение оперативности диагностики отказов.

**ПАО «Ижсталь». Автор идеи: Николай ДЕКТЕРЕВ.**

**Проблема:** Ревизия и настройка вентиляторов производится в местах их установки, что затрудняет процесс обслуживания и наладки.

**Решение:** Николай Дектерев предложил изготовить специализированный стенд, имитирующий основание вентилятора.

**Мнение:** «Сейчас сотрудники ЦРТОП имеют возможность безопасно и эффективно менять подшипники и балансировать вентиляторы в специализированном месте».

**Результат:** Стенд для балансировки упрощает и ускоряет ремонт вентиляторов, сокращает трудозатраты.

> Служебная пометка: мелкие подписи должностей и фамилий под двумя цитатами требуют дополнительной сверки; они сохранены в увеличенном фрагменте. Текст карточек прочитан визуально; страница остаётся pending до сверки этих подписей.

![Увеличенный исходный фрагмент карточек](assets/cards46.png)''')
# Begin report with source title; work-version annotation after title.
parts[1]=parts[1].replace('# Отчёт об устойчивом развитии 2024','# Отчёт об устойчивом развитии 2024\n\n> Служебная информация: рабочая версия полной конвертации. Статусы сверки и ограничения приведены в `_проверка/pages.json`; выборочный просмотр не является полной сверкой PDF.')
# Long body lines incorrectly flagged as superscript are ordinary text in inspected source pages.
for n in [15,16,25,31,37,42,46,47,60,67,69,71,78,85,86,87,97,98,99,101,110,113,115,118,121,127,128,129,130,131,132,133]:
 parts[n]=re.sub(r'<sup>([^<>]{4,})</sup>',lambda m:m[1] if re.search(r'[А-Яа-яA-Za-z]',m[1]) else m[0],parts[n])
report=''.join(f'<!-- pdf_page: {n} -->'+parts[n] for n in range(1,134))
# Put the title first, while preserving the physical page marker inside its page.
report=report.replace('<!-- pdf_page: 1 -->\n<a id="pdf-page-1"></a>\n\n# Отчёт об устойчивом развитии 2024','# Отчёт об устойчивом развитии 2024\n\n<!-- pdf_page: 1 -->\n<a id="pdf-page-1"></a>',1)
(BASE/'report.md').write_text(report)
(BASE/'_проверка/refined_geometry.json').write_text(json.dumps(refined,ensure_ascii=False,indent=2))
(BASE/'_проверка/changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
print('saved',len(report), 'tables',[(n,x['tables']) for n,x in refined.items()])
