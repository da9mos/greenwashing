"""Reassess eight real project claims with transparent old/new search provenance."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo
D=Path(__file__).resolve().parent
P=D.parent.parent
OLD=P/'08_Аудит_агентов_2026-11-20/03_Фактчекинг'
FACT=P/'03_Фактчекинг/Агент'
sys.path.insert(0,str(FACT))
import factcheck
if (D/'run').exists(): raise SystemExit('Existing immutable run; do not overwrite.')
def write(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
reviewpath=D.parent/'01_Сверка_цитат/citation_review.json'
review=json.loads(reviewpath.read_text())
bindings={q['atomic_source_id']:q for q in review['atomic_bindings']}
J={p.name.split('_')[0]:(p,json.loads(p.read_text())) for p in (D/'journal').glob('*.json')}
def at(j): return datetime.strptime(J[j][1]['at']['current_time'],'%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Asia/Yekaterinburg')).isoformat()
def part(j,ref): return J[j][1]['result'].split('cite'+ref+'',1)[1].split('--------------------------------------------------------------------------------',1)[0]
def lines(j,ref,lo,hi):
 values=[]
 for line in part(j,ref).splitlines():
  m=re.match(r'L(\d+)(?:@[^:]+)?: (.*)',line)
  if m and lo<=int(m[1])<=hi: values.append(m[2])
 return '\n'.join(values)
def src(id,url,name,origin,basis,j,ref,locator,content,ind='issuer',date=None,event='2023',access='excerpt'):
 assert content and (content in J[j][1]['result'] or all(x in J[j][1]['result'] for x in content.splitlines()))
 return dict(id=id,url=url,publisher=name,origin_group=origin,origin_basis=basis,publication_date=date,publication_date_note=None if date else 'Точная дата публикации в прочитанном фрагменте не указана; год отчета не заменяет дату публикации.',event_period=event,locator=locator,content=content,content_sha256=hashlib.sha256(content.encode()).hexdigest(),tool_ref='web.run '+ref+'; journal/'+J[j][0].name,retrieved_at=at(j),access=access,independence=ind)
KOM=src('N_KOM','https://www.kommersant.ru/doc/5927481','Коммерсантъ','Пресс-служба правительства Республики Башкортостан','Редакционное сообщение по сведениям государственного контрагента; не заявление собственной проверки текста соглашения.','07','turn17view2','L106',lines('07','turn17view2',106,106),ind='independent',date='2023-04-12',event='2023-04-12')
SAL=src('N_SAL','https://www.salavatsovet.ru/2023/04/12/salavat-i-sterlitamak-vklyuchili-v-proekt-chistyj-vozdux/','Совет Салавата','Администрация ГО Салават / проектный офис Чистый воздух','Первичное официальное сообщение с объяснением руководителя проектного офиса; не содержит точных двух пунктов обязанностей.','09','turn19view4','L75–76','Следующая задача – оснащение труб системами автоматического контроля выбросов.',ind='independent',date='2023-04-12',event='2023-04-11/2023-04-12')
VIB=src('N_VIB','https://gazetavibor.ru/news/novosti/2023-04-13/salavat-i-sterlitamak-voshli-v-federalnyy-proekt-chistyy-vozduh-soglasheniya-podpisany-3218587','Выбор Салават','Пресс-служба ООО Газпром нефтехим Салават','Сам текст статьи приписывает изложение работ пресс-службе предприятия. Прямое открытие403 (turn12view0); текст выдан поиском, не открытый оригинал и не решающее доказательство.','04','turn14search0','Индексированный текст публикации13.04.2023; абзац об обязанностях','Предприятие обязуется разработать план создания систем автоматического контроля выбросов загрязняющих веществ (САКВ)',ind='issuer_republication',date='2023-04-13',event='2023-04-12',access='snippet')
FIN=src('N_FIN','https://sustainability.gazpromreport.ru/2024/environmental-protection/environmental-management/','Газпром, отчет2024','ПАО Газпром, собственная ретроспектива расходов','Первичная корпоративная таблица; не независимое подтверждение расходов.','09','turn19view1','L112/115/120; млнруб, столбцы2022/2023/2024',lines('09','turn19view1',120,120),event='2022/2023/2024')
POL=src('N_POL',FIN['url'],'Газпром, экологическая политика','ПАО Газпром, собственная политика','Наличие экологической политики не удостоверяет достижение измеримого результата или реальную иерархию приоритетов.','09','turn19view2','L47','Экологической политике ПАО «Газпром»',event='Политика2015 в отчете2024')
PDFURL='https://draga.ru/wp-content/uploads/2024/06/gazprom-environmental-report-2023-ru.pdf'
PDF_FIN=src('N_PDF_FIN',PDFURL,'Газпром, экологический отчет2023','ПАО Газпром; хостинг ДРАГА','Републикация проверяемого корпоративного отчета; не независимый аудит.','10','turn20view1','Физическая страница14, печатная12; L578–581',lines('10','turn20view1',578,581),ind='issuer_republication')
PDF_STAT=src('N_STAT',PDFURL,'Газпром, экологический отчет2023','ПАО Газпром; хостинг ДРАГА','Републикация исходного корпоративного раскрытия, а не полный реестр государственных проверок.','10','turn20view0','Физическая страница38, печатная36; L2215–2217',lines('10','turn20view0',2215,2217),ind='issuer_republication')
shorts=[
'Коммерсантъ: соглашение предусматривает САКВ до 2025 года; Совет Салавата: названа задача оснащения труб. Вывод: точная обязанность разработать план для объектов I категории не подтверждена доступным оригиналом соглашения; исполнение не установлено.',
'Коммерсантъ: соглашение предусматривает САКВ; Совет Салавата: описаны мониторинг и оснащение труб. Вывод: точный пункт о представлении количества источников в доступном оригинале соглашения не подтвержден; «до 2025 г.» относится к оснащению.',
'Газпром, отчет2023: 96,23 млрд руб.; отчет2024: 96 232,61 млн руб. за тот же год. Вывод: суммы согласуются после округления, но независимого подтверждения общих расходов Группы в РФ нет.',
'Газпром, отчет2024: 89 138,75 млн руб. за 2022 и 96 232,61 млн руб. за 2023 дают рост 7,96%; отчет2023 указывает 8,0%. Вывод: округление верно, но исходные суммы независимо не подтверждены.',
'Газпром: сохранение природы закреплено в экологической политике и названо принципом работы. Вывод: измеримый критерий «главного принципа» не задан; оценить эту декларацию как достигнутый результат нельзя.',
'Газпром, экологический отчет2023: государственные органы провели 761 проверку. Вывод: независимый полный реестр проверок объектов Группы за тот же год не подтверждает доступными данными этот итог.',
'Газпром, экологический отчет2023: выявлено 517 нарушений. Вывод: независимого свода актов по всей Группе нет; 26 нарушений Салавата не устанавливают и не опровергают групповые 517.',
'Газпром, экологический отчет2023: 563 проверки завершились без нарушений. Вывод: независимого полного перечня результатов нет; 517 нарушений нельзя складывать с 563 проверками.'
]
# Avoid implying a contrary independent register exists: missing register != contradiction.
shorts[5]='Газпром, экологический отчет2023: государственные органы провели 761 проверку. Вывод: независимого полного реестра проверок объектов Группы за тот же год нет, поэтому этот итог независимо не подтвержден.'
oldinput=json.loads((OLD/'atomic_input.json').read_text())
rows=[]
for row in oldinput['claims']:
 row=copy.deepcopy(row); b=bindings[row['id']]; assert b['verified']
 row.update(quote=b['exact_quote'],statement=b['atomic_proposition_label'],exact_quote=b['exact_quote'],aspect=b['atomic_proposition_label'],statement_is_direct_quote=False,quote_id=b['quote_id'],source_md_sha256=b['source_md_sha256'])
 row['prior_quote_assembly']=row.pop('quote_assembly')
 rows.append(row)
write(D/'input.json',{'claims':rows,'presentation_policy':'Full verified continuous parent quotation in quote/exact_quote; atomic analytical label in statement/aspect, explicitly not a direct quote.'})
factcheck.prepare(D/'input.json',D/'run')
plan=factcheck.load(D/'run'); now=datetime.now(ZoneInfo('Asia/Yekaterinburg')).isoformat(); presentation=[]; provenance=[]
(D/'responses').mkdir()
def query(id,dr,j,idx,ref,ids,note): return dict(id=id,direction=dr,query=J[j][1]['args']['search_query'][idx]['q'],tool='web.run',tool_ref='web.run '+ref+'; journal/'+J[j][0].name,searched_at=at(j),status='completed',source_ids=ids,outcome_note=note)
for n,row in enumerate(rows,1):
 parentpath=OLD/f'atomic_run/results/C{n:06}.r000001.json'; parent=json.loads(parentpath.read_text()); p=copy.deepcopy(parent)
 p.update(source_sha256=plan['source_sha256'],quote=row['exact_quote'],revision=1,checked_at=now,reason=shorts[n-1])
 p['target']['proposition']=row['aspect']
 for q in p['searches']: q['source_ids']=[]; q['outcome_note']+=' Исторический запрос08; прежняя дата и ссылка сохранены, полный ответ доступен по parent native_journal_base.'
 p['sources']=[]; p['evidence']=[]
 if n in (1,2):
  p['sources']=[KOM,SAL,VIB]
  for eidx,s in enumerate(p['sources'],1):
   p['evidence'].append(dict(id=f'N_E{eidx}',source_id=s['id'],quote=s['content'],relation='context',reason='Подтверждает общий контекст/изложение, но не независимо удостоверяет точный пункт оригинала соглашения; исполнение этим не проверяется.',alignment={a:{'status':st,'reason':why} for a,st,why in [('entity','matched','ООО Газпром нефтехим Салават названо в прочитанном материале.'),('period','matched','Апрель2023, принятие соглашения; срок действий отдельно не установлен.'),('boundary','unknown','Не прочитан юридический оригинал с точным списком объектов/источников.'),('metric','unknown','Точное обязательство данного атома не удостоверено открытым независимым первоисточником.'),('unit','not_applicable','Факт принятия обязанности; численное значение количества источников не заявлено.')]}))
  p['searches'] += [query('NEW_SUPPORT','support','03',0,'turn13search6',['N_VIB'],'Точный текст обязанностей найден в корпоративной пресс-службе через газету; прямой доступ403, не decisive.'),query('NEW_OPPOSING','contradiction','08',0,'turn18search0',[],'Сопоставимого опровержения принятия точного обязательства не найдено.'),dict(id='NEW_OPEN_KOM',direction='support',query=KOM['url'],tool='web.run open',tool_ref=KOM['tool_ref'],searched_at=KOM['retrieved_at'],status='completed',source_ids=['N_KOM'],outcome_note='Открыто сообщение по сведениям правительства; установлены границы содержания.'),dict(id='NEW_OPEN_SAL',direction='support',query=SAL['url'],tool='web.run find',tool_ref=SAL['tool_ref'],searched_at=SAL['retrieved_at'],status='completed',source_ids=['N_SAL'],outcome_note='Прочитан официальный муниципальный контекст; два точных пункта не приведены.')]
 elif n in (3,4):
  p['sources']=[FIN,PDF_FIN]
  olde=copy.deepcopy(parent['evidence'])
  for e,s in zip(olde,p['sources']): e.update(id='N_'+e['id'],source_id=s['id'],quote=s['content'])
  p['evidence']=olde
  p['searches'] += [query('NEW_SUPPORT','support','06',0,'turn16search14',[],'Поиск первичного независимого подтверждения экологических расходов; корпоративный отчет не независимый аудит.'),query('NEW_OPPOSING','contradiction','08',1,'turn18search15',[],'Не найдено сопоставимого исправления исходных показателей; финансовые котировки исключены.'),dict(id='NEW_OPEN_FIN',direction='support',query=FIN['url'],tool='web.run find',tool_ref=FIN['tool_ref'],searched_at=FIN['retrieved_at'],status='completed',source_ids=['N_FIN'],outcome_note='Прочитана таблица2022–2024 с тем же показателем и единицами; источник корпоративный.'),dict(id='NEW_OPEN_PDF',direction='support',query=PDFURL,tool='web.run find',tool_ref=PDF_FIN['tool_ref'],searched_at=PDF_FIN['retrieved_at'],status='completed',source_ids=['N_PDF_FIN'],outcome_note='Повторно прочитан исходный абзац; не независимое подтверждение.')]
 elif n==5:
  p['sources']=[POL]; e=copy.deepcopy(parent['evidence'][0]); e.update(id='N_E1',source_id=POL['id'],quote=POL['content']);p['evidence']=[e]
  p['searches'] += [query('NEW_SUPPORT','support','06',3,'turn16search14',[],'Проверен контекст политики; не найден операциональный критерий общего принципа.'),dict(id='NEW_OPEN_POL',direction='support',query=POL['url'],tool='web.run find',tool_ref=POL['tool_ref'],searched_at=POL['retrieved_at'],status='completed',source_ids=['N_POL'],outcome_note='Прочитано наличие и содержание политики; результат и эффективность не подменены принципом.')]
 else:
  p['sources']=[PDF_STAT]; e=copy.deepcopy(parent['evidence'][0]);e.update(id='N_E1',source_id=PDF_STAT['id']);p['evidence']=[e]
  p['searches'] += [query('NEW_SUPPORT','support','06',2,'turn16search1',[],'Независимого полного группового свода не найдено; нерелевантные газовые счетчики исключены.'),query('NEW_OPPOSING','contradiction','08',2,'turn18search12',[],'Прямого сопоставимого опровержения группового счетчика не найдено; отдельные предприятия не подменяют группу.'),dict(id='NEW_OPEN_STAT',direction='support',query=PDFURL,tool='web.run find',tool_ref=PDF_STAT['tool_ref'],searched_at=PDF_STAT['retrieved_at'],status='completed',source_ids=['N_STAT'],outcome_note='Прочитан весь абзац с тремя разными мерами учета; источник корпоративный.')]
 for a in p['aspects']:
  a['evidence_ids']=[e['id'] for e in p['evidence']];a['reason']=shorts[n-1]
 b=bindings[row['id']]
 p['source_review']=dict(status='verified',method=review['review_method']+'; проверен полный родительский абзац и привязка конкретного аспекта, не внешняя истинность',locator='../01_Сверка_цитат/citation_review.json; quote_id='+b['quote_id']+'; page='+str(b['page']),review_sha256=sha(reviewpath),source_md_sha256=review['source_md_sha256'],source_pdf_sha256=review['source_pdf_sha256'])
 p['research_lineage']=dict(parent_packet=str(parentpath.relative_to(P)),parent_packet_sha256=sha(parentpath),parent_native_journal_base=str((OLD/'journal').relative_to(P)),new_native_journal_base='journal/',new_input_reason='Полная непрерывная проверенная цитата вместо старых склеенных фрагментов; аспект хранится отдельно.')
 p['derived_research']=dict(reassessment=True,parent_packet_sha256=sha(parentpath),new_searches=True,prior_search_times_preserved=True)
 p['aspect_coverage_reason']='Полная цитата сохранена отдельно; оценивается только указанный атом '+row['id']+'. Все существенные части этого атома сохранены; другие части полной цитаты имеют собственные строки.'
 factcheck.validate(p,plan); out=D/f'responses/C{n:06}.r000001.json';write(out,p)
 names={s['id']:s['publisher'] for s in p['sources']}
 assertions=[]
 for s in p['sources']:
  assertion={'N_KOM':'Сообщает о соглашении и планируемой установке САКВ; точный пункт данного атома не приведен.','N_SAL':'Описывает задачу оснащения труб и развитие мониторинга; точных двух обязанностей не содержит.','N_VIB':'Поисковый текст пересказывает слова пресс-службы предприятия; оригинал закрыт403, поэтому не решающее подтверждение.','N_FIN':'Корпоративная таблица:2022=89 138,75млнруб,2023=96 232,61млнруб; независимым аудитом не является.','N_PDF_FIN':'Исходный корпоративный отчет:96,23млрдруб и8,0%; сравнение раскрытий не подтверждает фактическую независимую сумму.','N_POL':'Собственная экологическая политика; не задает измеримый критерий статуса главного принципа.','N_STAT':'Корпоративный итог за2023:761проверка,517нарушений,563проверки безнарушений; разные единицы учета.'}[s['id']]
  assertions.append(dict(name=s['publisher'],url=s['url'],assertion=assertion,access=s['access'],independence=s['independence']))
 presentation.append(dict(atom_id=row['id'],claim_id=p['claim_id'],verdict=p['verdict'],check_label='Непроверяемая декларация' if p['verdict']=='not_verifiable' else 'Недостаточно данных',short_reason=shorts[n-1],sources=assertions,exact_quote=row['exact_quote'],quote_id=row['quote_id'],aspect=row['aspect'],aspect_is_direct_quote=False,pdf_page=row['pdf_page'],type=row['type'],block='E'))
 provenance.append(dict(atom_id=row['id'],parent_packet=str(parentpath.relative_to(P)),parent_packet_sha256=sha(parentpath),response_sha256=sha(out),source_review_sha256=sha(reviewpath),old_searches=[{k:q[k] for k in ['id','query','direction','tool_ref','searched_at']} for q in parent['searches']],new_search_ids=[q['id'] for q in p['searches'] if q['id'] not in {q['id'] for q in parent['searches']}]))
write(D/'presentation.json',dict(schema_version='esg-user-presentation-1.0',checked_at=now,label_mapping={'true':'Правда','false':'Неправда','partial':'Частично правда','insufficient_evidence':'Недостаточно данных','not_verifiable':'Непроверяемая декларация','not_due':'Срок не наступил'},rows=presentation))
write(D/'provenance.json',dict(schema_version='reassessment-lineage-1.0',input_sha256=sha(D/'input.json'),old_run_unchanged=True,new_input_immutable=True,new_revision=1,reason='Новая версия исходной цитаты: полный непрерывный абзац, проверенный в09. Исторические searched_at не обновлялись; новые запросы сохранены отдельно.',parent_input_sha256=sha(OLD/'atomic_input.json'),source_review_sha256=sha(reviewpath),mappings=provenance))
print('Prepared eight reassessed packets and concise user presentation; no forced categorical verdicts.')
