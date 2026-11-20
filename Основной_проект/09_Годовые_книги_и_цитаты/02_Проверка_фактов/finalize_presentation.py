"""Editorial revision only; retain original sources and actual search timestamps."""
import copy
from datetime import datetime
from zoneinfo import ZoneInfo
from research_common import *
import sys
sys.path.insert(0,str(D.parent.parent/'03_Фактчекинг/Агент'));import factcheck
p=D/'presentation.json';v=json.loads(p.read_text()); plan=factcheck.load(D/'run')
reasons={
1:'Коммерсантъ и Совет Салавата: соглашение предусматривает САКВ и развитие мониторинга. Дело А07-40790/2023: предписание Росприроднадзора Салавату №135-В от 28.09.2023 касается выбросов. Вывод: этот надзорный факт не удостоверяет точный пункт о плане САКВ или его исполнение; доступного оригинала соглашения нет.',
2:'Коммерсантъ и Совет Салавата: подтверждают соглашение и задачи САКВ. Дело А07-40790/2023: предписание Росприроднадзора №135-В от 28.09.2023 не удостоверяет обязанность представить количество источников. Вывод: точный пункт соглашения не установлен; «до 2025 г.» относится к оснащению, а не к сроку представления сведений.',
6:'Газпром, отчёт за 2023 год: проведена 761 проверка. Дело А07-40790/2023: предписание Росприроднадзора Салавату №135-В от 28.09.2023 подтверждает отдельный надзорный эпизод. Вывод: это один объект, не полный перечень проверок Группы; независимого подтверждения общего итога нет.',
7:'Газпром, отчёт за 2023 год: выявлено 517 нарушений. Дело А07-40790/2023: предписание Росприроднадзора Салавату №135-В от 28.09.2023 относится к отдельному объекту. Вывод: судебный факт учтён, но групповой итог 517 им не подтверждается и не опровергается.',
8:'Газпром, отчёт за 2023 год: 563 проверки завершились без нарушений. Дело А07-40790/2023: предписание Росприроднадзора Салавату №135-В от 28.09.2023 касается одного объекта. Вывод: это не полный перечень Группы; независимого подтверждения 563 проверок нет, а 517 нарушений имеют другую единицу учёта.'}
for n,row in enumerate(v['rows'],1):
 if n in reasons:
  row['short_reason']=reasons[n]
  if not any(s['url']==R23['url'] for s in row['sources']):row['sources'].append(dict(name='Арбитражный суд Республики Башкортостан, дело А07-40790/2023 (копия решения)',url=R23['url'],assertion='Суд рассматривает предписание Росприроднадзора Салавату №135-В от28.09.2023; это отдельный надзорный эпизод, не полный перечень Группы и не оригинал соглашения.',access='excerpt',independence='independent'))
 previous=D/f'run/results/C{n:06}.r000002.json';packet=copy.deepcopy(json.loads(previous.read_text()));packet.update(revision=3,checked_at=datetime.now(ZoneInfo('Asia/Yekaterinburg')).isoformat(),reason=row['short_reason'])
 for a in packet['aspects']:a['reason']=row['short_reason']
 packet['presentation_revision_parent_sha256']=sha(previous);packet['presentation_revision_note']='Краткое объяснение согласовано с уже прочитанными судебными фактами и четырьмя risk_checks. Запросы и даты не изменены; новых поисков в этой редактуре нет.'
 out=D/f'responses/C{n:06}.r000003.json';write(out,packet);factcheck.validate(packet,plan);factcheck.ingest(D/'run',out)
 row.update(record_path=f'run/results/C{n:06}.r000003.json',assessment_path=f'run/results/C{n:06}.r000003.json',assessment_export_path='export_r3/claims.json',assessment_revision=3)
 assert len(row['short_reason'])<=900
write(p,v);summary=factcheck.export(D/'run',D/'export_r3');write(D/'attempts/r3_export_summary.json',summary)
print(summary)
