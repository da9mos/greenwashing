"""Addressed source-based edits to the existing native candidate; no conversion engine."""
from pathlib import Path
import json,re,html,hashlib,collections,sys
sys.path.insert(0,'/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
R=Path('result'); V=R/'_проверка/versions'; meta=json.loads((V/'pages.native.json').read_text()); pages=meta['pages']
raw=(V/'report.native.md').read_text(); split=re.split(r'<!-- pdf_page: (\d+) -->',raw); chunks={n:split[2*n] for n in range(1,248)}
log=[]; ocr_archive={}; excluded={}
def note(n,action,reason):log.append({'pdf_page':n,'action':action,'source_basis':reason})
# Quarantine unverified supplemental OCR rather than expose recognizer noise as author text.
for n,t in chunks.items():
 pattern=r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\.\n\n(.*?)(?=\n\n(?:>|<details>))'
 m=re.search(pattern,t,re.S)
 if m:
  ocr_archive[n]=m.group(1);chunks[n]=t[:m.start()]+t[m.end():]
  note(n,'Supplemental automatic OCR moved to the review ledger; native body retained','Diagnostic-image triage: duplicated native words and OCR artifacts; not accepted as additional source text. Raster body on 192–193 handled separately.')
# Native objects are paired with the already rendered HTML, so numbers are never regenerated.
for n,t in list(chunks.items()):
 prefix=t.split('> Служебная')[0].split('<details>')[0]
 matches=list(re.finditer(r'<p>.*?</p>|<table>.*?</table>',prefix,re.S)); objs=pages[n-1]['objects']
 assert len(matches)==len(objs),(n,len(matches),len(objs))
 pairs=list(zip(matches,objs)); removed=[]
 covers={1,4,13,36,71,93,111,133,168,189}
 if n not in covers:
  removed=[i for i,(m,o) in enumerate(pairs) if o['kind']=='text' and o['bbox'][3]<100]
  excluded[n]=[{'bbox':pairs[i][1]['bbox'],'html':pairs[i][0].group()} for i in removed]
 # Page 5: geography columns are interleaved by candidate; page 10: five cards must be read top-to-bottom in each column.
 order=list(range(len(pairs)))
 if n==5:
  def key(i):
   b=objs[i]['bbox'];x,y=b[:2]
   if b[3]<100:return(-1,x,y)
   if x<650:
    if y<755:return(0,0,y)
    return(0,1 if x<350 else 2,y)
   return(1 if x<1360 else 2,0 if x<1000 else 1,y)
  order.sort(key=key);note(n,'Restored the two geography columns; grouped priority cards by column','Full page_0005.png, native object coordinates; source numbers and text unchanged.')
 if n==10:
  def key(i):
   b=objs[i]['bbox'];x,y=b[:2]
   if b[3]<100:return(-2,x,y)
   if y<185:return(-1,x,y)
   return(int((x-40)//360),y,x)
  order.sort(key=key);note(n,'Restored five independent event columns','Full page_0010.png; source objects reordered, no numerical rewriting.')
 # Standard top strip is navigation, established visually on source pages; preserve its exact text in audit.
 new='\n\n'.join(pairs[i][0].group() for i in order if i not in removed)
 if matches:
  chunks[n]=prefix[:matches[0].start()]+new+t[matches[-1].end():]
# Confirmed nonprinting font-mapping control, all instances visually checked on their five source pages.
for n in [4,5,10,14,189]:
 count=chunks[n].count('\x03');chunks[n]=chunks[n].replace('\x03','');note(n,f'Removed {count} U+0003 font-map controls','Full original source images; positions correspond to spacing and no visible symbol.')
# Source cover and chapter titles/slogans. Only exact observed display tracking is normalized.
cover_data={
 4:('О КОМПАНИИ','01','ЛИДИРУЮЩИЕ ПОЗИЦИИ В МИРОВОЙ АЛМАЗОДОБЫВАЮЩЕЙ ОТРАСЛИ',1,5),
 13:('СТРАТЕГИЯ УСТОЙЧИВОГО РАЗВИТИЯ','02','ОБЕСПЕЧИВАЕМ ЭКОНОМИЧЕСКУЮ УСТОЙЧИВОСТЬ, ИНТЕГРИРУЯ ОТВЕТСТВЕННЫЕ ПРАКТИКИ',3,6),
 36:('УПРАВЛЕНИЕ И ДЕЛОВАЯ ЭТИКА','03','СВЯЗЫВАЯ ПРОШЛОЕ И БУДУЩЕЕ, ФОРМИРУЕМ ЭТИЧЕСКИЕ ОРИЕНТИРЫ',2,4),
 71:('РАЗВИТИЕ ЧЕЛОВЕЧЕСКОГО КАПИТАЛА','04','СОХРАНЯЯ ПРЕЕМСТВЕННОСТЬ, ВОСПИТЫВАЕМ ПРОФЕССИОНАЛОВ',3,4),
 93:('ОХРАНА ТРУДА И ПРОМЫШЛЕННАЯ БЕЗОПАСНОСТЬ','05','СОЗДАВАЯ БЕЗОПАСНЫЕ УСЛОВИЯ ТРУДА ДЛЯ КАЖДОГО, СОХРАНЯЕМ ЖИЗНЬ И ЗДОРОВЬЕ',3,4),
 111:('ИЗМЕНЕНИЕ КЛИМАТА И ЭНЕРГОЭФФЕКТИВНОСТЬ','06','ЗАБОТЯСЬ О КЛИМАТЕ СЕГОДНЯ, ОБЕСПЕЧИВАЕМ СТАБИЛЬНОСТЬ ДЛЯ БУДУЩИХ ПОКОЛЕНИЙ',3,5),
 133:('ОХРАНА ОКРУЖАЮЩЕЙ СРЕДЫ','07','СОХРАНЯЯ ПРИРОДНЫЕ БОГАТСТВА, РАБОТАЕМ ДЛЯ БУДУЩИХ ПОКОЛЕНИЙ',3,4),
 168:('РАЗВИТИЕ РЕГИОНОВ ПРИСУТСТВИЯ','08','РАЗВИВАЯ КУЛЬТУРУ, СОХРАНЯЕМ ТРАДИЦИИ',3,4),
 189:('ПРИЛОЖЕНИЯ','09','ДОВЕРИЕ В ОСНОВЕ ЭФФЕКТИВНОГО СОТРУДНИЧЕСТВА',1,4)}
for n,(title,num,slogan,first,last) in cover_data.items():
 t=chunks[n];ps=list(re.finditer('<p>.*?</p>',t.split('> Служебная')[0],re.S))
 t=t[:ps[-last].start()]+'<p>'+slogan+'</p>'+t[ps[-1].end():]
 ps=list(re.finditer('<p>.*?</p>',t,re.S));t=t[:ps[0].start()]+f'<h2>{title}</h2>\n\n<p>{num}</p>'+t[ps[first-1].end():];chunks[n]=t
 note(n,'Normalized display tracking in title and slogan; transcribed the decorative chapter number','Source page image; navigation and original photograph retained.')
# Cover contains image-only company name/year absent from native text.
chunks[1]='\n<a id="pdf-page-1"></a>\n\n<p>АЛРОСА</p>\n\n<p>2025</p>\n\n<p>ТРАДИЦИИ. ОПЫТ. РАЗВИТИЕ</p>\n\n'+chunks[1][chunks[1].index('<details>'):]
note(1,'Added company/year, corrected slogan, removed OCR artifacts','Full cover image; document title is the opening heading.')
# Rebuild page 9 table from existing native cells, keeping every source number literally.
n=9;t=chunks[n];table=re.search('<table>.*?</table>',t,re.S);soup=BeautifulSoup(table.group(),'html.parser');rows=[[c.decode_contents() for c in tr.find_all('td',recursive=False)] for tr in soup.find_all('tr')]
nonempty=lambda row:[c for c in row if BeautifulSoup(c,'html.parser').get_text().strip()]
header=['ПОКАЗАТЕЛЬ','2022<sup>2</sup>','2023','2024','2025','ЗАИНТЕРЕСОВАННЫЕ СТОРОНЫ, ДЛЯ КОТОРЫХ СОЗДАЕТСЯ ЦЕННОСТЬ']
out=['<p>GRI 201-1 · GRI 14.9.2 · GRI 14.23.2 · СОКБ 19 · СОКБ 61 · СОКБ 64</p>','<table>','<tr>'+''.join('<th>'+x+'</th>' for x in header)+'</tr>']
for ri in list(range(2,9))+list(range(10,17)):
 cells=nonempty(rows[ri])
 if ri in [8,12]:cells=[cells[0]+' '+cells[1]]+cells[2:]
 if 2<=ri<=8:
  cells=cells[:5]
  if ri==2:cells.append('Широкий круг заинтересованных сторон')
  out.append('<tr>'+''.join('<td>'+c+'</td>' for c in cells[:5])+('<td rowspan="7">'+cells[5]+'</td>' if ri==2 else '')+'</tr>')
 else:
  if len(cells)==5:cells.append('')
  assert len(cells)==6,(ri,cells)
  out.append('<tr>'+''.join('<td>'+c+'</td>' for c in cells)+'</tr>')
out.append('</table>');chunks[n]=t[:table.start()]+'\n'.join(out)+t[table.end():]
chunks[n]=chunks[n].replace('<p>ТЬ</p>','')
note(9,'Replaced 18 detector columns with six semantic columns; restored the stakeholder rowspan and full header','Full source page image. All numerical strings and footnote superscripts taken from native candidate cells unchanged.')
# Page 244: three semantic columns and two independent records, with image-only arrow directions transcribed.
t=chunks[244];tabs=list(re.finditer('<table>.*?</table>',t,re.S));assert len(tabs)==2
soups=[BeautifulSoup(x.group(),'html.parser') for x in tabs]
measures1=max((c.decode_contents() for c in soups[0].find_all('td')),key=len)
measures2=max((c.decode_contents() for c in soups[1].find_all('td')),key=len)
head='<table><tr><th>ГРУППА РиВУР</th><th>НАЗВАНИЕ РИСКА/ВОЗМОЖНОСТИ</th><th>МЕРОПРИЯТИЯ ПО УПРАВЛЕНИЮ РиВУР</th></tr>'
a=head+'<tr><td>Управление и деловая этика (продолжение)</td><td><strong>Снижение динамики развития инноваций</strong><br/>Вероятность: низкая<br/>Влияние: среднее<br/>Уровень риска: средний<br/>CAPEX ▲<br/>OPEX ▲<br/>Выручка ▼<br/>Временной горизонт: среднесрочный</td><td>'+measures1+'</td></tr></table>'
b=head+'<tr><td>Охрана окружающей среды</td><td><strong>Возможность поглощения парниковых газов кимберлитом</strong><br/>CAPEX ▲<br/>OPEX ▼<br/>(выгода от реализации потенциального климатического проекта может превысить инвестиционные затраты)<sup>1</sup><br/>Временной горизонт: долгосрочный</td><td>'+measures2+'</td></tr></table>'
t=t[:tabs[1].start()]+b+t[tabs[1].end():];t=t[:tabs[0].start()]+a+t[tabs[0].end():];chunks[244]=t
# The six detached header lines have now been incorporated in table headers.
for label in ['ГРУППА','РиВУР','НАЗВАНИЕ','РИСК А/ВОЗМОЖНОСТИ','МЕРОПРИЯТИЯ','ПО\u00a0УПРАВЛЕНИЮ РиВУР']:
 chunks[244]=chunks[244].replace('<p>'+label+'</p>','',1)
note(244,'Rebuilt two records into the source three-column structure; read arrow symbols and restored title/attribute connections','Full page_0244.png. Ambiguous glyph is a space between title words. Measures and note copied from native cells.')
# Embedded scan of the independent assurance report, with visually confirmed OCR corrections.
corrections={'дапее':'далее','АК «АПРОСА»':'АК «АЛРОСА»','зтики':'этики','узеренность':'уверенность','критериез':'критериев','вспедствие':'вследствие','инслектирование':'инспектирование','зэходящих':'входящих','хоторые':'которые','раздепе':'разделе','СЕ»':'GRI»','СК!»':'GRI»','атчетности':'отчетности','подпежит':'подлежит','попученных':'полученных','BO зсех':'во всех','TOT':'тот','огоаниченной':'ограниченной','GRi':'GRI','OPH3':'ОРНЗ','(O00':'(ООО','АПРОСА':'АЛРОСА'}
scan=[]
for i in range(3):
 text=(R/f'_проверка/ocr/p192_{i}.txt').read_text()
 if i==0:text=text[text.index('Заключение независимого'):];text='ФБК\n\nАудит | Консалтинг | Право\n\n'+text
 for old,new in corrections.items():text=text.replace(old,new)
 # Detached page footer is recorded literally from the raster, not accepted from OCR.
 text=re.split(r'\nАК [«Ц]',text)[0].strip()
 text=text.replace('Отчет},','Отчет).').replace('(ПАО)}','(ПАО))').replace('(ПАО)},','(ПАО)).').replace('GRI» (далее — Применимые критерии),','GRI» (далее — Применимые критерии).').replace('бухгалтеров. которые','бухгалтеров, которые').replace('Отчета,\n','Отчета.\n')
 if i==0:
  text=text.replace('по отчетности’','по отчетности<sup>1</sup>').replace("' GRI Sustainability Reporting Standards",'1 GRI Sustainability Reporting Standards')
 if i==1:
  text=text.replace('(пересмотренным}', '(пересмотренным)').replace('Задание;', 'Задание,').replace('задание;', 'задание,').replace('документирования.', 'документирования,').replace('данных;', 'данных,').replace('ссылки Ha', 'ссылки на').replace('и ‘элементов','и элементов')
  text=re.sub(r'(?m)^[e®©»]\s+','• ',text).replace('*« ', '• ')
 if i==2:
  text=text.replace('© содержит','• содержит').replace('« является','• является').replace('АК«АЛРОСА»','АК «АЛРОСА»')
  # Signature is graphic; remove OCR scribbles. Restore the source two-column requisites as two blocks.
  start=text.index('Руководитель задания,');end=text.index('Дата заключения')
  text=text[:start]+'Руководитель задания, обеспечивающего ограниченную уверенность, по результатам которого составлено заключение, действует от имени аудиторской организации на основании доверенности № 67/26 от 03 июня 2026 года.\n\nВладимир Юлианович Скобарев (ОРНЗ 21606080523)\n\n'+text[end:]
  text=text.replace('(АК «АЛРОСА» (ПАО)},','(АК «АЛРОСА» (ПАО)).').replace('д, 44','д. 44').replace('2002г.','2002 г.')
  text+='\n\nРеквизиты аудиторской организации\n\nНаименование:\n\nОбщество с ограниченной ответственностью «Финансовые и бухгалтерские консультанты» (ООО «ФБК»).\n\nАдрес юридического лица в пределах места нахождения юридического лица:\n\n101000, г. Москва, ул. Мясницкая, д. 44, стр. 2.\n\nВнесено в Единый государственный реестр юридических лиц 24 июля 2002 г. за основным государственным регистрационным номером 1027700058286.\n\nОсновной регистрационный номер записи в реестре аудиторов и аудиторских организаций саморегулируемой организации аудиторов 11506030481.'
 # Join soft linebreaks inside OCR paragraphs; paragraphs remain separate.
 paras=[re.sub(r'(?<!\n)\n(?!\n)',' ',p).strip() for p in text.split('\n\n') if p.strip()]
 scan.append(f'### Служебно: растровый лист {i+1} из 3\n\n'+'\n\n'.join(html.escape(p).replace('&lt;sup&gt;','<sup>').replace('&lt;/sup&gt;','</sup>') for p in paras)+f'\n\nАК «АЛРОСА» (ПАО)\n\nЗаключение независимого практикующего специалиста по заданию, обеспечивающему ограниченную уверенность\n\n{i+1} из 3\n')
scan[2]+='\n![Подпись в заключении](assets/assurance_signature.png)\n'
for i in range(3):
 scan[i]+=f'\n<details>\n<summary>Исходный растровый лист {i+1}</summary>\n\n![Лист {i+1} заключения](assets/assurance_{i+1}.png)\n\n</details>\n'
insert='\n\n> Служебная пометка: текст трех растровых листов извлечен локальным OCR; исправлены ошибки, подтверждённые изображениями. Полная повторная посимвольная сверка не завершена (pending).\n\n'+'\n\n'.join(scan)+'\n\n'
t=chunks[192];pos=t.index('> Служебная информация: ссылки');chunks[192]=t[:pos]+insert+t[pos:]
note(192,'Added full body of all three scanned assurance sheets using local Tesseract rus+eng; corrected visible OCR errors, separated signature and requisites','Three raster originals extracted from source PDF; rotated 90 degrees and inspected individually. Final character-level proofreading remains pending.')
# Certificate: full visual reading, including text missed by OCR.
cert='''### Российский союз промышленников и предпринимателей

СВИДЕТЕЛЬСТВО

об общественном заверении корпоративного нефинансового отчета

**Отчет об устойчивом развитии Группы АЛРОСА за 2025 год**

прошел процедуру общественного заверения в Совете РСПП по нефинансовой отчетности, индексам и рейтингам устойчивого развития:

Отчет об устойчивом развитии Группы АЛРОСА за 2025 год содержит значимую информацию по основным направлениям ответственной деловой практики в соответствии с принципами Социальной хартии российского бизнеса и с достаточной полнотой раскрывает сведения о деятельности Компании в этих направлениях.

Развернутое заключение Совета РСПП об общественном заверении Отчета об устойчивом развитии Группы АЛРОСА за 2025 год направлено в Компанию, которая может публиковать его без каких-либо изменений и использовать как для внутрикорпоративных целей, так и в целях коммуникаций с заинтересованными сторонами.

Регистрационный номер 343.01.294.03.25

Президент РСПП — А. Шохин

Москва, 2026

![Свидетельство с графической подписью и печатью](assets/certificate.png)
'''
from PIL import Image
Image.open(R/'_проверка/ocr/p193_0.jpeg').save(R/'assets/certificate.png')
t=chunks[193];pos=t.index('> Служебная информация: ссылки');chunks[193]=t[:pos]+cert+'\n\n'+t[pos:]
note(193,'Transcribed full raster certificate; recovered issuer, title and place/year missed by OCR','Full source image and extracted certificate raster inspected.')
# Fold extracted PDF annotation destinations, which are technical repetitions, without dropping destinations.
for n,t in list(chunks.items()):
 pat=r'> Служебная информация: ссылки исходного PDF\n\n(<ul>.*?</ul>)'
 t=re.sub(pat,r'<details>\n<summary>Служебно: ссылки исходного PDF</summary>\n\n\1\n\n</details>',t,flags=re.S)
 chunks[n]=t
# Preserve every original diagnostic, record what was actually reviewed; do not promote triage to checked.
fully_checked={1,4,13,36,71,93,111,133,168,189,193,244}
for x in pages:
 n=x['pdf_page'];x['original_issues']=x.get('issues',[])[:];x['conversion_status']='converted';x['review_status']='checked' if n in fully_checked else 'pending';x['semantic_source_review_completed']=n in fully_checked
 x['verification_scope']='Full source-page content review' if n in fully_checked else 'Native conversion; diagnostics inspected where flagged; full source-page review pending'
 x['source_image']=f'assets/page_{n:04}.png';x['printed_page']=None if n in {1,4,13,36,71,93,111,133,168,189} else str(n)
 x['content_type']='mixed raster and native text' if n in {192,193} else ('illustrated chapter divider' if n in covers else ('native text with tables and graphics' if x['tables'] else 'native text and graphics'))
 x['diagnostic_review_completed']=True;x['source_image_triage_completed']=bool(x['original_issues']) or n in {192,193}
 x['corrections']=[e for e in log if e['pdf_page']==n]
 x['issues']=[] if n in fully_checked else ['Полная сверка текста, порядка чтения и связей по оригиналу не завершена.']
 if x.get('tables') and n not in fully_checked and n!=9:x['issues'].append('Геометрическая сетка кандидата: возможны раздробленные/пустые колонки и нарушенные связи; требуется сверка всех ячеек.')
 if n==9:x['issues'].append('Таблица сверена и исправлена; остальной текст и примечания страницы требуют полной повторной сверки.')
 if n in ocr_archive and n not in fully_checked:x['issues'].append('Непроверенный дополнительный OCR вынесен в служебный реестр; текст/подписи внутри графики требуют окончательной сверки.')
 if n==192:x['issues'].append('Тело трех растровых листов добавлено OCR; окончательная вычитка пунктуации и реквизитов pending.')
 if n==225:x['issues'].append('Часть назначений исходных ссылок не установлена; адреса не выдуманы.')
 if n in [4,5,10,14,189]:x['unresolved_unicode']=0
 if n==244:x['ambiguous_cell_assignments_resolved']=x['ambiguous_cell_assignments'];x['ambiguous_cell_assignments']=[]
 if n not in fully_checked:
  marker=f'<a id="pdf-page-{n}"></a>'
  warning='\n\n> Служебно: converted / pending — полная сверка этой страницы по оригиналу не завершена.'
  if x.get('tables') and n!=9:warning+=' Геометрическая сетка таблиц требует проверки смысловых колонок и объединений.'
  chunks[n]=chunks[n].replace(marker,marker+warning,1)
# First source title, then explicitly separate the technical status.
intro='# ОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ\n\n> Служебно: рабочая конвертация всех 247 физических страниц. Текстовый слой, таблицы, изображения и OCR растровых листов собраны ниже. Полная сверка всего документа по оригиналу не завершена; постраничные статусы приведены в `_проверка/pages.json`.\n\n'
report=intro+'\n\n'.join(f'<!-- pdf_page: {n} -->'+chunks[n].strip('\n') for n in range(1,248))+'\n'
# Ensure comments remain independently delimited from anchors.
report=re.sub(r'(<!-- pdf_page: \d+ -->)(?=\S)',r'\1\n',report)
(R/'report.md').write_text(report)
meta['pages']=pages;meta['summary']={'physical_pages':247,'conversion_status':'converted','review_status':'pending','fully_checked_pages':sorted(fully_checked),'source_image_diagnostic_triage_pages':[x['pdf_page'] for x in pages if x['source_image_triage_completed']],'limitations':'Full content review remains pending except the explicitly listed checked pages. Contact sheets used only for diagnostic triage.'}
(R/'_проверка/pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
for name,data in [('changes.json',log),('supplemental_ocr_unaccepted.json',ocr_archive),('excluded_navigation.json',excluded)]:
 (R/'_проверка'/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
coverage=json.loads((V/'native_coverage.original.json').read_text());coverage['native_candidate_report_sha256']=coverage.pop('report_sha256');coverage['report_sha256']=hashlib.sha256((R/'report.md').read_bytes()).hexdigest();coverage['coverage_applies_to']='Original native candidate before reviewed exclusions and corrections; see versions/report.native.md and changes.json';coverage['semantic_source_review_completed']=False;coverage['review_status']='pending';coverage['pending_pages']=[n for n in range(1,248) if n not in fully_checked];(R/'_проверка/native_coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n')
print('saved',len(report),'characters;',len(log),'edits;',len(ocr_archive),'OCR blocks quarantined')
