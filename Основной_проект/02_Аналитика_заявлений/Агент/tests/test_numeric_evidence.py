import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import esg_agent_v3_1 as profile
import review_response

base = profile.base


class NumericEvidenceTests(unittest.TestCase):
    def test_partial_integers_and_years_rejected(self):
        for field, value, quote in [('value', '5', '517'), ('value', '17', '517'),
                                     ('period', '202', '2023'), ('period', '2023', '20230')]:
            with self.subTest(field=field, value=value, quote=quote):
                self.assertFalse(base.evidence_supports(field, value, quote))

    def test_decimal_sign_and_exponent_parts_rejected(self):
        for value, quote in [('5', '5,17'), ('17', '5.17'), ('5', '-5'), ('5', '−5'),
                             ('5', '+5'),
                             ('5', '5e3'), ('3', '5e-3'), ('1', '1/2')]:
            with self.subTest(value=value, quote=quote):
                self.assertFalse(base.evidence_supports('value', value, quote))

    def test_grouped_number_parts_rejected(self):
        for space in (' ', '\u00a0', '\u202f'):
            for value in ('517', '1'):
                with self.subTest(space=repr(space), value=value):
                    self.assertFalse(base.evidence_supports('value', value, f'1{space}517'))
            self.assertTrue(base.evidence_supports('value', f'1{space}517', f'Итого 1{space}517 тонн'))

    def test_exact_ranges_and_values_supported_without_normalizing(self):
        for field, value, quote in [
            ('value', '517', 'Выявлено 517 нарушений.'),
            ('value', '8,0', 'Рост 8,0 %'), ('value', '96,23', '96,23 млрд руб.'),
            ('value', '0', '0 случаев'), ('value', '-5,17', 'Изменение -5,17 %'),
            ('value', '−5', '−5 тонн'), ('value', '+5', '+5 тонн'),
            ('value', '5e-3', 'Итого 5e-3'), ('value', '1/2', 'Доля 1/2'),
            ('period', '2023', 'В 2023 г.'),
            ('period', '2023–2025', 'План на 2023–2025 гг.'),
            ('period', '2023 – 2025', 'План на 2023 – 2025 гг.'),
            ('period', '2023 относительно 2022', '2023 относительно 2022'),
            ('value', '16,8', 'ПАО «Газпром» — 16,8 %'),
            ('value', '5 144', 'В дочерних обществах — 5 144 человека'),
            ('period', '2025', 'Вахта памяти — 2025. Щит Кавказа'),
            ('value', '10', 'троллейбусов –10 ед.'),
        ]:
            with self.subTest(field=field, value=value, quote=quote):
                self.assertTrue(base.evidence_supports(field, value, quote))
        self.assertFalse(base.evidence_supports('value', '96.23', '96,23'))
        self.assertFalse(base.evidence_supports('period', '2023', '2023–2025'))

    def test_math_sign_with_spacing_cannot_be_removed(self):
        for signed in ('− 5', '+ 5', '−\u00a05', '+\u202f5'):
            with self.subTest(signed=signed):
                self.assertFalse(base.evidence_supports('value', '5', signed))
                self.assertTrue(base.evidence_supports('value', signed, signed))

    def test_table_direction_marker_cannot_be_removed(self):
        for signed in ('↓ 3,7', '↑\u00a03,7'):
            with self.subTest(signed=signed):
                self.assertFalse(base.evidence_supports('value', '3,7', f'{signed}%'))
                self.assertTrue(base.evidence_supports('value', signed, f'{signed}%'))

    def test_exact_occurrence_can_follow_invalid_occurrence(self):
        self.assertTrue(base.evidence_supports('value', '517', '1 517 тонн; ранее 517 тонн'))
        self.assertTrue(base.evidence_supports('value', '517', '517 2023'))

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        source = self.root / 'source.md'
        source.write_text('<!-- pdf_page: 1 -->Компания; Выбросы; 517; тонн; 2023')
        self.work = self.root / 'work'
        manifest = profile.prepare(source, self.work, 'NUMERIC')
        batch = base.read(self.work / manifest['batches'][0]['file'])
        bid = batch['target_block_ids'][0]
        statement = batch['blocks'][0]['text']
        self.data = {
            'schema_version': base.VERSION, 'source_sha256': manifest['source_sha256'],
            'batch_id': batch['batch_id'], 'reviewer': 'Regression test',
            'claims': [{
                'id': 'c1', 'type': 'результат', 'block': 'E', 'topic': 'климат',
                'block2': '', 'statement': statement, 'source_kind': 'text',
                'source_status': 'md_only', 'reason': 'Раскрытие показателя',
                'quantitative': True, 'metric': 'Выбросы', 'value': '517',
                'unit': 'тонн', 'period': '2023', 'entity_scope': 'Компания',
                'evidence': [{'block_id': bid, 'quote': statement, 'role': 'statement'}] + [
                    {'block_id': bid, 'quote': quote, 'role': role}
                    for role, quote in [('subject', 'Компания'), ('metric', 'Выбросы'),
                                        ('value', '517'), ('unit', 'тонн'), ('period', '2023')]],
                'decision': {'inclusion_rule': 'I4', 'classification_rule': 'E1',
                             'subject': 'Компания', 'proposition': 'Раскрыты выбросы',
                             'esg_object': 'Выбросы', 'source_refs': ['ESRS2023', 'GRI2021'],
                             'secondary_blocks': [], 'classification_status': 'resolved',
                             'ambiguity_note': ''}}],
            'coverage': [{'block_id': bid, 'status': 'extracted', 'reason': 'Показатель',
                          'claim_ids': ['c1']}]
        }

    def test_validator_blocks_false_number_and_period_even_when_pending(self):
        for field, value in [('value', '5'), ('period', '202')]:
            for status in ('md_only', 'needs_pdf_review'):
                with self.subTest(field=field, status=status):
                    data = copy.deepcopy(self.data)
                    data['claims'][0].update({field: value, 'source_status': status})
                    with self.assertRaises(ValueError):
                        profile.check(self.work, data)

    def test_review_withholds_false_value_and_preserves_original(self):
        self.data['claims'][0]['value'] = '5'
        path = self.root / 'response.json'
        base.write(path, self.data)
        before = path.read_bytes()
        data, stats = review_response.review(self.work, path)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(data['claims'][0]['value'], '')
        self.assertEqual(data['claims'][0]['source_status'], 'needs_pdf_review')
        self.assertEqual(data['coverage'][0]['status'], 'pending')
        self.assertEqual(stats['cleared_unsupported_fields'], {'value': 1})
        self.assertEqual(stats['pending_blocks'], 1)
        self.assertEqual(stats['pending_claims'], 1)

    def test_review_reopens_already_incomplete_context(self):
        self.data['claims'][0].update(value='', source_status='needs_pdf_review')
        path = self.root / 'response.json'
        base.write(path, self.data)
        data, stats = review_response.review(self.work, path)
        self.assertEqual(data['coverage'][0]['status'], 'pending')
        self.assertEqual(stats['reopened_blocks'], 1)

    def test_sliced_numeric_quote_is_rejected_against_source(self):
        for field, false_value, role in [('value', '5', 'value'), ('period', '202', 'period')]:
            data = copy.deepcopy(self.data)
            data['claims'][0][field] = false_value
            next(e for e in data['claims'][0]['evidence'] if e['role'] == role)['quote'] = false_value
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    profile.check(self.work, data)
                path = self.root / (field + '.json')
                base.write(path, data)
                with self.assertRaises(ValueError):
                    review_response.review(self.work, path)


if __name__ == '__main__':
    unittest.main()
