"""Helpers for already executed, saved native web tool calls; no network calls."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo
D=Path(__file__).resolve().parent
J={p.name.split('_')[0]:(p,json.loads(p.read_text())) for p in (D/'journal').glob('*.json')}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def at(j):return datetime.strptime(J[j][1]['at']['current_time'],'%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Asia/Yekaterinburg')).isoformat()
def lines(j,ref,lo,hi):
 text=J[j][1]['result'].split('cite'+ref+'',1)[1].split('--------------------------------------------------------------------------------',1)[0];values=[]
 for line in text.splitlines():
  m=re.match(r'L(\d+)(?:@[^:]+)?: (.*)',line)
  if m and lo<=int(m[1])<=hi:values.append(m[2])
 return '\n'.join(values)
def src(id,url,publisher,origin,basis,j,ref,locator,content,ind='independent',date=None,event='2023'):
 assert content and (content in J[j][1]['result'] or all(x in J[j][1]['result'] for x in content.splitlines())),id
 return dict(id=id,url=url,publisher=publisher,origin_group=origin,origin_basis=basis,publication_date=date,publication_date_note=None if date else 'Точная календарная дата публикации в прочитанном фрагменте не указана.',event_period=event,locator=locator,content=content,content_sha256=hashlib.sha256(content.encode()).hexdigest(),tool_ref='web.run '+ref+'; journal/'+J[j][0].name,retrieved_at=at(j),access='excerpt',independence=ind)
def query(id,dr,j,idx,refs,ids,note,category=None):
 q=dict(id=id,direction=dr,query=J[j][1]['args']['search_query'][idx]['q'],tool='web.run',tool_ref='web.run '+refs+'; journal/'+J[j][0].name,searched_at=at(j),status='completed',source_ids=ids,outcome_note=note)
 if category:q['category']=category
 return q
R23=src('R23','https://onlineecology.com/file/download-inline/a273118f-2125-4e25-8130-6cea31672acf/%D0%9007-40790-2023__20240221.pdf','Арбитражный суд Республики Башкортостан; копия onlineecology','Арбитражный суд Республики Башкортостан','Первичный текст судебного решения; источник фактов о предписании — суд, не предприятие. Не групповой полный свод.','20','turn30view3','Страница1–2; строки19–20',lines('20','turn30view3',19,20),date='2024-02-21',event='Предписание28.09.2023; решение21.02.2024')
T23=src('T23','https://www.zakonrf.info/arbsud/doc-e4fae0db-51d2-5a32-bd56-0218ef396b78/','Одиннадцатый арбитражный апелляционный суд; копия ЗаконРФ','11 ААС, делоА65-20459/2023','Судебный текст о надзоре промышленной безопасности отдельного ООО; не экологический групповой счетчик.','20','turn30view4','L237',lines('20','turn30view4',237,237),date='2023-11-20',event='Предписание10.07.2023')
R24=src('R24','https://sudact.ru/arbitral/doc/fa1RlI0KetQ6/','Арбитражный суд Иркутской области; СудАкт','Арбитражный суд Иркутской области','Первичный судебный текст о споре ООО Газпром инвест с Росприроднадзором; заголовокагрегатора12.02расходится сдатойтекста13.02, использована дата полного решения в самом документе.','20','turn30view2','L24–29',lines('20','turn30view2',24,29),date='2025-02-13',event='Предписания2024; решение2025')
M24=src('M24','https://www.interfax.ru/russia/949646','Интерфакс','Пресс-служба Газпром трансгаз Югорск / правительствоХМАО / МЧС','В публикации явно названы источники сообщений; технический эпизод не независимое доказательство доли акций.','20','turn30view5','L27; короткий релевантный фрагмент','произошла разгерметизация газопровода с возгоранием.',ind='issuer_republication',date='2024-03-10',event='2024-03-09')
CATS=['rosp_enforcement','rost_enforcement','court_cases','media_incidents']
FIND={2023:[
'Росприроднадзор: опубликованный судебный текст подтверждает предписание Салавату №135-В от28.09.2023. Новостной первоисточник о26нарушениях ранее вернул403; закрытый реестр не считается прочитанным. Один объект не доказывает групповые итоги или отсутствие плана САКВ.',
'Ростехнадзор: судебный текст отражает контроль и новое предписание ООО Газпром сжиженный газ от10.07.2023. Иной субъект/метрика: это не опровержение экологических расходов, точного обещания или трех групповых счетчиков.',
'Судебная практика: А07-40790/2023 рассмотрен21.02.2024, касается предписания2023. Наличие экологических нарушений учтено как контекст; не заменяет юридический оригинал соглашения либо полный свод актов Группы.',
'СМИ/инциденты: выполнены запросы поГазпрому/Салавату2023. Встреченные эпизоды иных лет и отдельных объектов не сопоставимы с проверяемыми метриками; отсутствия всех аварий не утверждается.'
],2024:[
'Росприроднадзор: прочитан судебный текст по спору ООО Газпром инвест о предписаниях2024. Это экологический надзор, а не данные об изменении государственного пакета ПАО Газпром.',
'Ростехнадзор: выполнены адресные запросы2024; найдены споры промышленной безопасности отдельных обществ, не сведения об утрате РФ контроля над акциями. Полный реестр надзора не удостоверен.',
'Судебная практика: рассмотрен текст А19-21175/2024; экологические предписания не устанавливают долю акций на31.12.2024. Корпоративное раскрытие и новостной контекст не выданы за судебную фиксацию владения.',
'СМИ/инциденты: Интерфакс10.03.2024 сообщил о разгерметизации МГ Уренгой-Центр-1 со ссылками на предприятие, регион иМЧС. Эпизод безопасности не меняет показатель собственности.'
],2025:[
'Росприроднадзор: выполнен запрос поГазпрому2025; открытая выдача не дала сопоставимого предписания, опровергающего сам факт газификации мемориалов в проекте. Не утверждается отсутствие всех нарушений Группы.',
'Ростехнадзор: запросы2025 выявили материалы по опасным объектам отдельных газораспределительных обществ. Нет установленной связи этих актов с отрицанием проведения проекта; промышленная безопасность не смешивается с фактом его реализации.',
'Судебная практика: адресный поиск2025 поГазпрому и названию проекта не дал сопоставимого судебного опровержения его проведения. Найденные сторонние споры ПХГ/газовых сетей не удостоверяют безопасность всех мемориалов.',
'СМИ/инциденты: адресный запрос2025 с названием проекта не дал сопоставимого сообщения, отменяющего факт реализации. Репортажи с места6мая подтверждают событие, но не полноту годовых счетчиков189/80 и не отсутствие всех инцидентов.'
]}
def add_risks(p,year):
 j={2023:'16',2024:'17',2025:'18'}[year]
 refs={2023:'turn26search0,turn26search4,turn26search13',2024:'turn27search2,turn27search11',2025:'turn28search1,turn28search3,turn28search10'}[year]
 selected={2023:[R23,T23],2024:[R24,M24],2025:[]}[year]
 existing={s['id'] for s in p['sources']}
 for s in selected:
  if s['id'] not in existing:p['sources'].append(s)
 indexes=[]
 for idx,cat in enumerate(CATS):
  ids={2023:{0:['R23'],1:['T23'],2:['R23'],3:[]},2024:{0:['R24'],1:[],2:['R24'],3:['M24']},2025:{0:[],1:[],2:[],3:[]}}[year][idx]
  indexes.append([len(p['searches'])]);p['searches'].append(query(f'RISK_{year}_{cat}','contradiction',j,idx,refs,ids,FIND[year][idx],cat))
 # Actual follow-up requests retain their category and original time.
 extraidx={2023:0,2024:1,2025:2}[year]
 indexes[1].append(len(p['searches']));p['searches'].append(query(f'RISK_{year}_rost_followup','contradiction','19',extraidx,'turn29search0,turn29search2,turn29search11',[],FIND[year][1],'rost_enforcement'))
 if year==2023:
  indexes[3].append(len(p['searches']));p['searches'].append(query('RISK_2023_media_followup','contradiction','19',3,'turn29search16,turn29search19',[],FIND[year][3],'media_incidents'))
 p['risk_checks']=[dict(category=cat,search_indexes=indexes[idx],finding=FIND[year][idx],entity_scope=p['target']['entity']+'; релевантные объекты группы сопоставлены отдельно',period_scope=str(year)+'; дата публикации может быть позднее даты события и указана отдельно') for idx,cat in enumerate(CATS)]
 return p
