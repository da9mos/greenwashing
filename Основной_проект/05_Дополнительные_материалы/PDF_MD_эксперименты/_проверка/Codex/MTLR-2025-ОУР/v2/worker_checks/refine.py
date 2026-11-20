"""Addressed refinement of the supplied native candidate; no new OCR/model calls."""
from pathlib import Path
import json,re,html,sys,hashlib,collections
ROOT=Path(__file__).resolve().parents[1]; CHECK=ROOT/'_проверка'
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf as fitz
src=json.loads((ROOT.parent/'source.json').read_text());doc=fitz.open(src['source_pdf'])
records=json.loads((CHECK/'baseline/pages.json').read_text())['pages']
base=(CHECK/'baseline/report.md').read_text()
parts=re.split(r'<!-- pdf_page: \d+ -->',base)[1:]
changes=[]

def order(obs,depth=0):
    if len(obs)<2 or depth>20:return sorted(obs,key=lambda o:(round(o['bbox'][1]/3),o['bbox'][0]))
    # Empty vertical strips preserve whole tables and side-by-side text columns.
    ranges=sorted((o['bbox'][0],o['bbox'][2]) for o in obs);end=ranges[0][1];gaps=[]
    for a,b in ranges[1:]:
        if a-end>10:gaps.append((a-end,(a+end)/2))
        end=max(end,b)
    if gaps:
        cut=max(gaps)[1]
        return order([o for o in obs if o['bbox'][2]<=cut],depth+1)+order([o for o in obs if o['bbox'][0]>=cut],depth+1)
    # A spanning title must precede the columns it heads, not interleave them.
    starts=sorted(set(round(o['bbox'][0],0) for o in obs))
    options=[]
    for a,b in zip(starts,starts[1:]):
        if b-a<15:continue
        cut=b-5
        left=[o for o in obs if o['bbox'][2]<=cut];right=[o for o in obs if o['bbox'][0]>=cut];cross=[o for o in obs if o not in left and o not in right]
        if not left or not right or len(cross)>max(3,len(obs)*.1):continue
        # Only isolate spanning objects that are above or below all remaining text.
        if cross and (max(o['bbox'][3] for o in cross)<=min(o['bbox'][1] for o in left+right)+1):
            options.append((len(left)*len(right)/(len(cross)+1),order(cross,depth+1)+order(left,depth+1)+order(right,depth+1)))
        elif cross and min(o['bbox'][1] for o in cross)>=max(o['bbox'][3] for o in left+right)-1:
            options.append((len(left)*len(right)/(len(cross)+1),order(left,depth+1)+order(right,depth+1)+order(cross,depth+1)))
    if options:return max(options,key=lambda t:t[0])[1]
    # Split at horizontal whitespace only after trying independent columns.
    ranges=sorted((o['bbox'][1],o['bbox'][3]) for o in obs);end=ranges[0][1];gaps=[]
    for a,b in ranges[1:]:
        if a-end>3:gaps.append((a-end,(a+end)/2))
        end=max(end,b)
    if gaps:
        cut=max(gaps)[1]
        return order([o for o in obs if o['bbox'][3]<=cut],depth+1)+order([o for o in obs if o['bbox'][1]>=cut],depth+1)
    return sorted(obs,key=lambda o:(round(o['bbox'][1]/3),o['bbox'][0]))

def table(headers,rows):
    return '<table>\n<tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in headers)+'</tr>\n'+'\n'.join('<tr>'+''.join('<td>'+html.escape(str(c))+'</td>' for c in r)+'</tr>' for r in rows)+'\n</table>'

supp={}
supp[9]=table(['Направление','Активы, обозначенные на карте'],[
('Металлургия','Вяртсильский метизный завод; «Ижсталь»; БМК; ЧМК; «Уралкуз»; Гурьевский филиал ПАО «ЧМК»; Братский завод ферросплавов'),
('Горная добыча','«Москокс»; «Мечел-Кокс»; «Южный Кузбасс»; Коршуновский ГОК; ЯРК; «Якутуголь»'),
('Энергетика','«Кузбассэнергосбыт»; Южно-Кузбасская ГРЭС'),('Порты','«Порт Мечел-Темрюк»; «Торговый порт Посьет»'),('Сбыт','«Мечел-Сервис Бел»; «Мечел-Сервис» (головной офис)')])+ '\n\nПримечание: БМК — Белорецкий металлургический комбинат; ЧМК — Челябинский металлургический комбинат; «Уралкуз» — «Уральская кузница»; ЯРК — Якутская рудная компания.'
supp[14]='''### Приоритетные направления устойчивого развития «Мечела»

- Социальная поддержка работников
- Развитие регионов присутствия, поддержка местных сообществ
- Снижение выбросов загрязняющих веществ, управление отходами, водными ресурсами
- Декарбонизация и энергоэффективность
- Ответственные практики управления
- Управление цепочкой поставок'''
supp[33]='''### Водный баланс в 2025 году

GRI 303-3, 303-4, 303-5

'''+table(['Показатель','Объем, млн м³','Доля'],[
('Водозабор','195,16',''),('Поверхностные водные объекты','178,24','91%'),('Подземные водные объекты','3,79','2%'),('Вода, предоставленная третьими лицами','13,13','7%'),('Водосброс','175,73',''),('В сети канализации','10,48','6%'),('В поверхностные воды','165,25','94%'),('Невозвратное водопотребление¹','19,43',''),('Оборотное водоснабжение','1677,63','89,6%')])+'''

Основные водные объекты: Белорецкое водохранилище, реки Миасс, Белая, Иж, Томь, Уса, Ольжерас, Гладкая, Юуванйоки.

### Объем водозабора, водоотведения и водопотребления, млн м³

GRI 303-3, 303-4, 303-5

'''+table(['Год','Водозабор','Водоотведение','Водопотребление'],[('2022','117,38','90,22','27,16'),('2023','151,97','89,56','62,41'),('2024','139,44','86,08','53,36'),('2025','195,16','175,73','19,43')])
supp[37]='### Объем утилизированных шлаков ООО «Мечел-Материалы» в 2025 году, млн т\n\n'+table(['Вид шлака','Объем, млн т'],[('Шлак электросталеплавильный','0,04'),('Шлак конвертерный','0,55'),('Шлак доменный основной негранулированный','1,08')])
supp[48]=table(['Территория','Физические климатические риски на карте'],[
('Санкт-Петербург','Экстремальное изменение среднегодовых температур; осадки; грозы'),('Москва','Гололед; лесные пожары; экстремальное изменение среднегодовых температур; осадки; грозы'),('Ижевск','Наводнения; экстремальное изменение среднегодовых температур; осадки'),('Темрюк','Сильные ветра; осадки'),('Белорецк','Наводнения; сильные ветра; грозы; осадки'),('Челябинск','Экстремальное изменение среднегодовых температур; пожароопасность'),('Междуреченск','Сильные ветра; экстремальное изменение среднегодовых температур; осадки'),('Братск','Осадки; наводнения'),('Нерюнгри','Лесные пожары; экстремальное изменение среднегодовых температур; таяние многолетнемерзлых пород (ММП)'),('Посьет','Сильные ветра')])+ '\n\nЭкстремальное изменение среднегодовых температур — аномальная жара или аномальный холод.'
risks=['Риск появления профзаболеваний','Риск травмирования работников','Риск возникновения инцидентов и аварий','Риск повторных несчастных случаев','Риск получения штрафов','Риск влияния вредных производственных факторов']
measures=[
('Регулярные профилактические медицинские осмотры работников, а также проведение медицинского осмотра перед началом рабочей смены на опасных производствах.',[0,5]),
('Обеспечение работников всеми видами СИЗ и специальной униформой.',[0,1,5]),
('Проведение оценки управления профессиональными рисками.',[1,5]),
('Обучение сотрудников и повышение осведомленности о соблюдении мер безопасности на производстве.',[1,5,2,3]),
('Повышение культуры безопасности труда.',[1,5,3]),
('Разработка соответствующих локальных нормативных актов.',[1,2,3]),
('Информирование работников о действующих законах и нормативных правовых актах по охране труда.',[1,4,3]),
('Своевременное профильное обучение руководителей и специалистов.',[1,2,4]),
('Обеспечение безопасности технологических процессов и производственного оборудования.',[2,3]),
('Повсеместное внедрение систем обнаружения и тушения пожаров, их своевременный технический осмотр и замена.',[2,3]),
('Учет и анализ состояния производственного травматизма, расследование несчастных случаев.',[2,3]),
('Профилактика производственного травматизма и профессиональных заболеваний.',[2,3,0]),
('Совершенствование системы управления ОТиПБ.',[2,4]),
('Производственный контроль и регулярная оценка условий труда.',[4,5,0,1])]
supp[57]=table(['№','Мероприятия','Предотвращаемые риски'],[(i+1,m,'; '.join(risks[r] for r in rr)) for i,(m,rr) in enumerate(measures)])
supp[69]='''### Сотрудникам всегда доступны в ЛК:

- остаток отпусков;
- история кадровых перемещений;
- должностная инструкция и Положение о подразделении;
- новости Компании;
- контакты ЦОО;
- вакансии в рамках Группы.

### Через ЛК можно заказать и получить:

- расчетный лист за любой период;
- график отпусков;
- справки;
- копии кадровых документов.'''
supp[109]='''### Структура корпоративного управления ПАО «Мечел»

'''+table(['Орган / подразделение','Связь, подписанная на схеме','Орган / подразделение'],[
('Общее собрание акционеров','Утверждает','Внешний аудитор'),('Комитет по аудиту','Одобряет','Внешний аудитор'),('Общее собрание акционеров','Избирает','Совет директоров*'),('Совет директоров*','Формирует','Комитет по аудиту'),('Комитет по аудиту','Готовит предложение','Совет директоров*'),('Совет директоров*','Формирует','Комитет по инвестициям и стратегическому планированию; Комитет по назначениям и вознаграждениям'),('Комитет по инвестициям и стратегическому планированию; Комитет по назначениям и вознаграждениям','Готовит предложения','Совет директоров*'),('Совет директоров*','Избирает','Коллегиальный исполнительный орган — Правление; Генеральный директор — председатель Правления'),('Генеральный директор — председатель Правления','Обеспечивает создание','Блок «Управление рисками и внутренний контроль»')])+'''

Подразделения, также представленные на схеме: Управление внутреннего аудита; Корпоративный секретарь (Департамент корпоративного управления и собственности).

Условные обозначения: функциональное подчинение — серая стрелка; административное подчинение — черная стрелка.

* 55% состава Совета директоров — независимые директора.

> Служебная пометка: неподписанные связи подчинения сохранены на исходном изображении; их текстовое описание требует дополнительной проверки.'''
supp[123]='''### Карта рисков Компании с изменением оценок

'''+table(['№','Наименование рисков','По сравнению с прошлым годом'],[
('1','Экологические риски','оценка риска выросла'),('2','Климатические риски','оценка риска не изменилась'),('3','Риски в области ОТиПБ','оценка риска снизилась'),('4','Риски в области управления персоналом','оценка риска снизилась'),('5','Социальные риски','оценка риска не изменилась'),('6','Корпоративные риски','оценка риска выросла'),('7','Отраслевые риски','оценка риска выросла'),('8','Риски цепочки поставок','оценка риска не изменилась'),('9','Финансовые риски','оценка риска не изменилась'),('10','ИТ-риски','оценка риска снизилась')])+'''

Вертикальная ось: «Степень влияния риска на цели» — от низкой до высокой. Горизонтальная ось: «Вероятность» — от низкой до высокой.

> Служебная пометка: числовая шкала осей отсутствует. Расположение рисков сохранено на исходном изображении; точные координаты не вычислялись.'''

# Read native glyphs within visually established row and column boundaries on p.159.
def glyph_table(page,xs,ys,merged_rows=()):
    groups=[[[] for _ in range(len(xs)-1)] for _ in range(len(ys)-1)]
    for bi,b in enumerate(page.get_text('rawdict')['blocks']):
        for li,l in enumerate(b.get('lines',[])):
            for sp in l['spans']:
                for c in sp.get('chars',[]):
                    x=(c['bbox'][0]+c['bbox'][2])/2;y=(c['bbox'][1]+c['bbox'][3])/2
                    for r in range(len(ys)-1):
                        if ys[r]<=y<ys[r+1]:
                            for k in range(len(xs)-1):
                                if xs[k]<=x<xs[k+1]:groups[r][k].append((bi,li,sp['flags'],c['c']))
    rows=[]
    for ri,row in enumerate(groups):
        if ri in merged_rows:row=[sum(row,[])]
        cells=[]
        for g in row:
            out='';prev=None;raised=False
            for bi,li,fl,c in g:
                if prev is not None and prev!=(bi,li):
                    if raised:out+='</sup>';raised=False
                    out+='<br/>'
                new=bool(fl&1)
                if new!=raised:out+='<sup>' if new else '</sup>';raised=new
                out+=html.escape(c);prev=(bi,li)
            if raised:out+='</sup>'
            cells.append(out.strip())
        rows.append('<tr>'+''.join(('<td colspan="3">' if ri in merged_rows else '<td>')+c+'</td>' for c in cells)+'</tr>')
    return '<table>\n'+'\n'.join(rows)+'\n</table>'

outparts=[]
for n,(part,record) in enumerate(zip(parts,records),1):
    native=part.split('> Служебная пометка')[0].split('> Служебная информация')[0].split('<details>')[0]
    tags=re.findall(r'<p>.*?</p>|<table>.*?</table>',native,re.S)
    assert len(tags)==len(record['objects']),(n,len(tags),len(record['objects']))
    obs=[dict(o,text=t) for o,t in zip(record['objects'],tags)]
    # Navigation/footer roles were established on the source layout overview.
    keep=[];excluded=[]
    for o in obs:
        b=o['bbox'];plain=re.sub('<[^>]+>','',o['text']).strip()
        if b[3]<40 or (b[1]>638 and b[0]>1150 and plain==str(n)) or plain=='mechel.ru':excluded.append(o)
        else:keep.append(o)
    obs=keep
    if n==1:
        obs=[{'bbox':[40,60,600,470],'kind':'manual','text':'# Сила людей и промышленности\n\nМечел\n\nОтчет об устойчивом развитии\n\n2025'}]
    titles={3:'О компании',13:'Подход к управлению устойчивым развитием',22:'Экологический аспект',52:'Социальный аспект',107:'Управленческий аспект',144:'Приложения'}
    if n in titles:obs.insert(0,{'bbox':[40,40,1100,55],'kind':'manual','text':'## '+titles[n]})
    if n==33:
        obs=[o for o in obs if not (o['bbox'][0]>410 and 50<o['bbox'][1]<623) and not(o['bbox'][0]<410 and 375<o['bbox'][1]<630)]
    if n==37:obs=[o for o in obs if not(o['bbox'][0]<410 and 180<o['bbox'][1]<370)]
    if n==57:obs=[o for o in obs if o['kind']!='table']
    if n==69:
        obs=[o for o in obs if not(o['bbox'][0]<400 and 70<o['bbox'][1]<165)]
        obs.append({'bbox':[42,80,394,159],'kind':'manual','text':'<p>&gt;36,8 тыс. человек пользовались личным кабинетом в 2025 году</p>'})
    if n==109:obs=[o for o in obs if not(o['bbox'][0]>410 and 175<o['bbox'][1]<205)]
    if n==159:
        obs=[o for o in obs if o['bbox'][1]<105 or o['bbox'][1]>630]
        left=[107.5,119,130.5,142,153,164.5,176,187,221,255,272.5,300.5,312,329,346,360,371.5,383,399.9,411,451,504.5,521.5,538.5,592.5,604,621]
        right=[107.5,119,130.5,153,181.5,198.5,221.5,244,261,278,289.5,300.5,349,360,459.5,476.5,504.5,521.5,533,550,567,584,607,630]
        obs.extend([{'bbox':[42,107,567,621],'kind':'manual','text':glyph_table(doc[158],[42,65,270,568],left,(1,14))}, {'bbox':[624,107,1149,630],'kind':'manual','text':glyph_table(doc[158],[624,646,851.5,1149],right,(0,12))}])
    if n in supp:
        boxes={37:[42,180,394,380],9:[42,200,1149,620],14:[420,110,1149,525],33:[420,65,1149,620],48:[42,180,715,615],57:[52,90,450,627],69:[42,310,394,620],109:[420,180,1149,595],123:[42,65,582,375]}
        obs.append({'bbox':boxes[n],'kind':'manual','text':supp[n]})
    ordered=order(obs)
    # Page 4: explicit column order verified in the source, spanning heading first.
    if n==4:
        title=[o for o in obs if o['bbox'][0]>300 and o['bbox'][3]<90]
        rest=[o for o in obs if o not in title]
        ordered=title+sum([sorted([o for o in rest if a<=(o['bbox'][0]+o['bbox'][2])/2<b],key=lambda o:o['bbox'][1]) for a,b in [(0,310),(310,600),(600,880),(880,1200)]],[])
    body='\n\n'.join(o['text'] for o in ordered)
    # Retain the supplied PDF annotation destinations and full page assets unchanged.
    links=''
    if '> Служебная информация: ссылки исходного PDF' in part:
        links='> Служебная информация: ссылки исходного PDF'+part.split('> Служебная информация: ссылки исходного PDF',1)[1].split('<details>',1)[0]
    status='> Служебная пометка: рабочая транскрипция. Полная построчная сверка этой страницы по PDF не завершена; исходное изображение сохранено ниже.\n\n' if n!=1 else ''
    outparts.append(f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+status+body+'\n\n'+links+f'\n\n<details>\n<summary>Источник: PDF-страница {n}</summary>\n\n![Полная исходная страница {n}](assets/page_{n:04d}.png)\n\n</details>')
    record.update(conversion_status='converted',review_status='checked' if n==1 else 'pending',semantic_source_review_completed=n==1,printed_page=None if n==1 else str(n),content_type='text_layer_with_graphics',verification_scope='Layout overview; selected source regions reviewed. Not a full page proofread.' if n!=1 else 'Cover text read against source image',issues=[] if n==1 else ['Полная построчная сверка страницы и всех связей по оригиналу не завершена.'])
    if n in [109,123]:record['issues'].append('Графические связи / расположение элементов сохранены изображением; текстовое представление не полностью проверено.')
    if record.get('ocr_chars'):
        changes.append({'pdf_page':n,'action':'Removed unverified whole-page OCR append; retained native text. Raster content restored separately where identified.','original_ocr_chars':record['ocr_chars']})
        record['ocr_append_removed']=True
    record['source_image_review']='layout_overview'
    if n in [1,4,9,14,33,37,48,57,69,109,123,132,155,159]:record['source_image_review']='selected_regions_at_full_resolution'
    if n in supp or n in [1,159]:changes.append({'pdf_page':n,'action':'Source-image-based restoration / structure correction','region_reviewed':True,'whole_page_checked':n==1})
    if n==159:record['issues'].append('Таблицы пересобраны из исходных глифов по визуальным границам строк и столбцов; нужна полная сверка всех ячеек.')
    record['excluded_navigation_objects']=len(excluded)
    (CHECK/'pages.json').write_text(json.dumps({'pages':records[:n]},ensure_ascii=False,indent=2))
report='\n\n'.join(outparts)+'\n'
# The document starts with the source title; technical notices follow inside pages.
(ROOT/'report.md').write_text(report)
(CHECK/'changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
(CHECK/'refined_integrity.json').write_text(json.dumps({'source_sha256':hashlib.sha256(Path(src['source_pdf']).read_bytes()).hexdigest(),'report_sha256':hashlib.sha256(report.encode()).hexdigest(),'physical_pages':len(records),'full_page_reviewed':[1],'layout_overview_pages':list(range(1,165)),'review_pending':list(range(2,165)),'baseline_coverage_applies_to':'baseline/report.md; final contains documented edits, navigation exclusions and visual transcriptions','note':'No claim of complete visual or semantic fidelity.'},ensure_ascii=False,indent=2))
print('Saved',len(records),'pages;',len(report),'characters')
