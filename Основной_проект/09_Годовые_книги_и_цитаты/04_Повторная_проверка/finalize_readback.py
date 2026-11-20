"""Typography/readback revision; preserves all earlier accepted packets."""
from pathlib import Path
import json,hashlib,subprocess,sys
from datetime import datetime
from zoneinfo import ZoneInfo
D=Path(__file__).resolve().parent;CORE=D.parent.parent/'03_Фактчекинг/Агент/factcheck.py'
def read(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
j=read(D/'presentation.json'); reasons=[
'Выбор, сообщение пресс-службы Салавата от 13.04.2023: обещаны снижение выбросов, план САКВ и сведения об источниках, оснащаемых до 2025 г. Это объявленные обязательства, а не сообщение об их исполнении.',
'Газпром, сравнительная таблица ОСД за 2023 год: 96 232,61 млн руб. против 89 138,75 млн руб. в 2022 году. Это 96,23 млрд руб. и рост 8,0% после округления.',
'Экологическая политика Газпрома закрепляет сохранение благоприятной среды, ресурсосбережение и биоразнообразие в обязательствах компании. Реестр документов за 2023 год подтверждает действие этой политики.',
'Газпром сообщает 761 проверку, 517 нарушений и 563 проверки без нарушений. Дело А07-40790/2023 подтверждает предписание РПН Салавату № 135-В от 28.09.2023, но открытого свода для проверки трёх итогов всей Группы нет.',
'Финансовый отчёт за 2024 год: смешанная российская собственность с федеральной долей. Интерфакс и годовой отчёт: РФ — 38,37%, Роснефтегаз — 10,97%, Росгазификация — 0,89%; вместе под контролем РФ — 50,23%.',
'Интерфакс, репортаж от 6 мая 2025 года: специалисты Газпрома подключали мемориалы к сетевому газу в проекте «Храним огонь Победы». Телеканал Санкт-Петербург также сообщает о газификации мемориальных комплексов в рамках проекта.'
]
assertions=[
['Пресс-служба предприятия объявила снижение выбросов, разработку плана САКВ для объектов I категории и предоставление сведений об оснащаемых источниках.'],
['Расходы 2023 года — 96 232,61 млн руб., 2022 года — 89 138,75 млн руб.; раскрыт рост 8,0%.'],
['Политика закрепляет сохранение благоприятной среды, ресурсосбережение и биоразнообразие как обязательства компании.','В реестре за 2023 год указана действующая Экологическая политика, постановление от 25.05.2015 № 21, без изменений в 2023 году.'],
['Исходный отчёт содержит 761 проверку, 517 нарушений и 563 проверки без выявленных нарушений; отдельный групповой свод не найден.','Предписание РПН Салавату № 135-В от 28.09.2023; отдельный эпизод, не групповой свод.'],
['Прямой пакет РФ — 38,37%; через Роснефтегаз — 10,97%, через Росгазификацию — 0,89%.','Структура капитала и сноска раскрывают 50,23% прямого и косвенного контроля РФ.','Форма собственности: смешанная российская с долей федеральной собственности.'],
['Собственный корреспондент сообщает о проекте и подключении мемориалов специалистами Газпрома к сетевому природному газу.','Авторский репортаж подтверждает проведение проекта и газификацию мемориальных комплексов.']
]
transcript=read(D/'cli_transcript.json')
def cli(*args):
 r=subprocess.run([sys.executable,str(CORE),*map(str,args)],capture_output=True,text=True);transcript.append(dict(args=list(map(str,args)),returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));write(D/'cli_transcript.json',transcript)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
for i,r in enumerate(j['rows']):
 old=D/r['assessment_path'];p=read(old);p.update(revision=2,reason=reasons[i],checked_at=datetime.now(ZoneInfo('Asia/Yekaterinburg')).isoformat());q=old.parent.parent.parent/'responses'/f"{p['claim_id']}.r000002.json";write(q,p);cli('ingest',old.parent.parent,q)
 rel=str((old.parent/f"{p['claim_id']}.r000002.json").relative_to(D));r.update(short_reason=reasons[i],assessment_path=rel,record_path=rel,export_path=str(Path(str(r['year']))/'export_r2/claims.json'))
 for s,assertion in zip(r['sources'],assertions[i]):s['assertion']=assertion
for year in [2023,2024,2025]:cli('check',D/str(year)/'run');cli('export',D/str(year)/'run',D/str(year)/'export_r2')
write(D/'presentation.json',j)
checks=[]
for r in j['rows']:
 p=D/r['record_path'];a=read(p);assert a['quote']==r['exact_quote'];assert a['reason']==r['short_reason'];assert len(a['risk_checks'])==4;assert p.with_suffix('.sha256').read_text()==hashlib.sha256(p.read_bytes()).hexdigest();assert 'Вывод:' not in r['short_reason'];assert len(r['short_reason'])<900
 for e in a['evidence']:
  s=next(x for x in a['sources'] if x['id']==e['source_id']);assert e['quote'] in s['content'];assert hashlib.sha256(s['content'].encode()).hexdigest()==s['content_sha256']
 checks.append(dict(quote_id=r['quote_id'],record_path=r['record_path'],quote_exact=True,assessment_reason_equal=True,risk_categories=[x['category'] for x in a['risk_checks']],packet_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),verdict=a['verdict'],aspects=len(a['aspects'])))
write(D/'final_readback.json',dict(rows=checks,arithmetic=dict(control_sum=38.37+10.97+0.89,expense_growth=(96232.61/89138.75-1)*100),scope='6 selected complete quotations only; not annual completeness'))
(D/'audit.md').write_text('''# Повторная проверка выбранных цитат\n\nПроектный FACT_CHECK_AGENT: шесть полных исходных цитат, прежние десять атомов сохранены в metadata. Пять строк true; одна insufficient_evidence (761/517/563). Всего 14 существенных пропозиций: 3+2+2+3+2+2. Это не полная проверка годовых отчётов.\n\nРеальные новые запросы и чтения сохранены в journal. Риск-проверки по четырём категориям переиспользованы для неизменных entity/period с исходными поисковыми датами, refs и indexes. Родительские пакеты и журналы указаны с SHA в provenance. Их результаты не выданы за новые запросы.\n\nВсе три run прошли штатные prepare, next, ingest, check, export. Первые принятые пакеты r1 сохранены; r2 улучшает краткие пользовательские объяснения без изменения доказательств и вердиктов. Текущие экспорты: 2023/export_r2, 2024/export_r2, 2025/export_r2. final_readback.json проверяет SHA, точные цитаты, совпадение причин и четыре risk_checks.\n\nСобственность: официальный финансовый отчёт раскрывает смешанную российскую форму; годовой отчёт — структуру и механизм контроля, Интерфакс — доли2024. Прямое владение38,37% не подменяет прямой+косвенный контроль50,23%. Дополнительное условие именно31.12 отсутствует в target.\n\nРасходы: отдельная сравнительная статистическая таблица другого отчёта содержит компоненты, итог96 232,61млн и базу89 138,75млн. Это корпоративная запись по компетенции, не независимый аудит.\n\nОбязательства: свежий поиск фактически вернул развёрнутый кэшированный текст статьи с прямой атрибуцией пресс-службе. Указан excerpt и прямой403, а не притворное чтение оригинального URL. Подтверждено публичное объявление трёх обязательств, не юридическая полнота и не исполнение.\n\nПринцип: отдельный воспроизведённый нормативный текст политики и реестр применимых документов2023. Проверяется документально закреплённый принцип, не соответствие всех операций политике. Надзорный контекст сохранён.\n\nСчётчики: исходная фраза не использована как доказательство самой себя. Судебное предписание отдельному обществу не сверяет полный групповой итог; поэтому неопределённость сохранена.\n\n2025: авторские репортажи с мероприятия подтверждают реализацию и газификацию мемориалов. Цитата содержит полное первое предложение, годовые189/80 в проверяемый текст не включены.\n''')
print('Readback OK:6rows;5true+1insufficient;immutable r1+r2;14aspects;24riskchecks')
