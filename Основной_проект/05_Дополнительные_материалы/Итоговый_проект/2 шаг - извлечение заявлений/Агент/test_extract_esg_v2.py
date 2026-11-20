import copy
import json
import csv
import tempfile
import unittest
from pathlib import Path
from extract_esg_v2 import prepare, validate, export


class V2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.report = Path(self.tmp.name) / 'source.md'
        self.report.write_text('<!-- pdf_page: 1 --><!-- source_text_begin -->Компания снизила выбросы.\n\nПланируем обучение работников.<!-- source_text_end -->')
        self.data, self.blocks = prepare(self.report, 'Компания', 2024)
        self.claim = {'id': 'c1', 'type': 'результат', 'type_reason': 'Состоявшееся действие', 'primary_topic': 'E', 'secondary_topics': [], 'topic_reason': 'Выбросы', 'subtopic': 'Загрязнение', 'statement': 'Компания снизила выбросы.', 'source_kind': 'text', 'status': 'reviewed', 'evidence': [{'block_id': self.blocks[0]['id'], 'quote': 'Компания снизила выбросы.', 'role': 'statement'}]}
        self.data['claims'] = [self.claim]
        self.data['coverage'][0].update(status='extracted', reason='Найдено заявление', claim_ids=['c1'])

    def test_pending_blocks_not_reported_complete(self):
        stats = validate(self.report, self.data)
        self.assertEqual(stats['pending_blocks'], 1)
        self.assertEqual(stats['recall'], 'not measured')

    def test_unknown_topic_retained_when_pending(self):
        self.claim.update(primary_topic=None, status='pending', review_reason='Неясен предмет')
        self.assertEqual(validate(self.report, self.data)['pending_claims'], 1)

    def test_unknown_topic_cannot_be_reviewed(self):
        self.claim['primary_topic'] = None
        with self.assertRaises(ValueError): validate(self.report, self.data)

    def test_secondary_cannot_duplicate_primary(self):
        self.claim['secondary_topics'] = ['E']
        with self.assertRaises(ValueError): validate(self.report, self.data)

    def test_invented_statement_with_real_quote_rejected(self):
        self.claim['statement'] = 'Выбросы снижены на 99 процентов.'
        with self.assertRaises(ValueError): validate(self.report, self.data)

    def test_narrative_table_allowed(self):
        self.claim['source_kind'] = 'table'
        validate(self.report, self.data)

    def test_fake_quote_rejected(self):
        self.claim['evidence'][0]['quote'] = 'Снизила на 90 процентов'
        with self.assertRaises(ValueError): validate(self.report, self.data)

    def test_missing_block_rejected(self):
        self.data['coverage'].pop()
        with self.assertRaises(ValueError): validate(self.report, self.data)

    def test_excluded_block_cannot_have_claim(self):
        self.data['coverage'][0]['status'] = 'excluded'
        with self.assertRaises(ValueError): validate(self.report, self.data)

    def test_missing_backreference_rejected(self):
        self.data['coverage'][0].update(status='pending', claim_ids=[])
        with self.assertRaises(ValueError): validate(self.report, self.data)

    def test_duplicate_id_rejected(self):
        self.data['claims'].append(copy.deepcopy(self.claim))
        with self.assertRaises(ValueError): validate(self.report, self.data)

    def test_table_requires_units_period_subject(self):
        self.claim['source_kind'] = 'table'
        self.claim['quantitative'] = True
        with self.assertRaises(ValueError): validate(self.report, self.data)

    def test_second_pass_requires_evidence(self):
        self.data['second_pass']['status'] = 'completed'
        with self.assertRaises(ValueError): validate(self.report, self.data)

    def test_export_retains_pending_and_refuses_overwrite(self):
        self.claim.update(primary_topic=None, status='pending', review_reason='Контекст')
        out = Path(self.tmp.name) / 'export'
        export(self.report, self.data, out)
        self.assertIn('Не определено', (out/'registry.csv').read_text(encoding='utf-8-sig'))
        with self.assertRaises(FileExistsError): export(self.report, self.data, out)

    def test_primary_views_partition_and_secondary_does_not_duplicate(self):
        self.claim['secondary_topics'] = ['G']
        out = Path(self.tmp.name) / 'views'
        export(self.report, self.data, out)
        summary = json.loads((out/'summary.json').read_text())
        self.assertEqual(summary['unique_claims'], 1)
        self.assertEqual(summary['primary_counts'], {'E': 1, 'S': 0, 'G': 0})
        self.assertEqual(summary['secondary_label_counts']['G'], 1)
        for topic, expected in [('E', 2), ('S', 1), ('G', 1), ('unresolved', 1)]:
            with (out/f'primary_{topic}.csv').open(encoding='utf-8-sig', newline='') as f:
                self.assertEqual(len(list(csv.reader(f, delimiter=';'))), expected)

    def test_unresolved_view_retains_pending(self):
        self.claim.update(primary_topic=None, status='pending', review_reason='Контекст')
        out = Path(self.tmp.name) / 'pending_views'
        export(self.report, self.data, out)
        summary = json.loads((out/'summary.json').read_text())
        self.assertEqual(summary['primary_unresolved'], 1)
        self.assertEqual(sum(summary['primary_counts'].values()), 0)
        self.assertIn('c1', (out/'primary_unresolved.csv').read_text(encoding='utf-8-sig'))

    def test_stale_source_rejected(self):
        self.report.write_text(self.report.read_text() + '\n')
        with self.assertRaises(ValueError): validate(self.report, self.data)

    def test_inventory_retains_all_nonwhitespace(self):
        self.assertEqual([b['text'] for b in self.blocks], ['Компания снизила выбросы.', 'Планируем обучение работников.'])


if __name__ == '__main__': unittest.main()
