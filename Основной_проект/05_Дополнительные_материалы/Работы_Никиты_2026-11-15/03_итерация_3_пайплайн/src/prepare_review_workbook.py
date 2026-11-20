from pathlib import Path
import csv,json,re
P=Path(__file__).resolve().parents[1]
def read(p):
    with p.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f,delimiter=';'))
S=[]
def present(v):
 if isinstance(v,str) and v.startswith('['):
  try:
   x=json.loads(v)
   if isinstance(x,list) and all(isinstance(t,str) for t in x):return '\n'.join('• '+t for t in x)
  except ValueError:pass
 return v

def add(name,rows,cols,widths=None):
    S.append({'name':name,'headers':[v for k,v in cols],'rows':[[present(r.get(k)) if r.get(k) not in ('',None) else None for k,v in cols]for r in rows],'widths':widths or {}})
base=P/'data/out'
review=P/'data/review_v2'
dynamic=read(review/'metrics_dynamics.csv' if (review/'metrics_dynamics.csv').exists()else base/'metrics_dynamics.csv')
targets=read(base/'targets.csv');td={r['target_id']:r for r in targets}
categories={'comparable_result_found':'Найден сопоставимый результат','explicit_achievement_statement':'Отчёт прямо подтверждает выполнение','explicit_data_perimeter_revision':'Изменены данные или периметр','explicit_deadline_change':'Официально изменён срок','perimeter_mismatch':'Разный периметр','carried_forward_measurement':'Последний опрос другого года','early_achievement_and_perimeter_mismatch':'Ранний результат; другой периметр','early_achievement_and_metric_mismatch':'Ранний результат; другая метрика','perimeter_exclusion':'Исключение части активов','missing_cumulative_same_scope_metric':'Нет накопленного итога в нужном периметре','metric_definition_unclear':'Не установлена эквивалентность метрик','missing_target_specific_result':'Нет результата по целевой метрике','missing_project_specific_cumulative_amount':'Нет накопленной суммы по проекту','missing_new_projects_denominator':'Нет знаменателя по новым проектам','carried_forward_measurement_officially_adopted':'Официально принят последний замер','target_achieved':'Подтверждено','target_not_achieved':'Не достигнута','target_or_scope_changed':'Изменение цели или периметра'}
for r in dynamic:
 r['reason_category']=categories.get(r.get('reason_category'),r.get('reason_category',''))
 r['source_url']=td[r['target_id']]['source_url']
 for k in ['base_year','base_value','target_value','target_year','value_2023','value_2024','value_2025']:
  try:r[k]=float(r[k])if r.get(k) not in ['',None]else None
  except ValueError:pass
S.append({'name':'Обзор','headers':['Показатель','Значение','Пояснение'],'rows':[
 ['Компаний',30,'Корпус отчётов 2023–2025'],['Отчётов',92,'Ссылки на оригиналы в реестре'],['Заявлений',None,'Извлечённые заявления; статус проверки указан отдельно'],['Проверяемых целей',None,'Цели из отчётов 2023 года'],['Выполнены',None,'Статусы достижения целей, не вердикт о гринвошинге'],['Не выполнены',None,'Невыполнение не доказывает недостоверность коммуникации'],['Нет однозначного итога',None,'Показатели найдены частично; причина сопоставимости указана для каждой цели']], 'widths':{0:30,1:16,2:70},'formulas':{'B4':"=COUNTA('Заявления'!A2:A975)",'B5':f"=COUNTA('Динамика'!A2:A{len(dynamic)+1})",'B6':f'=COUNTIFS(\'Динамика\'!D2:D{len(dynamic)+1},"выполнена")','B7':f'=COUNTIFS(\'Динамика\'!D2:D{len(dynamic)+1},"не выполнена")','B8':f'=COUNTIFS(\'Динамика\'!D2:D{len(dynamic)+1},"нет данных")'}})
for r in dynamic:
 if r.get('target_upper_bound'):r['target_display']=str(r['target_value']).removesuffix('.0')+'–'+r['target_upper_bound']
 else:r['target_display']=r['target_value']
add('Динамика',dynamic,[('target_id','Цель ID'),('company_id','Компания'),('metric','Показатель'),('status','Статус исходной цели'),('target_display','Цель'),('unit','Единица'),('target_year','Срок'),('value_2023','2023'),('value_2024','2024'),('value_2025','2025'),('comparison_operator','Правило сравнения'),('base_year','Базовый год'),('base_value','База'),('comment','Обоснование'),('source_url','Отчёт цели'),('old_status','Исходный статус v1'),('assessment_year','Год оценки'),('measurement_year','Год последнего замера'),('restated','Изменения базы / данных'),('esg_block','Блок'),('claim_id_commitment','Заявление ID'),('review_status','Проверка')],{0:18,1:13,2:45,3:24,4:14,5:30,10:32,13:90,14:55,18:80})
audit_file=P/'data/review_v3/comparison_audit.csv'
if audit_file.exists():
 add('Сопоставления',read(audit_file),[('target_id','Цель ID'),('company_id','Компания'),('status_before','До проверки v3'),('status_after','После проверки v3'),('audit_status','Проверка'),('metric_check','Показатель'),('unit_check','Единица'),('base_check','База'),('period_check','Период'),('scope_check','Периметр'),('operator_check','Правило'),('conclusion','Вывод и исправления'),('sources','Источники')],{0:18,1:13,2:23,3:23,4:30,5:65,6:35,7:60,8:50,9:65,10:40,11:90,12:70})

claims=read(base/'claims.csv')+read(base/'claims_dynamics_additions.csv')
for c in claims:c['verification']='нет операционального критерия' if c['type']=='декларация' else 'требует проверки доказательств'
add('Заявления',claims,[('claim_id','Заявление ID'),('company_id','Компания'),('year','Год'),('type','Тип'),('esg_block','Блок'),('text','Точная цитата'),('report_id','Отчёт'),('page','Страница'),('source_url','Источник'),('review_status','Проверка цитаты'),('verification','Проверка утверждения')],{5:95,8:55,9:40,10:40})
companies=read(base/'companies_review.csv')
for c in companies:
 rs=[r for r in dynamic if r['company_id']==c['company_id']]
 c.update(goal_count=len(rs),fulfilled=sum(r['status']=='выполнена' for r in rs),failed=sum(r['status']=='не выполнена' for r in rs),changed=sum(r['status']=='изменена' for r in rs),unresolved=sum(r['status'] in ('нет данных','несопоставимая база') for r in rs),reviewed=sum(r.get('review_status')=='завершена' for r in rs))
 c['coverage_note']='Цели ещё не извлечены в таблицу динамики; не означает отсутствие целей в отчётах.' if not rs else 'Статусы относятся только к выбранным целям. Полнота покрытия заявлений компании не подтверждена.'
add('Компании',companies,[('company_id','Компания ID'),('company','Название'),('years_available','Годы отчётов'),('goal_count','Целей'),('fulfilled','Выполнены'),('failed','Не выполнены'),('changed','Изменены'),('unresolved','Требуют уточнения'),('reviewed','Повторно проверены'),('coverage_note','Границы вывода')],{1:40,2:25,9:85})
ev=read(P/'data/nikita/dynamics_evidence.csv')
for e in ev:e['kind']={'esg_table_two_years':'Таблица за два года','numeric_deadline_goal':'Измеримая цель со сроком','commitment':'Обязательство','observation':'Результат','observation_not_comparable':'Несопоставимое наблюдение','base':'База'}.get(e['kind'],e['kind'])
add('Доказательства',ev,[('target_id','Цель ID'),('company_id','Компания'),('kind','Роль источника'),('year','Год показателя'),('report_id','Отчёт'),('page','Страница'),('value','Значение'),('quote','Точная цитата'),('source_url','Источник')],{2:32,7:100,8:55})
if (review/'evidence_review.csv').exists():
 a=read(review/'evidence_review.csv')
 for e in a:
  e['found_value']=e.get('value') or e.get('reported_value') or ('Расчёт: '+e['derived_value'] if e.get('derived_value') else '')
  e['comparison_display']='Пересмотрено в v3' if e.get('superseded_by') else ('Да' if e.get('comparison_valid')=='True' else 'Нет / только контекст')
 add('Новые доказательства',a,[('target_id','Цель ID'),('company_id','Компания'),('year','Год'),('found_value','Найденное значение'),('comparison_display','Сопоставимо'),('quote','Точная цитата'),('report_id','Отчёт'),('page','Страница'),('source_url','Источник'),('formula','Расчёт'),('note','Примечание'),('quote_check','Проверка цитаты'),('review_version','Версия проверки'),('superseded_by','Заменено проверкой')],{3:45,4:30,5:100,8:65,9:30,10:65})
if (review/'review_log.csv').exists():
 log=read(review/'review_log.csv')
 for row in log:
  row['reason_category']=categories.get(row.get('reason_category'),row.get('reason_category',''))
  try:
   detail=json.loads(row['search_log'])
   if isinstance(detail,list):row['search_log']='\n'.join(f"{q.get('report_id','')}: {q.get('pages_scanned',q.get('page',''))} стр.; {q.get('source_type',q.get('method',''))} {q.get('source_url','')}" for q in detail)
   elif isinstance(detail,dict):row['search_log']='\n'.join(f'{k}: {v} стр.' for k,v in detail.items())
  except ValueError:pass
 add('Повторная проверка',log,[('target_id','Цель ID'),('review_status','Проверка'),('reason_category','Причина'),('reason','Вывод'),('source_observations','Новых доказательств'),('search_log','Журнал поиска')],{2:35,3:100,5:90})
ext=review/'external_facts_verified.csv'
if ext.exists():
 a=read(ext)
 if a:
  for e in a:
   if e['fact_id']=='F-SHLZ-001':e['description']='НЕ ПОДТВЕРЖДЕНО; вне периода 2023–2025. Исходная запись: '+e['description']
  names={'fact_id':'Факт ID','company_id':'Компания','company':'Компания','date':'Дата','source_type':'Тип источника','source_url':'Источник','quote':'Цитата','description':'Событие','claim_id':'Связь с заявлением','verification_status':'Проверка','limitations':'Ограничения'}
  add('Внешние факты',a,[('fact_id','Факт ID'),('company_id','Компания'),('legal_entity','Юридическое лицо'),('event_date','Дата события'),('event_type','Тип события'),('description','Содержание'),('procedural_status','Статус производства'),('independence','Независимость'),('verification_status','Проверка'),('source_url','Источник'),('linked_claim_ids','Связанные заявления'),('relation_type','Характер связи'),('limitations','Ограничения'),('quote','Цитата')],{2:40,5:80,6:40,7:35,8:45,9:60,12:85,13:90})
add('Пробелы',read(P/'data/nikita/coverage_gaps.csv'),[('company_id','Компания ID'),('company','Компания'),('targets_found','Целей'),('sg_targets','Целей S/G'),('missing_to_planned_three','До плановых трёх'),('next_action','Следующее действие'),('limitations','Ограничения')],{1:38,5:70,6:80})
reports=read(P.parent/'01_итерация_1_сбор_данных/выборка_30/reports.csv')
for r in reports:r['url']='https://drive.google.com/file/d/'+r['drive_id']+'/view' if r.get('drive_id')else r.get('url','')
add('Отчёты',reports,[('report_id','Отчёт ID'),('company_id','Компания'),('year','Год'),('url','Оригинал на Google Диске')],{0:30,3:70})
gf=review/'gold_flags_review.csv'
if gf.exists():
 a=read(gf)
 if a:add('Проверка разметки',a,[('sentence_id','Фрагмент ID'),('flag','Сигнал'),('decision','Решение'),('category','Категория'),('rationale','Обоснование'),('sentence','Исходный текст'),('gold_modified','Эталон изменён'),('review_method','Метод проверки')],{0:35,1:38,2:36,3:35,4:85,5:95,7:45})
add('Аудит команды',[
 {'part':'Корпус / Григорий','result':'30 компаний, 92 отчёта, реестр оригиналов','state':'Реестр собран; достаточность доказательств проверяется для каждого утверждения'},
 {'part':'Методика / Григорий','result':'Кодбук v4 и методика итерации 2','state':'Разделены тип заявления, достижение цели и риск гринвошинга; согласование с заказчиком не подтверждено'},
 {'part':'Извлечение / Георгий','result':'928 исходных заявлений; повторная сборка совпала по хешам','state':'Исправлено ложное падение сравнения float; числовые поля исходных 928 требуют отдельного наполнения'},
 {'part':'Выборка и динамика / Никита','result':'49 сопоставлений проверены в v3; 164 записи доказательств; 40 тестов','state':'Исправлены единицы, годы измерений и смысловые сравнения; рейтинг компаний не валидирован'},
 {'part':'Внешние факты / Егор К.','result':'Проверены исходные 7 строк, добавлены 6 событий','state':'Удалены 3 ошибочные связи; ограничения доступа и периода явно указаны'},
 {'part':'Эталон / Егор Д. и Григорий','result':'811 предложений, 465 заявлений; 76 флагов разобраны: 73 сняты, 3 открыты','state':'150 примеров с двумя независимыми людьми и согласованность ещё не подтверждены'},
 {'part':'Итоговый рейтинг','result':'Нет валидированного индекса риска на все компании','state':'Нельзя ранжировать компании по доле невыполненных целей или по отсутствию данных'}], [('part','Участок и ответственный'),('result','Что есть'),('state','Проверка и границы')],{0:35,1:75,2:100})
add('Методика',[
 {'rule':'Объект оценки','meaning':'Конкретное ESG-заявление компании. Статус достижения цели и риск недостоверной коммуникации оцениваются отдельно.'},
 {'rule':'Сопоставимость','meaning':'Совпадают показатель, единицы, база, период и периметр. Изменения фиксируются явно.'},
 {'rule':'Будущий срок','meaning':'До наступления срока цель не считается невыполненной.'},
 {'rule':'Недостигнутая цель','meaning':'Открытое признание неудачи не является доказательством гринвошинга.'},
 {'rule':'Внешнее событие','meaning':'Судебный иск, предписание, штраф и отмена решения различаются. Проверяется конкретное юрлицо и статус события.'},
 {'rule':'Отсутствие находок','meaning':'Означает результат поиска, не отсутствие нарушения. Для каждого пропуска нужен журнал поиска.'},
 {'rule':'Нуль и пропуск','meaning':'0 — найденное нулевое значение. Пусто — сопоставимое значение не установлено; причина указана в динамике и сопоставлениях.'},
 {'rule':'Парк и новые установки','meaning':'Накопленное количество оборудования не равно количеству новых установок за год.'},
 {'rule':'Изменение базы цели','meaning':'Перенос базового года сам по себе не делает текущий показатель несопоставимым. Исходный и пересмотренный пороги проверяются отдельно.'},
 {'rule':'Повторная сборка','meaning':'Готовые ответы моделей пересобираются без API. Цитаты сверяются с исходной страницей; смысл проверяется отдельно.'}], [('rule','Правило'),('meaning','Применение')],{0:30,1:110})
S[0]['rows'].append(['Изменена база / цель',None,'Документированное изменение; не считается выполнением или провалом'])
S[0]['formulas']['B9']=f'=COUNTIFS(\'Динамика\'!D2:D{len(dynamic)+1},"изменена")'
S[0]['rows'].append(['Несопоставимая база',None,'Числа найдены, но база сравнения изменилась'])
S[0]['formulas']['B10']=f'=COUNTIFS(\'Динамика\'!D2:D{len(dynamic)+1},"несопоставимая база")'
S[0]['rows'].append(['Что оцениваем','Заявления и цели','Проверяем конкретную цитату по отчётам и внешним фактам. Рейтинг компаний пока не валидирован.'])
(P/'outputs/review_v3').mkdir(parents=True,exist_ok=True)
out={'out':str(P/'outputs/review_v3'),'sheets':S}
for s in S:
 s['rows']=[[''.join(c for c in v if c in '\t\n\r' or 32<=ord(c)<=55295 or 57344<=ord(c)<=65533 or 65536<=ord(c)<=1114111) if isinstance(v,str) else v for v in row] for row in s['rows']]
(P/'outputs/review_v3/workbook_input.json').write_text(json.dumps(out,ensure_ascii=False))
print([(s['name'],len(s['rows']))for s in S])
