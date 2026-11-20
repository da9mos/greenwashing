"""Manually selected/typed semantic claims; mechanical exact-source binding only."""
import json,re,sys
from pathlib import Path
B=Path(__file__).resolve().parent
sys.path.insert(0,str(B.parent/'Агент'))
from extract_esg_v2 import prepare,validate

def run(rid,company,page_specs):
 report=B/'sources'/rid/'report.md';data,blocks=prepare(report,company,2023)
 coverage={c['block_id']:c for c in data['coverage']}
 def claim(block,start,end,kind,topic,reason,statement=None,secondary=None):
  text=block['text'];a=text.index(start);z=text.index(end,a)+len(end);quote=text[a:z]
  cid=f'{rid}-{len(data["claims"])+1:03d}'
  data['claims'].append({'id':cid,'type':kind,'type_reason':reason,'primary_topic':topic,'secondary_topics':secondary or [],'topic_reason':{'E':'Экологическое воздействие или природоохранные действия','S':'Работники, трудовые права и человеческий капитал','G':'Корпоративное управление и подотчётность'}[topic],'subtopic':{'E':'environmental_management','S':'own_workforce','G':'corporate_governance'}[topic],'statement':statement or quote,'source_kind':'text','status':'reviewed','evidence':[{'block_id':block['id'],'quote':quote,'role':'statement'}]})
  coverage[block['id']].update(status='extracted',reason='Смысловой просмотр указанного блока; заявления извлечены',claim_ids=coverage[block['id']]['claim_ids']+[cid])
 for page,specs in page_specs.items():
  pblocks=[b for b in blocks if b['page']==page]
  for block in pblocks:
   t=block['text']
   # Only clearly nonclaim metadata is excluded; difficult substantive blocks remain pending.
   if t.startswith(('#','<!--','- [Переход','<ul>','> Служебная')) or t.startswith('Отчет о социальной деятельности'):
    coverage[block['id']].update(status='excluded',reason='Заголовок, навигация или служебная метка; не самостоятельное заявление',claim_ids=[])
  for start,end,kind,topic,reason in specs:
   candidates=[b for b in pblocks if start in b['text'] and end in b['text']]
   if len(candidates)==1:
    claim(candidates[0],start,end,kind,topic,reason)
   else:
    a=next(i for i,b in enumerate(pblocks) if start in b['text'])
    z=next(i for i,b in enumerate(pblocks[a:],a) if end in b['text'])
    chosen=pblocks[a:z+1]; fragments=[]
    for i,b in enumerate(chosen):
     q=b['text'];q=q[q.index(start):] if i==0 else q;q=q[:q.index(end)+len(end)] if i==len(chosen)-1 else q
     fragments.append((b,q))
    # Bind first fragment, then extend evidence with the exact intervening blocks.
    b,q=fragments[0];claim(b,q,q,kind,topic,reason,statement=' '.join(q for _,q in fragments))
    c=data['claims'][-1]
    for b,q in fragments[1:]:
     c['evidence'].append({'block_id':b['id'],'quote':q,'role':'statement'})
     coverage[b['id']].update(status='extracted',reason='Фрагмент заявления, продолжающегося из соседнего блока',claim_ids=coverage[b['id']]['claim_ids']+[c['id']])
  for block in pblocks:
   if coverage[block['id']]['status']=='pending':coverage[block['id']]['reason']='Блок просмотрен; требует разбора контекста/структуры или проверки PDF; не исключён'
 # The pilot verifies individual claims, not exhaustive recovery within every block.
 for entry in data['coverage']:
  if entry['status']=='extracted':
   entry['status']='pending'
   entry['reason']='Заявления извлечены; полнота блока и независимый второй проход ещё не подтверждены'
 data['pilot_scope']={'pages_read':list(page_specs),'other_pages':'not read','full_page_extraction_confirmed':False,'human_gold':False,'pdf_checked':False}
 out=B/f'{rid}.dev.claims.json';out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');stats=validate(report,data);(B/f'{rid}.dev.validation.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n');print(rid,stats)

run('GAZP-2023-ОУР','Газпром',{37:[
('В Группе Газпром на первое место','труда.','декларация','S','Декларируемые приоритеты отношения к персоналу'),
('В Газпроме работают','трудовых династий.','результат','S','Сообщение о составе работников'),
('В Группе Газпром\nобщее количество','более 1 500.','результат','S','Сообщение о текущей структуре профессий'),
('Общий результат ее деятельности','на благо настоящих и будущих поколений.','декларация','S','Оценочное описание вклада работников'),
('Главная задача Группы Газпром','условиях.','декларация','S','Общая качественная цель формирования коллектива без конкретного мероприятия'),
('Для эффективного управления','организаций <sup>1</sup> .','результат','S','Сообщается о разработанной кадровой политике'),
('Ее главная цель','от инвестиций в персонал.','декларация','S','Общая цель политики'),
('Это достигается','работника.','результат','S','Заявленные действующие механизмы мотивации и оценки'),
('Группа Газпром постоянно совершенствует','Программа) <sup>2</sup> .','результат','S','Заявлен действующий процесс пересмотра кадровой программы'),
('Каждое из этих направлений включает','работы организаций Группы Газпром.','результат','S','Действующий ежегодный анализ показателей'),
('Группа Газпром стремится снизить','в развитии и обучении.','обязательство','S','Намерение снизить кадровые риски названными мерами; срок не указан'),
('В результате выполнения','печено удержание уровня рисков в приемлемом диапазоне.','результат','S','Заявлен полученный результат управления кадровыми рисками'),
('В Группе Газпром не допускается','с деловыми качествами работников.','декларация','S','Норма недискриминации без отдельного факта исполнения'),
('Все кадровые решения','качеств соискателей и работников.','результат','S','Утверждение о фактически применяемом процессе кадровых решений'),
('Группа Газпром соблюдает требования','отпуска.','результат','S','Проверяемое заявление о соблюдении трудовых требований'),
('Социальные льготы предоставляются','Федерации.','результат','S','Сообщение о текущем предоставлении льгот'),
('Работники организаций Группы Газпром','ПАО «Газпром».','результат','S','Заявлен доступный механизм защиты от дискриминации'),
('Равные права и возможности','(ГКД).','результат','S','Права закреплены в конкретном документе'),
]})
run('AKRN-2023-ОУР','Акрон',{16:[
('Реализация инициатив по сохранению','каждый год','обязательство','E','Конкретные ежегодные действия в блоке КПЭ стратегии 2027'),
],41:[
('Группа «Акрон» нацелена','тик корпоративного управления.','декларация','G','Общее намерение непрерывного развития'),
('Компания ежегодно проводит','РФ).','результат','G','Действующая ежегодная процедура оценки'),
('В\u00a02023\u00a0году полностью','полностью и\u00a016%\u00a0— частично).','результат','G','Сообщение о степени соблюдения рекомендаций'),
('В\u00a0наибольшей степени Обществом','него контроля.','результат','G','Заявление о соблюдении принципов управления'),
('В\u00a0меньшей степени','практиками управления делами.','результат','G','Ограничение соблюдения принципов совета директоров'),
('В\u00a0частности, неприменение','нии максимизации прибыли.','результат','G','Сообщение о неприменении положений и его причине'),
('В\u00a02024\u00a0году Компания планирует','тельством.','обязательство','G','План конкретных изменений внутренних документов'),
('На\u00a0конец 2023\u00a0года','от\u00a0общего числа директоров.','результат','G','Количество и независимость директоров'),
('Председатель Совета директо-','директором.','результат','G','Факт отсутствия независимости председателя'),
('Координацию деятельности','них документах Компании.','результат','G','Действующий механизм координации независимых директоров'),
('Оценка независимости членов','дениям.','результат','G','Действующий процесс оценки независимости'),
('Группа «Акрон» приветствует','членов Совета директоров.','декларация','G','Принцип разнообразия в составе органа управления'),
('Состав<br/>Совета директоров сбалансирован','ний и\u00a0деловых качеств его членов.','декларация','G','Оценочное утверждение о сбалансированности совета'),
]})
run('MAGN-2023-ИО','ММК',{66:[
('Совокупное потребление энергии в 2023 году','прошлого года.','результат','E','Указаны достигнутый уровень потребления и отрицательная динамика'),
('Значение доли закупаемой электроэнергии','4,44% в 2022 году).','результат','E','Текущая доля закупаемой энергии'),
('Группа осуществляет постепенный переход','собственными силами.','результат','E','Сообщение о реализуемом переходе к утилизации энергоресурсов'),
('Степень использования вторичных энергетических ресурсов','на 0,2% — по коксовому газу.','результат','E','Сообщение о снижении доли использования вторичных ресурсов'),
('При этом показатели вторичного использования','99,2% соответственно.','результат','E','Достигнутые доли повторного использования газов'),
('Запуск турбогенераторов','на май 2024 года.','обязательство','E','Конкретное планируемое действие со сроком'),
('Запуск кислородного блока','на середину 2025 года.','обязательство','E','План инфраструктуры в разделе собственной генерации; тематическая привязка требует проверки контекста'),
]})
# One structured quantitative table example, kept pending until PDF verification.
rid='MAGN-2023-ИО';report=B/'sources'/rid/'report.md';p=B/f'{rid}.dev.claims.json';data=json.loads(p.read_text());_,blocks=prepare(report,'ММК',2023)
page=[b for b in blocks if b['page']==66];header=next(b for b in page if 'Совокупное энергопотребление по Группе' in b['text']);table=next(b for b in page if '<table>' in b['text'] and 'Потребление невозобновляемых ТЭР' in b['text'])
cid=rid+'-008';ev=[]
for block,quote,role in [(header,'Группе ММК','subject'),(table,'Потребление невозобновляемых ТЭР','metric'),(table,'329,51','value'),(header,'млн ГДж','unit'),(table,'2023','period')]:ev.append({'block_id':block['id'],'quote':quote,'role':role})
data['claims'].append({'id':cid,'type':'результат','type_reason':'Значение фактического потребления за отчётный год','primary_topic':'E','secondary_topics':[],'topic_reason':'Энергопотребление','subtopic':'energy','statement':'Группа ММК: потребление невозобновляемых ТЭР в 2023 году — 329,51 млн ГДж.','source_kind':'table','quantitative':True,'status':'pending','review_reason':'Роли подтверждены в MD; положение ячеек и исходную таблицу необходимо сверить с PDF','evidence':ev})
for entry in data['coverage']:
 if entry['block_id'] in {e['block_id'] for e in ev}:entry.update(status='pending',reason='Контекст количественной записи; требуется PDF-сверка',claim_ids=entry['claim_ids']+[cid])
# Reviewer disagreements are preserved rather than silently resolved.
for item in data['claims']:
 if item['id'].endswith('-007'):item.update(status='pending',review_reason='Проверить ESG-релевантность промышленной инфраструктуры и разделить два разных срока')
p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');(B/f'{rid}.dev.validation.json').write_text(json.dumps(validate(report,data),ensure_ascii=False,indent=2)+'\n')
for rid,ids in [('GAZP-2023-ОУР',[5,8,13]),('AKRN-2023-ОУР',[13])]:
 p=B/f'{rid}.dev.claims.json';data=json.loads(p.read_text())
 for c in data['claims']:
  if int(c['id'].rsplit('-',1)[1]) in ids:c.update(status='pending',review_reason='Независимый проверяющий отметил границу типа или основной/дополнительной темы; требуется арбитраж по codebook')
 p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');(B/f'{rid}.dev.validation.json').write_text(json.dumps(validate(B/'sources'/rid/'report.md',data),ensure_ascii=False,indent=2)+'\n')
