"""Reproducible adjudication register for the existing 76 heuristic flags.

Does not edit gold or produce human/true-false labels. Per-case decisions follow
codebook v4 rules 30/39 and were inspected against the flagged sentence text.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

P = Path(__file__).resolve().parents[1]
FLAGS = P / 'data/gold_extract/audit_flags.csv'
GOLD = P / 'data/out/gold_extract.csv'
CODEBOOK = P / 'codebook/Инструкция_по_разметке_v4.md'

# Explicit review of this exact snapshot, not a generic digit-removal rule.
GROUPS = [
    ([1, 4, 15, 30, 34, 36, 41, 45, 54, 55, 64, 73, 75],
     'служебная_верстка', 'Ложная тревога по has_number: цифры колонтитула, навигации, страниц или заголовков; правило30/39. Содержательная мысль не содержит количественного показателя.'),
    ([2, 6, 10, 35, 40, 44, 47, 48, 49, 51, 52, 66, 67, 68, 70, 76],
     'идентификатор_стандарта', 'Ложная тревога по has_number: GRI/МЭР/СОКБ/ASI/OHSAS/СанПиН и номера разделов — идентификаторы, а не количество или показатель.'),
    ([5, 14, 27, 31, 32, 50],
     'дата_или_номер_документа', 'Ложная тревога по has_number: дата решения/утверждения, номер приказа или протокола. Правило30 исключает даты и номера документов.'),
    ([7, 16, 29, 39, 57, 63, 69, 71],
     'сноска_или_ссылка', 'Ложная тревога по has_number: номер сноски, приложения либо ссылки на источник/документ; не количественный признак заявления.'),
    ([12, 13, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26],
     'номер_пункта', 'Ложная тревога по has_number: порядковый номер критерия или пункта перечня действий, не число выполненных действий.'),
    ([9, 65],
     'идентификатор_вещества_или_охвата', 'Ложная тревога по has_number: CO2 и охваты1/2 — обозначения вещества/областей учета, не числовой результат или размер цели.'),
    ([3, 11, 38, 42, 43, 46, 56, 58, 61, 62, 74],
     'соседняя_диаграмма_или_шапка', 'По правилу39 числовой фрагмент соседнего графика/таблицы не относится к размечаемой законченной мысли. Тревога has_number сама по себе не доказывает ошибку. Сохранить как признак загрязнения сегментации, не приписывать эти числа заявлению.'),
    ([59], 'название_мероприятия', 'COP-29 — название конференции, а не количество мероприятий или результат.'),
    ([28], 'regex_не_узнает_будущее', '«Следующий шаг — прохождение экологической экспертизы и начало строительно-монтажных работ» явно обозначает будущее действие, хотя regex FUTURE не содержит этот оборот. Есть также склейка соседнего описания процедур; это отдельная проблема границ.'),
    ([33], 'regex_не_узнает_числительное', '«Не реже одного раза в год»: количественная частота есть. NUM_WORDS не включает падежную форму «одного». has_number=да поддерживается текстом.'),
    ([60], 'regex_не_узнает_номинальную_цель', 'Климатическая цель сформулирована отглагольным существительным «Сокращение до нуля…» в стратегии с горизонтами2025/2030/2050, а не глаголом будущего. Отсутствие regex-маркера не доказывает ошибку типа.'),
    ([72], 'будущее_во_второстепенной_части', 'Основная мысль: «Свеза» уже получила статус партнера и была верифицирована. Будущее относится к присуждению премии, а не отменяет состоявшийся результат. Не является явным обязательством компании.'),
]
PENDING = {
    8: ('возраст_получателя', '16-летний получатель помощи — число связано с описанием получателя, но не с объемом ESG-результата. Требуется уточнение codebook: считается ли возраст релевантным количеством; не менять final_has_number автоматически.'),
    37: ('граница_предложения', 'После перечня направлений программы склеен фрагмент «предприниматель принял участие…41». Возможно, это реальный количественный результат41предприниматель, а не колонтитул. Требуется визуально установить связь и границы; ни снятие флага, ни замена label не доказаны.'),
    53: ('уровень_рейтинга', '1-я группа и2-й уровень рейтинга относятся к достижению, но представляют категории/ранг, а не количество. Нужна явная конвенция codebook по порядковым рейтингам; автоматическую замену не выполнять.'),
}

def main():
    gold_hash = hashlib.sha256(GOLD.read_bytes()).hexdigest()
    assert hashlib.sha256(FLAGS.read_bytes()).hexdigest() == '20b5c15a27ad9c1a3915f62a8062750956b0374c77894d07bef20eccb4186e69', 'Flag snapshot changed: review decisions again'
    with FLAGS.open(encoding='utf-8-sig') as f:
        flags = list(csv.DictReader(f, delimiter=';'))
    assert len(flags) == 76, 'Snapshot changed: inspect flags again, do not silently reuse decisions'
    decisions = {}
    for indices, category, reason in GROUPS:
        for i in indices:
            assert i not in decisions
            decisions[i] = ('эвристический флаг снят', category, reason)
    for i, (category, reason) in PENDING.items():
        assert i not in decisions
        decisions[i] = ('требует адресной проверки', category, reason)
    assert set(decisions) == set(range(1, 77))
    expected = {8: 'LKOH-2023-ОУР_f016_s07', 33: 'ALRS-2023-ОУР_f044_s09',
                37: 'IRKN-2025-ИО_f049_s01', 53: 'TRMK-2025-ОУР_f091_s01',
                72: 'SVEZ-2023-ОУР_f126_s05', 76: 'URKA-2025-ОУР_f130_s05'}
    for i, sid in expected.items(): assert flags[i-1]['sentence_id'] == sid
    rows = []
    for i, f in enumerate(flags, 1):
        decision, category, reason = decisions[i]
        rows.append(dict(sentence_id=f['sentence_id'], flag=f['что'],
                         decision=decision, category=category, rationale=reason,
                         original_flag_details=f['детали'], sentence=f['предложение'],
                         gold_modified='нет', review_method='одна машинная проверка по codebook v4'))
    dest=P/'data/review_v2';dest.mkdir(exist_ok=True)
    with (dest/'gold_flags_review.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f, list(rows[0]),delimiter=';');w.writeheader();w.writerows(rows)
    summary={'flags_total':76,'decisions':dict(Counter(r['decision'] for r in rows)),
             'confirmed_gold_label_errors':0, 'pending_sentence_ids':[flags[i-1]['sentence_id'] for i in PENDING],
             'gold_unchanged':hashlib.sha256(GOLD.read_bytes()).hexdigest()==gold_hash,
             'gold_sha256':gold_hash,'flags_sha256':hashlib.sha256(FLAGS.read_bytes()).hexdigest(),
             'codebook_sha256':hashlib.sha256(CODEBOOK.read_bytes()).hexdigest(),
             'human_review':False,'double_independent_human_annotation':False}
    (dest/'gold_flags_review.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
