"""Derive atomic assessments from accepted real-research packets; performs no searches."""
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

D = Path(__file__).resolve().parent
if (D / 'atomic_run').exists():
    raise SystemExit('Atomic run already exists; use a new run for a new derivation. Accepted history must not be overwritten.')
PROJECT = D.parent.parent
FACT = PROJECT / '03_Фактчекинг/Агент'
import sys
sys.path.insert(0, str(FACT))
import factcheck


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


review_path = D.parent / '02_ESG/classification_review.json'
review = json.loads(review_path.read_text())
parents = {n: json.loads((D / f'run/results/C{n:06}.r000001.json').read_text()) for n in range(1, 5)}
# Exact mappings from the project ESG review's atomic parts to already researched aspects.
map_parts = {
    '001-a': (1, ['A1'], ['E1', 'E2']),
    '001-b': (1, ['A2'], ['E1']),
    '002-a': (2, ['A1'], ['E1', 'E2']),
    '002-b': (2, ['A2'], ['E1', 'E2']),
    '003-a': (3, ['A1', 'A2'], ['E1']),
    '004-a': (4, ['A1'], ['E1']),
    '004-b': (4, ['A2'], ['E1']),
    '004-c': (4, ['A3'], ['E1']),
}
scopes = {
 '001-a': ('апрель 2023 — принятие обязательства; срок разработки плана в цитате не установлен', 'Эксплуатируемые объекты НВОС I категории ООО «Газпром нефтехим Салават»'),
 '001-b': ('апрель 2023 — принятие обязательства; срок представления сведений не установлен; до 2025 г. относится к планируемому оснащению', 'Стационарные источники ООО «Газпром нефтехим Салават», планируемые к оснащению САКВ; полный перечень не установлен'),
 '002-a': ('2023', 'Общие расходы Группы Газпром на охрану окружающей среды в Российской Федерации'),
 '002-b': ('2023 относительно 2022', 'Общие расходы Группы Газпром на охрану окружающей среды в Российской Федерации'),
 '003-a': ('В самой декларации срок не указан; размещена в отчете за 2023 г.', 'Сохранение окружающей среды и природных богатств нашей страны; перечень операций не задан'),
 '004-a': ('2023', 'Объекты Группы Газпром; государственные проверки ООС и природопользования; география не сужена до РФ'),
 '004-b': ('2023', 'Нарушения, выявленные описанными государственными проверками на объектах Группы Газпром; география отдельно не задана'),
 '004-c': ('2023', 'Описанные государственные проверки объектов Группы Газпром без выявленных нарушений; география отдельно не задана'),
}
reasons = {
 '001-a': 'Исследуется принятие обязанности подготовить план, не установка САКВ. Прочитаны сведения о соглашении и официальный комментарий, но юридический оригинал с обязанностью, объектами I категории и приложениями не прочитан. Подходящего независимого подтверждения или опровержения этого точного обязательства недостаточно.',
 '001-b': 'Исследуется принятие обязанности представить сведения о количестве источников, не фактическая установка оборудования. В прочитанных внешних материалах нет точного подтверждения или опровержения этой обязанности. «До 2025 г.» относится к планируемому оснащению; срок представления сведений не установлен.',
 '002-a': 'Корпоративная ретроспектива сообщает 96 232,61 млн руб. за 2023 г., что согласуется с 96,23 млрд руб. после округления. Независимая сопоставимая проверка именно суммы общих расходов в РФ не получена. Это не вывод о ложности суммы.',
 '002-b': 'Рост (96 232,61 / 89 138,75 − 1) × 100 = 7,958223…%, что согласуется с 8,0% после округления. Исходные суммы корпоративные, независимо не удостоверены. Проверяется относительный рост, не процентные пункты и не экологический эффект.',
 '003-a': 'Формулировка задает принцип, без измеримого порога, периода результата и операционного периметра. Наличие политики не удостоверяет достигнутый эффект, а отдельное нарушение не превращает общий принцип в бинарно ложный. Оба направления поиска выполнены ранее; это not_verifiable, не гринвошинг.',
 '004-a': '761 — число государственных экологических проверок объектов Группы за 2023 г. Прочитан корпоративный итог, но независимый полный реестр с тем же составом группы, годом и видами надзора не получен. Не подменено суммой нарушений.',
 '004-b': '517 — число выявленных нарушений, не число проверок с нарушениями. Прочитан корпоративный итог; независимая консолидированная совокупность актов в том же периметре не получена. Отдельные 26 нарушений Салавата не устанавливают и не опровергают этот групповой итог.',
 '004-c': '563 — число проверок без выявленных нарушений, не число объектов и не утверждение об отсутствии всех нарушений Группы. Независимый полный перечень результатов проверок не получен. 517 нарушений нельзя складывать с 563 проверками как однородные меры.',
}
propositions = {'001-a': 'ООО «Газпром нефтехим Салават» приняло обязательство разработать план создания САКВ на эксплуатируемых объектах I категории.', '001-b': 'ООО «Газпром нефтехим Салават» приняло обязательство представить сведения о количестве стационарных источников, планируемых к оснащению САКВ до 2025 г.; срок представления не установлен.', '002-a': 'Общие расходы Группы Газпром на охрану окружающей среды в Российской Федерации в 2023 г. составили 96,23 млрд руб.', '002-b': 'Общие расходы Группы Газпром на охрану окружающей среды в Российской Федерации в 2023 г. увеличились на 8,0% относительно 2022 г.', '003-a': 'Сохранение благоприятной окружающей среды и природных богатств нашей страны является одним из главных принципов работы Газпрома.', '004-a': 'В 2023 г. государственные надзорные органы провели 761 проверку требований ООС и природопользования на объектах Группы Газпром.', '004-b': 'В результате описанных государственных проверок объектов Группы Газпром в 2023 г. выявлено 517 нарушений.', '004-c': 'По результатам 563 описанных государственных проверок объектов Группы Газпром в 2023 г. нарушений выявлено не было.'}
rows = []
origins = []
for original in review['rows']:
    for part in original['recommended_atomic_parts']:
        pid = part['part_id']
        parent_number, aspect_ids, evidence_ids = map_parts[pid]
        parent = parents[parent_number]
        assert original['quote'] == parent['quote']
        fragments = part['quote_fragments']
        assert all(fragment in original['quote'] for fragment in fragments)
        statement = ' '.join(fragments)
        period, boundary = scopes[pid]
        row = {
            'id': 'GAZP-2023-ATOMIC-' + pid,
            'statement': statement, 'quote': statement,
            'type': part['type'], 'claim_type': part['type'], 'block': 'E',
            'pdf_page': original['source']['pdf_page'],
            'entity_scope': part.get('entity_scope', original['entity_scope']),
            'period': period, 'boundary': boundary,
            'topic': part['topic'], 'source_quote': original['quote'],
            'quote_fragments': fragments, 'quote_assembly': 'join quote_fragments using a single ASCII space; fragment characters unchanged',
            'source_url': next(c['original']['source_url'] for c in factcheck.load(D / 'run')['claims'] if c['id'] == parent['claim_id']),
            'esg_part_id': pid,
            'quantitative': part['quantitative'],
        }
        for field in ('metric', 'value', 'unit', 'period_evidence', 'context_note'):
            if field in part:
                row[field] = part[field]
        rows.append(row)
        parent_path = D / f'run/results/C{parent_number:06}.r000001.json'
        origins.append({
            'atomic_id': row['id'], 'esg_part_id': pid,
            'parent_packet': str(parent_path.relative_to(D)), 'parent_packet_sha256': sha(parent_path),
            'parent_claim_id': parent['claim_id'], 'parent_aspect_ids': aspect_ids,
            'selected_evidence_ids': evidence_ids,
            'excluded_evidence': [{'id': e['id'], 'reason': 'Не нужен для данного атома: закупка/отдельная надзорная проверка не устанавливает точное принятие обещания, групповой счетчик или операциональный критерий принципа; не выдается за опровержение.'} for e in parent['evidence'] if e['id'] not in evidence_ids],
            'quote_assembly': {'method': row['quote_assembly'], 'statement': statement,
                'parent_quote': original['quote'], 'fragment_spans': [{'quote': f, 'start': original['quote'].index(f), 'end': original['quote'].index(f)+len(f)} for f in fragments],
                'context': 'Фрагменты могут быть разнесены или содержать исходный перенос/часть слова; полный исходный абзац сохранен и проверен PDF-агентом. Не заявляется, что сборка является непрерывной дословной цитатой.',
                'quantitative_fields': {k: part[k] for k in ('metric','value','unit','period','entity_scope','period_evidence') if k in part}},
            'reuse_disclosure': 'Производная атомарная оценка по уже выполненному живому поиску принятой родительской строки. Новых запросов нет; searched_at, tool_ref, content и content_sha256 не переписываются.',
        })
write(D / 'atomic_input.json', {'claims': rows, 'provenance': {'classification_review': '../02_ESG/classification_review.json', 'sha256': sha(review_path), 'atomic_parts': 8, 'full_report_extraction_complete': False}})
factcheck.prepare(D / 'atomic_input.json', D / 'atomic_run')
plan = factcheck.load(D / 'atomic_run')
(D / 'atomic_responses').mkdir()
checked = datetime.now(ZoneInfo('Asia/Yekaterinburg')).isoformat()
for n, (row, origin) in enumerate(zip(rows, origins), 1):
    pid = row['esg_part_id']
    parent = parents[map_parts[pid][0]]
    packet = copy.deepcopy(parent)
    packet.update(source_sha256=plan['source_sha256'], claim_id=f'C{n:06}', quote=row['statement'],
                  revision=1, checked_at=checked,
                  reviewer=parent['reviewer'] + '; derivative atomic assessment from existing accepted research',
                  reason=reasons[pid])
    packet['target'].update(proposition=propositions[pid], entity=row['entity_scope'], period=row['period'], boundary=row['boundary'])
    selected = origin['selected_evidence_ids']
    packet['evidence'] = [e for e in packet['evidence'] if e['id'] in selected]
    source_ids = {e['source_id'] for e in packet['evidence']}
    packet['sources'] = [s for s in packet['sources'] if s['id'] in source_ids]
    for query in packet['searches']:
        query['source_ids'] = [sid for sid in query['source_ids'] if sid in source_ids]
        query['outcome_note'] += ' [Атомарная производная: запрос и время сохранены; source_ids ограничены источниками данного атома. Полный результат запроса — в родительском native journal.]'
    packet['aspects'] = [a for a in packet['aspects'] if a['id'] in origin['parent_aspect_ids']]
    for aspect in packet['aspects']:
        aspect['evidence_ids'] = [eid for eid in aspect['evidence_ids'] if eid in selected]
        aspect['reason'] = reasons[pid]
    packet['aspect_coverage_reason'] = f"Атом {pid} проектного ESG3.1. Только аспекты {origin['parent_aspect_ids']} родительской строки; юридический scope, period и unit пересмотрены отдельно. Полный корпус не заявляется."
    packet['source_review']['method'] += '; атомарная сборка сверена по точным quote_fragments проверенной исходной цитаты'
    packet['source_review']['locator'] += f'; ../02_ESG/classification_review.json part_id={pid}; provenance.json atomic_id={row["id"]}'
    packet['source_review']['parent_packet_sha256'] = origin['parent_packet_sha256']
    packet['source_review']['scope'] = 'verified parent PDF quote plus deterministic exact-fragment assembly; not independent external truth'
    packet['derived_research'] = {'provenance': 'provenance.json', 'atomic_id': row['id'], 'new_searches': False, 'parent_packet_sha256': origin['parent_packet_sha256']}
    packet['limitations'].append('Это производная оценка конкретного атома по ранее выполненным поискам; checked_at — дата атомарного пересмотра, searched_at — сохраненная дата реальных запросов.')
    if pid == '001-a':
        for e in packet['evidence']:
            e['reason'] = 'Контекст соглашения/задачи САКВ; не юридический оригинал с точной обязанностью разработки плана на объектах I категории.'
            e['alignment']['metric'] = {'status':'unknown', 'reason':'Не удостоверено точное обязательство разработать именно план САКВ; оснащение труб и экологический план модернизации не тождественны этому документу.'}
        packet['aspects'][0]['proposition'] = 'Принято обязательство разработать план создания САКВ на эксплуатируемых объектах I категории.'
    elif pid == '001-b':
        for e in packet['evidence']:
            e['reason'] = 'Сообщение о соглашении не содержит точной обязанности представить сведения о количестве стационарных источников.'
            e['alignment']['metric'] = {'status':'unknown','reason':'Прямого текста обязанности представить сведения о количестве источников в отрывке нет.'}
            e['alignment']['period'] = {'status':'matched','reason':'Контекст принятия соглашения — апрель 2023; до2025 — планируемое оснащение, не срок представления сведений.'}
        packet['aspects'][0]['proposition'] = 'Принято обязательство представить сведения о количестве стационарных источников, планируемых к оснащению САКВ до 2025 г.; срок представления не установлен.'
    elif pid == '002-a':
        for e in packet['evidence']:
            e['reason'] = 'Корпоративное раскрытие суммы 96,23 млрд руб. либо 96 232,61 млн руб. за 2023; независимого происхождения нет.'
            e['alignment']['metric'] = {'status':'matched','reason':'Именно сумма общих экологических расходов за2023, не только инвестиции.'}
            e['alignment']['unit'] = {'status':'matched','reason':'Млрдруб; для корпоративной таблицы выполнено точное преобразование 96 232,61 млнруб /1000=96,23261 млрдруб с округлением до96,23.'}
    elif pid == '002-b':
        for e in packet['evidence']:
            e['reason'] = 'Корпоративный источник дает рост8,0% либо две исходные суммы для его расчета; суммы независимо не удостоверены.'
            e['alignment']['metric'] = {'status':'matched','reason':'Относительный рост общих расходов2023 к2022; (96232,61/89138,75−1)×100=7,958223…%, округляется до8,0%.'}
            e['alignment']['unit'] = {'status':'matched','reason':'Процент относительного роста. В таблице исходные суммы вмлнруб; при отношении единицыруб сокращаются, результат умножается на100. Не процентные пункты.'}
    elif pid.startswith('004-'):
        e = packet['evidence'][0]
        metric = {'004-a':'Число проверок — 761','004-b':'Число выявленных нарушений — 517','004-c':'Число проверок без выявленных нарушений — 563'}[pid]
        e['reason'] = metric + '; собственное корпоративное раскрытие, не независимый свод.'
        e['alignment']['metric'] = {'status':'matched','reason':metric + '; не смешивается с двумя другими счетчиками.'}
        e['alignment']['unit'] = {'status':'matched','reason':'Нарушения; не проверки и не объекты.' if pid=='004-b' else 'Проверки; не нарушения и не объекты.'}
        if pid == '004-a': e['quote'] = e['quote'].split(', в ре')[0]
        elif pid == '004-b': e['quote'] = 'выявлено 517 нарушений.'
        else: e['quote'] = '563 проверок нарушений выявлено не было.'
    factcheck.validate(packet, plan)
    response_path = D / f'atomic_responses/C{n:06}.r000001.json'
    write(response_path, packet)
    origin['canonical_claim_id'] = packet['claim_id']
    origin['atomic_response'] = str(response_path.relative_to(D))
    origin['atomic_response_sha256'] = sha(response_path)
    origin['reused_searches'] = [{k:q[k] for k in ('id','direction','query','tool_ref','searched_at')} for q in packet['searches']]
write(D / 'provenance.json', {'schema_version':'atomic-derivation-1.0', 'derived_at':checked, 'method':'Existing project FACT_CHECK_AGENT esg-factcheck-1.0; atomic selection and reassessment, no new search calls', 'classification_review':str(review_path.relative_to(D.parent)), 'classification_review_sha256':sha(review_path), 'atomic_input_sha256':sha(D/'atomic_input.json'), 'parent_run':'run', 'native_journals':'journal/', 'atomic_count':len(rows), 'new_searches':False, 'mappings':origins})
print('Prepared eight atomic packets with explicit parent-aspect provenance; not yet ingested.')
