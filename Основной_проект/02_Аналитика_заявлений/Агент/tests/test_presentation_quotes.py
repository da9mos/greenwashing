import copy
import csv
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import esg_agent_v3_1 as profile
import review_response

base = profile.base
PARAGRAPH = ('В 2023 г. государственными надзорными органами прове-\n'
             'дена 761 проверка соблюдения требований в области ООС\n'
             'и природопользования на объектах Группы Газпром, в ре-\n'
             'зультате которых выявлено 517 нарушений. По результатам\n'
             '563 проверок нарушений выявлено не было.')
ATOM = 'зультате которых выявлено 517 нарушений.'


class PresentationQuoteTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        source = self.root / 'source.md'
        source.write_text('<!-- pdf_page: 1 -->' + PARAGRAPH + '\n\nКонтакты.', encoding='utf-8', newline='\n')
        self.work = self.root / 'work'
        manifest = profile.prepare(source, self.work, 'QUOTES')
        batch = base.read(self.work / manifest['batches'][0]['file'])
        self.bid, self.other = batch['target_block_ids']
        self.data = {
            'schema_version': base.VERSION, 'source_sha256': manifest['source_sha256'],
            'batch_id': batch['batch_id'], 'reviewer': 'Regression fixture',
            'claims': [{'id': 'c1', 'type': 'результат', 'block': 'E', 'topic': 'другое',
                        'block2': '', 'statement': ATOM, 'source_kind': 'text',
                        'source_status': 'md_only', 'reason': 'Экологические нарушения', 'quantitative': False,
                        'evidence': [{'block_id': self.bid, 'quote': ATOM, 'role': 'statement'}],
                        'decision': {'inclusion_rule': 'I1', 'classification_rule': 'E1',
                                     'subject': 'Группа Газпром', 'proposition': 'Выявлено 517 нарушений',
                                     'esg_object': 'Соблюдение экологических требований',
                                     'source_refs': ['ESRS2023', 'GRI2021'], 'secondary_blocks': [],
                                     'classification_status': 'resolved', 'ambiguity_note': ''}}],
            'coverage': [{'block_id': self.bid, 'status': 'extracted', 'reason': 'Выявленные нарушения',
                          'claim_ids': ['c1']},
                         {'block_id': self.other, 'status': 'excluded', 'reason': 'Контакты',
                          'claim_ids': [], 'exclusion_rule': 'X1'}]}

    def prepared(self, quote=PARAGRAPH):
        self.data['claims'][0].update(presentation_quote=quote, presentation_block_id=self.bid)
        return self.data

    def test_legacy_is_valid_for_classification_but_explicitly_unprepared(self):
        before = copy.deepcopy(self.data)
        data, stats = profile.check(self.work, self.data)
        self.assertEqual(data, before)
        self.assertEqual(stats['presentation_ready_claims'], 0)
        self.assertEqual(stats['presentation_unready_claims'], 1)
        self.assertEqual(stats['presentation_status_by_claim'], {'c1': 'unprepared_legacy'})

    def test_continuous_full_paragraph_preserves_wrapping_and_atomic_core(self):
        self.prepared()
        data, stats = profile.check(self.work, self.data)
        self.assertEqual(stats['presentation_ready_claims'], 1)
        self.assertEqual(data['claims'][0]['presentation_quote'], PARAGRAPH)
        self.assertEqual(data['claims'][0]['statement'], ATOM)

    def test_start_inside_line_wrapped_word_is_rejected(self):
        self.prepared(ATOM)
        with self.assertRaisesRegex(ValueError, 'обрезает слово'):
            profile.check(self.work, self.data)

    def test_end_inside_word_is_rejected(self):
        self.prepared(PARAGRAPH[:PARAGRAPH.index('нарушений.') + len('наруше')])
        with self.assertRaisesRegex(ValueError, 'обрезает слово'):
            profile.check(self.work, self.data)

    def test_disjoint_fragments_are_not_a_presentation_quote(self):
        self.prepared('В 2023 г. 563 проверок нарушений выявлено не было.')
        with self.assertRaisesRegex(ValueError, 'непрерывной точной цитатой'):
            profile.check(self.work, self.data)

    def test_multiple_atomic_claims_can_share_one_exact_paragraph(self):
        self.prepared()
        fragments = ['дена 761 проверка соблюдения требований в области ООС', ATOM,
                     '563 проверок нарушений выявлено не было.']
        template = self.data['claims'][0]
        self.data['claims'] = []
        for i, fragment in enumerate(fragments, 1):
            claim = copy.deepcopy(template)
            claim.update(id=f'c{i}', statement=fragment,
                         evidence=[{'block_id': self.bid, 'quote': fragment, 'role': 'statement'}])
            self.data['claims'].append(claim)
        self.data['coverage'][0]['claim_ids'] = ['c1', 'c2', 'c3']
        data, stats = profile.check(self.work, self.data)
        self.assertEqual(stats['presentation_ready_claims'], 3)
        self.assertTrue(all(c['presentation_quote'] == PARAGRAPH for c in data['claims']))

    def test_incomplete_empty_and_unrelated_source_pairs_are_rejected(self):
        for updates in ({'presentation_quote': PARAGRAPH},
                        {'presentation_quote': '', 'presentation_block_id': self.bid},
                        {'presentation_quote': PARAGRAPH, 'presentation_block_id': 'unknown'},
                        {'presentation_quote': 'Контакты.', 'presentation_block_id': self.other}):
            with self.subTest(updates=updates):
                self.data['claims'][0].update(updates)
                with self.assertRaises(ValueError):
                    profile.check(self.work, self.data)
                self.data['claims'][0].pop('presentation_quote', None)
                self.data['claims'][0].pop('presentation_block_id', None)

    def test_review_never_constructs_or_repairs_a_display_quote(self):
        path = self.root / 'response.json'
        base.write(path, self.data)
        before = path.read_bytes()
        data, stats = review_response.review(self.work, path)
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn('presentation_quote', data['claims'][0])
        self.assertEqual(stats['presentation_unready_claims'], 1)
        self.prepared(ATOM)
        base.write(path, self.data)
        with self.assertRaises(ValueError):
            review_response.review(self.work, path)

    def test_export_marks_legacy_and_never_fills_quote_from_statement(self):
        path = self.root / 'response.json'
        base.write(path, self.data)
        out, summary = profile.export(self.work, [path], self.root / 'export')
        with (out / 'claims.csv').open(encoding='utf-8-sig', newline='') as stream:
            row = next(csv.DictReader(stream, delimiter=';'))
        self.assertEqual(row['presentation_quote'], '')
        self.assertEqual(row['presentation_status'], 'unprepared_legacy')
        self.assertEqual(summary['presentation_unready_claims'], 1)

    def test_plain_and_hyphenated_word_boundaries_and_exact_occurrences(self):
        self.assertFalse(base.whole_word_quote('ботник', 'работник'))
        self.assertFalse(base.whole_word_quote('работ', 'работник'))
        self.assertFalse(base.whole_word_quote('зультате', 'ре-\nзультате'))
        self.assertFalse(base.whole_word_quote('ре', 'ре-\nзультате'))
        self.assertFalse(base.whole_word_quote('социальный', 'социально-социальный'))
        self.assertTrue(base.whole_word_quote('обучение', 'переобучение, обучение'))
        self.assertTrue(base.whole_word_quote('Выбросы снижены.', 'Группа Газпром. Выбросы снижены.'))


if __name__ == '__main__':
    unittest.main()
