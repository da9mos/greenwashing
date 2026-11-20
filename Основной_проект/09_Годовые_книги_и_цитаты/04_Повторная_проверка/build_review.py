"""Build immutable project-agent reassessments from real saved web responses.
No web requests or synthetic research are performed by this script.
"""
from pathlib import Path
import json,hashlib,re,subprocess,sys,copy
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
D=Path(__file__).resolve().parent; B=D.parent.parent; OLD=D.parent/'02_Проверка_фактов'; CORE=B/'03_Фактчекинг/Агент/factcheck.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def read(p):return json.loads(p.read_text())
J={p.name[:2]:(p,read(p)) for p in (D/'journal').glob('*.json')}
def at(n):return datetime.strptime(J[n][1]['at']['current_time'],'%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Asia/Yekaterinburg')).isoformat()
def section(n,ref):return J[n][1]['result'].split('cite'+ref+'',1)[1].split('--------------------------------------------------------------------------------',1)[0]
def lines(n,ref,lo,hi):
 out=[]
 for x in section(n,ref).splitlines():
  m=re.match(r'L(\d+)(?:@[^:]+)?: (.*)',x)
  if m and lo<=int(m[1])<=hi:out.append(m[2])
 assert out,(n,ref,lo,hi)
 return '\n'.join(out)
def source(id,url,publisher,n,ref,content,locator,ind='issuer',date=None,period='2023',origin=None,basis=None):
 assert content and all(any(x in entry[1]['result'] for entry in J.values()) for x in content.splitlines())
 return dict(id=id,url=url,publisher=publisher,origin_group=origin or publisher,origin_basis=basis or 'Первичный корпоративный документ; не независимый аудит.',publication_date=date,publication_date_note=None if date else 'Точная дата публикации в прочитанной части не указана.',event_period=period,locator=locator,content=content,content_sha256=hashlib.sha256(content.encode()).hexdigest(),tool_ref='web.run '+ref+'; journal/'+J[n][0].name,retrieved_at=at(n),access='excerpt',independence=ind)
def query(p,n,idx,dr,ids,note,ref):
 p['searches'].append(dict(id='FRESH_'+n+'_'+str(idx),direction=dr,query=J[n][1]['args']['search_query'][idx]['q'],tool='web.run',tool_ref='web.run '+ref+'; journal/'+J[n][0].name,searched_at=at(n),status='completed',source_ids=ids,outcome_note=note))
def align(entity,period,boundary,metric,unit=None):return {k:dict(status='not_applicable' if k=='unit' and unit is None else 'matched',reason=v) for k,v in dict(entity=entity,period=period,boundary=boundary,metric=metric,unit=unit or 'Качественное утверждение без числовой единицы.').items()}
def evidence(id,s,quote,al,reason,kind=None,record=None,scope=None,recordid=None):
 e=dict(id=id,source_id=s['id'],quote=quote,relation='supports',reason=reason,alignment=al)
 if kind:e['evidence_basis']=dict(kind='authoritative_primary',claim_kind=kind,record_type=record,competence=reason,why_sufficient=scope,source_locator=s['locator'],statement_scope=scope,record_id=recordid or s['url'],source_url=s['url'],reviewed_record=True,not_circular=True)
 return e
def aspect(id,prop,ids,reason,status='supported'):return dict(id=id,proposition=prop,status=status,evidence_ids=ids,reason=reason)
def parent(year,c):return OLD/(f'run/results/C{c:06}.r000003.json' if year==2023 else f'annual_{year}/run/results/C000001.r000001.json')
audit=read(D/'Цели_проверки.json'); proposed=audit['proposed_rows'];P=[];lineage=[]
for i,pr in enumerate(proposed):
 year=pr['year'];c=[1,3,5,6,1,1][i]; path=parent(year,c);p=read(path)
 originals=read(OLD/('run/plan.json' if year==2023 else f'annual_{year}/run/plan.json'))['claims'];original=copy.deepcopy(originals[c-1]['original'])
 original.update(id=pr['quote_id'],quote=pr['exact_quote'],statement=pr['exact_quote'],exact_quote=pr['exact_quote'],aspect=pr['minimal_whole_quote_task'],parent_atom_ids=pr['preserved_aspect_ids'],target_alignment_audit=str(D/'Цели_проверки.json'))
 original.pop('metric',None);original.pop('value',None);original.pop('unit',None)
 p.update(quote=pr['exact_quote'],revision=1,checked_at=datetime.now(ZoneInfo('Asia/Yekaterinburg')).isoformat(),reviewer='Codex; project FACT_CHECK_AGENT; reassessment with competent primary records, preserved real search history',assessed_quote_complete=True,aspect_coverage_confirmed=True,aspect_coverage_reason='Все существенные пропозиции полной отображаемой цитаты выделены явно; прежние атомы сохранены в metadata. Никакой результат одного атома не распространен на непроверенную часть цитаты.')
 p['source_review']['locator']=str((D.parent/'01_Сверка_цитат'/('citation_review.json' if year==2023 else 'annual_citation_review.json')).resolve())+'; quote_id='+pr['quote_id']+'; physical_page='+str(original['pdf_page'])
 p['provenance']=dict(parent_assessment_path=str(path),parent_assessment_sha256=sha(path),parent_atom_ids=pr['preserved_aspect_ids'],reused_native_journal_base=str(OLD/'journal'),older_native_journal_base=str(B/'08_Аудит_агентов_2026-11-20/03_Фактчекинг/journal'),new_native_journal_base=str(D/'journal'),search_dates_preserved=True)
 # Old source/search timestamps remain untouched. Their journal paths resolve via provenance.
 lineage.append(dict(quote_id=pr['quote_id'],parent_packet_path=str(path),parent_packet_sha256=sha(path),parent_atom_ids=pr['preserved_aspect_ids'],full_quote_unchanged=p['quote']==read(path)['quote']))
 P.append((p,original,year))
# 2023 whole commitment: publicly announced, not fulfillment or legal opinion.
p,o,y=P[0]
vurl='https://gazetavibor.ru/news/novosti/2023-04-13/salavat-i-sterlitamak-voshli-v-federalnyy-proekt-chistyy-vozduh-soglasheniya-podpisany-3218587'
vtext=section('08','turn38search0')
start=vtext.index('— В частности,');end=vtext.index('Все мероприятия',start)
content=vtext[start:end].strip()
v=source('PRIMARY_PROMISE',vurl,'Пресс-служба ООО Газпром нефтехим Салават; газета Выбор','08','turn38search0',content,'Кэшированный развернутый текст статьи13.04.2023: абзац прямой речи пресс-службы; direct open turn38view0=403','issuer_republication','2023-04-13',origin='Пресс-служба ООО Газпром нефтехим Салават',basis='Полный текст статьи, фактически полученный поисковым инструментом, содержит прямую атрибуцию пресс-службе и точные обязательства. Это первичное публичное объявление в републикации. Прямой URL403; не заявляется прямое чтение сайта или оригинала подписанного соглашения.')
p['sources'].append(v);p['evidence']=[]
al=align('ООО Газпром нефтехим Салават прямо названо.','Публикация13.04.2023 о подписании12.04.2023.','Эксплуатируемые объекты НВОС I категории; именно содержание публичного обещания.','Снижение выбросов, план САКВ, сведения о стационарных источниках; исполнение не утверждается.')
props=['Публично объявлено обязательство провести мероприятия и добиться снижения совокупного объема выбросов ЗВ.','Публично объявлено обязательство разработать план создания САКВ на эксплуатируемых объектах НВОС I категории.','Публично объявлено обязательство представить сведения о количестве стационарных источников, планируемых к оснащению САКВ до2025г.']
p['evidence']=[evidence('PC',v,content,al,'Пресс-служба участника соглашения компетентна публично объявить собственные обязательства; отдельное датированное сообщение предшествует проверяемому отчету.','announced_commitment','official_announcement','Три публичных обязательства, без удостоверения юридической полноты договора и исполнения.','Сообщение пресс-службы13.04.2023 о соглашении12.04.2023')]
p['aspects']=[aspect('A'+str(k+1),pr,['PC'],'Точная пропозиция приведена в отдельном датированном сообщении пресс-службы.') for k,pr in enumerate(props)]
p['target']=dict(proposition='В2023г. Салават публично принял названные в цитате обязательства по снижению выбросов, плану САКВ и сведениям об источниках.',entity='ООО «Газпром нефтехим Салават»',period='2023; до2025г. относится к планируемому оснащению источников',boundary='Публичные обязательства предприятия и объектов НВОС I категории; без проверки исполнения',assessment_object='promise_made')
p['verdict']='true';p['reason']='Выбор, сообщение пресс-службы Салавата13.04.2023: обещаны снижение выбросов, план САКВ и сведения об источниках, оснащаемых до2025г. Подтверждено объявление этих обязательств, их исполнение здесь не заявлено.'
p['limitations']=['Прочитан развернутый кэшированный текст инструмента; прямое открытие URL403. Это публичное объявление, не юридический оригинал соглашения и не подтверждение исполнения.','Предписание РПН135-В от28.09.2023 — неблагоприятный контекст, не опровержение существования обещания.']
query(p,'07',0,'support',['PRIMARY_PROMISE'],'Точное содержание трёх объявленных обязательств найдено; развернутый текст прочитан в последующем реальном запросе.','turn37search4')
query(p,'08',0,'support',['PRIMARY_PROMISE'],'Получен развернутый текст с прямой атрибуцией пресс-службе; доступ отмечен как cached excerpt, прямойURL403.','turn38search0')
# expenses: separate comparative statistical record plus arithmetic.
p,o,y=P[1]
f=source('PRIMARY_COST','https://sustainability.gazpromreport.ru/2023/environment-and-environmental-policy/environmental-protection/','Газпром, Отчет о социальной деятельности2023','08','turn38view1',lines('08','turn38view1',92,97),'Таблица расходы: столбцы2021/2022/2023 и прирост2023/2022, L92–97')
p['sources'].append(f)
al=align('Консолидированная Группа Газпром.','Таблица2022/2023, не текущие расходы2024.','Та же серия общих расходов на ООС в РФ: инвестиции + текущие затраты + плата за НВОС; сопоставимость дополнительно раскрыта в отдельной сравнительной таблице2024.','Общая сумма и относительный прирост, не экологический эффект.','Млн руб. в первичной таблице; млрд руб. в цитате; рост в %.')
p['evidence']=[evidence('COST',f,f['content'],al,'Компания ведет и раскрывает консолидированный статистический учет собственных расходов; прочитана отдельная сравнительная таблица другого отчета, а не повтор исходного предложения.','disclosed_quantity','statistical_record','2023:52 068,48+43 517,90+646,23=96 232,61 млн руб.; 2022:89 138,75 млн руб.','ОСД2023, показатель23, таблица расходов2021–2023')]
p['aspects']=[aspect('A1','Общие расходы Группы на ООС в РФ в2023 составили96,23млрд руб.',['COST'],'96 232,61млн/1000=96,23261млрд, округляется до96,23.'),aspect('A2','Те же расходы выросли на8,0% к2022.',['COST'],'(96 232,61/89 138,75−1)×100=7,9582%, округление до8,0%.')]
p['target']['proposition']='В2023г. общие расходы Группы Газпром на ООС в РФ составили96,23млрд руб., увеличившись на8,0% относительно2022.'
p['verdict']='true';p['reason']='Газпром, отдельная сравнительная таблица ОСД2023:96 232,61 млн руб. против89 138,75 млн руб. в2022. Это96,23 млрд руб. и рост8,0% после округления.'
p['limitations']=['Статистическая запись корпоративного учета, не независимый аудит расходов и не оценка экологического эффекта.']
query(p,'05',0,'support',['PRIMARY_COST'],'Найден отдельный статистический документ; таблица прочитана черезopen/find.','turn35search6')
query(p,'09',0,'support',['N_FIN'],'Сопоставлена серия расходов РФ со следующим отчетным раскрытием; это дополнительный первичный контекст, не независимый аудит.','turn39search3')
# principle as documented policy, not measured environmental effect.
p,o,y=P[2]
u='https://www.rostovoblgaz.ru/upload/iblock/9e2/9e2b5253bd93f7b25160f34da0b64db4.pdf'
pc=lines('12','turn42view1',386,404)+'\n'+lines('12','turn42view1',410,425)
s=source('POLICY',u,'ПАО Газпром, Экологическая политика; официальное корпоративное издание Прометей','12','turn42view1',pc,'Прометей №8–9(89–90), октябрь–ноябрь2015, p5/P4, L386–425','issuer_republication',period='Редакция2015, применима в2023 по реестру документов',origin='ПАО Газпром, текст утвержденной Экологической политики',basis='Воспроизведен нормативный текст политики на официальной площадке общества Группы, не исходная проверяемая фраза отчета2023. Прямой головнойURL timeout; официальный корпоративный текст доступен.')
r=source('POLICY_REGISTER','https://sustainability.gazpromreport.ru/2023/appendices/key-sustainability-development-documents/','Газпром, реестр ключевых документов2023','12','turn42view3',lines('12','turn42view3',234,237),'Реестр действующих документов2023, строка Экологическая политика L237')
p['sources'] += [s,r]
al=align('Текст политики ПАО Газпром распространяется на Компанию и дочерние общества.','Редакция2015 перечислена в реестре документов2023 без изменений.','Закрепленный принцип сохранения окружающей среды и природных богатств; не универсальное утверждение об отсутствии вреда.','Сохранение среды, ресурсосбережение, биоразнообразие прямо закреплены как обязательства политики.')
p['evidence']=[evidence('POL',s,pc,al,'Прочитан нормативный текст утвержденной компанией политики: официальный документ о собственных принципах компетентен подтверждать их закрепление.','declared_policy','approved_policy','Документально закрепленный принцип сохранения окружающей среды и природных ресурсов.','Экологическая политика, постановление25.05.2015№21'),evidence('POLREG',r,r['content'],al,'Официальный реестр компании фиксирует применимую в2023 редакцию и акт ее утверждения.','declared_policy','approved_policy','Применимость нормативной политики2015 в отчетном контексте2023.','Реестр ключевых документов2023, строка Экологическая политика')]
p['aspects']=[aspect('A1','Сохранение благоприятной окружающей среды закреплено как принцип Газпрома.',['POL','POLREG'],'Отдельный нормативный текст закрепляет официальную позицию и обязательства; реестр2023 подтверждает применимость.'),aspect('A2','Сохранение природных богатств страны закреплено как принцип Газпрома.',['POL','POLREG'],'Политика требует ресурсосбережения и сохранения биоразнообразия и уязвимых природных объектов.')]
p['target']['principle_test']='documented_policy';p['target']['boundary']='Закрепленный в корпоративной политике принцип сохранения окружающей среды и природных богатств; не оценка экологического результата всех операций.'
p['verdict']='true';p['reason']='Экологическая политика Газпрома: сохранение благоприятной среды, ресурсосбережение и биоразнообразие закреплены в обязательствах компании. Реестр документов2023 подтверждает действие этой политики; это заявленный принцип, а не оценка всех операций.'
p['limitations']=['Проверен закрепленный принцип компании; надзорные нарушения сохранены в risk_checks и не отрицаются. Фактическая экологическая эффективность и соблюдение принципа во всех операциях не заявляются.']
query(p,'10',0,'support',['POLICY'],'Найден отдельный полный нормативный текст политики на официальной корпоративной площадке; прочитан отдельно.','turn40search12')
query(p,'11',1,'support',['POLICY_REGISTER'],'Найдены действующая редакция и реестр2023; содержимое прочитано отдельно.','turn41search15,turn41search17')
# group oversight counters: no distinct underlying consolidated record found.
p,o,y=P[3]
pp=[read(parent(2023,k)) for k in [6,7,8]]
p['evidence']=copy.deepcopy(pp[0]['evidence']);p['aspects']=[]
for i,(num,unit) in enumerate([('761','проверка требований ООС и природопользования'),('517','выявленных нарушений'),('563','проверки без выявленных нарушений')]):
 p['aspects'].append(aspect('A'+str(i+1),'2023, объекты Группы Газпром: '+num+' '+unit+'.',[p['evidence'][0]['id']],'Внешний свод актов с полным периметром Группы и этой метрикой не найден; сама исходная цитата не является отдельной учетной записью.','unresolved'))
p['target']['proposition']='В2023 государственные органы провели761экологическую проверку на объектах Группы Газпром, выявили517нарушений;563проверки не выявили нарушений.'
p['verdict']='insufficient_evidence';p['reason']='Газпром сообщает761 проверку,517 нарушений и563 проверки без нарушений. ДелоА07-40790/2023 подтверждает предписание РПН Салавату№135-В от28.09.2023, но открытого свода для проверки трех итогов всей Группы нет.'
p['limitations']=['517нарушений нельзя складывать с563проверками: единицы различаются. Надзорные акты отдельных обществ не удостоверяют и не опровергают групповые итоги.']
query(p,'06',0,'support',['N_STAT'],'Найдена исходная публикация, не отдельный консолидированный свод надзорных органов.','turn36search12')
query(p,'07',1,'support',[],'Поиск вне источников самого отчета не дал сопоставимого консолидированного свода; иные761 — трудовая охрана/счетчики газа, не эта метрика.','turn37search0,turn37search12')
query(p,'07',2,'contradiction',[],'Найдены отдельные судебные эпизоды иной метрики; полного опровержения трех счетчиков нет.','turn37search3,turn37search6')
# ownership: whole mixed form plus total direct/indirect control, no imposed cutoff day.
p,o,y=P[4]
a=source('ANNUAL_OWN','https://draga.ru/wp-content/uploads/2025/06/2.-go-2024.pdf','ПАО Газпром, Годовой отчет2024; публикация регистратора ДРАГА','10','turn40view2',lines('10','turn40view2',9300,9306)+'\n'+lines('03','turn33view1',9307,9311),'Годовой отчет2024, печатнаяp155/P156: структура капитала и сноска о контроле','issuer_republication',period='2024',origin='ПАО Газпром',basis='Регистратор публикует первичный годовой отчет эмитента, не независимый аудит. Прочитаны таблица акционеров и пояснение механизма косвенного контроля.')
f=source('FIN_FORM','https://investonic.ru/wp-content/uploads/2025/07/finansovyj-otchet-gazprom-gazp-2024.pdf','ПАО Газпром, Финансовый отчет2024; копия Investonic','08','turn38view2',lines('08','turn38view2',486,488),'Финансовый отчет2024, P12: классификация формы собственности','issuer_republication',period='2024',origin='ПАО Газпром',basis='Первичная годовая бухгалтерская форма общества прямо раскрывает смешанную российскую собственность с федеральной долей; копия финансового отчета, не аналитическая оценка посредника.')
a['tool_ref'] += '; web.run turn33view1; journal/03_exact_primary_followup.json'
p['sources'] += [a,f]
al=align('ПАО Газпром, не другие общества.','Контекст2024, отчет и новостная публикация2024; дополнительный день не требуется исходной цитатой.','Прямое владение РФ и контроль через Роснефтегаз/Росгазификацию; не только прямой пакет.','Смешанная форма и контроль доли акций, а не экономическая доля, умноженная по цепочке.','Форма собственности и проценты акций; сумма38,37+10,97+0,89=50,23.')
p['evidence']=[evidence('OWN',a,a['content'],al,'Годовое раскрытие эмитента компетентно устанавливает структуру акционеров и механизм государственного контроля; отдельный первичный документ, не проверяемый абзац ОУР.','ownership','ownership_disclosure','Структура собственности и50,23% прямого+косвенного контроля РФ в контексте2024.','Годовой отчет2024, раздел уставный капитал, p155'),evidence('FORM',f,f['content'],al,'Годовая бухгалтерская форма эмитента прямо раскрывает форму собственности, отдельно от исходного ОУР.','ownership','ownership_disclosure','Смешанная российская собственность с федеральной долей.','Финансовый отчет2024, классификацияОКФС41')]
# Existing IF24 news readback is admissible for broad2024 context; fix prior artificial date mismatch.
s=next(s for s in p['sources'] if s['id']=='IF24');p['evidence'].append(evidence('IFOWN',s,'Государство контролирует более 50% бумаг напрямую (38,37%) и через госкомпании АО "Роснефтегаз" (10,97%) и "Росгазификация" (0,89%).',al,'Интерфакс03.12.2024 сообщает о том же прямом и косвенном государственном контроле; соответствует контексту2024 без придуманного дня.'))
p['aspects']=[aspect('A1','ПАО Газпром имеет смешанную российскую собственность с долей федеральной собственности.',['FORM','OWN'],'Это прямо указано в годовой бухгалтерской форме; таблица капитала содержит федерального владельца и прочих зарегистрированных лиц.'),aspect('A2','Суммарная доля акций под прямым и косвенным контролем РФ превышает50%.',['OWN','IFOWN'],'38,37+10,97+0,89=50,23%. РФ100%владеет Роснефтегазом, тот74,55%Росгазификации: учитывается контроль пакетов, не перемноженная экономическая доля.')]
p['target']=dict(proposition='В контексте2024 ПАО Газпром имеет смешанную российскую собственность с федеральной долей, а прямой и косвенный контроль РФ превышает50% акций.',entity='ПАО «Газпром»',period='2024; точный день в исходной цитате не задан',boundary='Форма собственности и контроль акций ПАО Газпром, включая контролируемые государством общества',assessment_object='reported_fact')
p['verdict']='true';p['reason']='Финансовый отчет2024: смешанная российская собственность с федеральной долей. Интерфакс и годовой отчет: РФ38,37%, Роснефтегаз10,97%, Росгазификация0,89%; вместе под контролем РФ50,23%.'
p['limitations']=['Прямое владение РФ38,37% отличается от прямого и косвенного контроля50,23%; арифметика относится к контролируемым пакетам, а не к экономической доле через перемножение.']
query(p,'01',0,'support',['ANNUAL_OWN','IF24'],'Найдены и прочитаны первичная структура капитала и независимая новостная справка.','turn31search12,turn31search3')
query(p,'06',3,'support',['FIN_FORM'],'Найдены ОКФС41 и отдельный финансовый отчет2024; документ прочитан.','turn36search0,turn36search13')
# 2025 implementation retains genuine on-site independent reporting and original risk checks.
p,o,y=P[5]
p['reason']='Интерфакс, репортаж6мая2025: специалисты Газпрома подключали мемориалы к сетевому газу в проекте «Храним огонь Победы». Телеканал Санкт-Петербург также сообщает о газификации мемориальных комплексов в рамках проекта.'
for a in p['aspects']:a['reason']='Собственные репортажи с мероприятия6мая2025 подтверждают именно факт проекта и подключение мемориалов; годовые счетчики не входят в цитату.'
# Build inputs first, then native prepare -> next -> ingest -> check -> export.
transcript=[];present=[]
for year in [2023,2024,2025]:
 group=[(p,o) for p,o,y in P if y==year];g=D/str(year);g.mkdir(exist_ok=True)
 mdsha=group[0][0]['source_review']['source_md_sha256']
 write(g/'input.json',dict(manifest=dict(report_id='GAZP-'+str(year)+'-'+('ЭО' if year==2023 else 'ОУР'),source_sha256=mdsha),claims=[o for p,o in group]))
 def cli(*args):
  r=subprocess.run([sys.executable,str(CORE),*map(str,args)],capture_output=True,text=True);transcript.append(dict(args=list(map(str,args)),returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));write(D/'cli_transcript.json',transcript)
  if r.returncode:raise RuntimeError(r.stdout+r.stderr)
  return r.stdout
 cli('prepare',g/'input.json',g/'run');cli('next',g/'run');plan=read(g/'run/plan.json')
 for idx,(p,o) in enumerate(group):
  p.update(source_sha256=plan['source_sha256'],claim_id=plan['claims'][idx]['id'])
  # Every inherited search stays indexed identically; new records are only appended.
  packet=g/'responses'/f"{p['claim_id']}.r000001.json";write(packet,p);cli('ingest',g/'run',packet)
  ridx=next(i for i,x in enumerate(P) if x[0] is p);pr=proposed[ridx]
  used={e['source_id'] for e in p['evidence']};pub=[dict(name=s['publisher'],url=s['url'],assertion=next((e['reason'] for e in p['evidence'] if e['source_id']==s['id']),s['origin_basis']),access=s['access'],independence=s['independence']) for s in p['sources'] if s['id'] in used]
  if year==2023 and ridx==3:
   r=next(s for s in p['sources'] if s['id']=='R23');pub.append(dict(name='Арбитражный суд Республики Башкортостан, делоА07-40790/2023',url=r['url'],assertion='Предписание РПН Салавату№135-В от28.09.2023; отдельный эпизод, не групповой свод.',access=r['access'],independence=r['independence']))
  present.append(dict(atom_id=o['id'],quote_id=o['id'],report_id=plan['report_id'],legacy_atomic_source_ids=pr['preserved_aspect_ids'],year=year,pdf_page=o['pdf_page'],type=o['type'],block=o['block'],claim_id=p['claim_id'],verdict=p['verdict'],check_label={'true':'Правда','insufficient_evidence':'Не установлено'}[p['verdict']],short_reason=p['reason'],sources=pub,exact_quote=p['quote'],aspect=p['target']['proposition'],target=p['target'],aspects=p['aspects'],parent_atom_ids=pr['preserved_aspect_ids'],source_md_sha256=mdsha,record_path=str((g/'run/results'/f"{p['claim_id']}.r000001.json").relative_to(D)),assessment_path=str((g/'run/results'/f"{p['claim_id']}.r000001.json").relative_to(D)),export_path=str((g/'export/claims.json').relative_to(D)),assessed_quote_complete=True))
 cli('check',g/'run');cli('export',g/'run',g/'export')
write(D/'presentation.json',dict(schema_version='esg-user-presentation-1.0',scope='Шесть полных выбранных цитат, прежние10атомов сохранены вmetadata; не полнота годов.',checked_at=datetime.now(ZoneInfo('Asia/Yekaterinburg')).isoformat(),rows=present))
write(D/'provenance.json',dict(parent_assessments=lineage,prior_native_journal_roots=[str(OLD/'journal'),str(B/'08_Аудит_агентов_2026-11-20/03_Фактчекинг/journal')],fresh_native_journals=[dict(path=str(p),sha256=sha(p)) for p in (D/'journal').glob('*.json')],reused_risk_queries='Те же entity/period scopes; queries, searched_at, tool_ref, source_ids и0-basedindexes сохранены из родителей; новые запросы добавлены в конец.',new_scope='4полные2023+1полная2024+1полное предложение2025; существенные аспекты3+2+2+3+2+2=14; старые10проверочныхатомов сохранены.'))
print(json.dumps(dict(rows=len(present),verdicts=[p['verdict'] for p in present],summaries=[read(D/str(y)/'export/summary.json') for y in [2023,2024,2025]]),ensure_ascii=False,indent=2))
