"""Isolated regression specifications. Never mutates model responses or agent files.

Run from any cwd: python3 /absolute/path/to/reproduce_defects.py -v
Four regression specifications FAIL against the original audited implementation.
"""
from pathlib import Path
import copy
import importlib.util
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[2]
SCRIPTS = PROJECT / '02_Аналитика_заявлений/Агент/scripts'
sys.path.insert(0, str(SCRIPTS))
import esg_agent_v3_1 as profile
import review_response


class RegressionSpecifications(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.md'
        self.source.write_text('<!-- pdf_page: 1 -->Компания; Выбросы; 517; тонн; 2023')
        self.work = self.root / 'work'
        self.manifest = profile.prepare(self.source, self.work, 'REPRO')
        batch = profile.base.read(self.work / self.manifest['batches'][0]['file'])
        bid = batch['target_block_ids'][0]
        statement = batch['blocks'][0]['text']
        claim = {
            'id': 'c1', 'type': 'результат', 'block': 'E', 'topic': 'климат',
            'block2': '', 'statement': statement, 'source_kind': 'text',
            'source_status': 'md_only', 'reason': 'Тестовый экологический показатель',
            'quantitative': True, 'metric': 'Выбросы', 'value': '517',
            'unit': 'тонн', 'period': '2023', 'entity_scope': 'Компания',
            'evidence': [{'block_id': bid, 'quote': statement, 'role': 'statement'}] + [
                {'block_id': bid, 'quote': value, 'role': role}
                for role, value in [('subject', 'Компания'), ('metric', 'Выбросы'),
                                    ('value', '517'), ('unit', 'тонн'), ('period', '2023')]
            ],
            'decision': {
                'inclusion_rule': 'I4', 'classification_rule': 'E1',
                'subject': 'Компания', 'proposition': 'Раскрыты выбросы',
                'esg_object': 'Выбросы', 'source_refs': ['ESRS2023', 'GRI2021'],
                'secondary_blocks': [], 'classification_status': 'resolved',
                'ambiguity_note': ''
            }
        }
        self.data = {
            'schema_version': profile.base.VERSION,
            'source_sha256': self.manifest['source_sha256'],
            'batch_id': batch['batch_id'], 'reviewer': 'Codex regression fixture',
            'claims': [claim],
            'coverage': [{'block_id': bid, 'status': 'extracted', 'reason': 'Числовой факт',
                          'claim_ids': ['c1']}]
        }

    def test_valid_complete_number_is_accepted(self):
        _, stats = profile.check(self.work, self.data)
        self.assertEqual(stats['pending_claims'], 0)

    def test_number_substring_must_not_pass(self):
        self.data['claims'][0]['value'] = '5'  # Only the complete value 517 exists.
        with self.assertRaises(ValueError):
            profile.check(self.work, self.data)

    def test_period_substring_must_not_pass(self):
        self.data['claims'][0]['period'] = '202'  # Only 2023 exists.
        with self.assertRaises(ValueError):
            profile.check(self.work, self.data)

    def test_review_must_not_leave_unsupported_number_md_only(self):
        self.data['claims'][0]['value'] = '5'
        path = self.root / 'response.json'
        profile.base.write(path, self.data)
        original = path.read_bytes()
        data, stats = review_response.review(self.work, path)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(data['claims'][0]['source_status'], 'needs_pdf_review')

    def test_incomplete_numeric_context_must_reopen_coverage(self):
        claim = self.data['claims'][0]
        claim['value'] = ''
        claim['source_status'] = 'needs_pdf_review'
        path = self.root / 'response.json'
        profile.base.write(path, self.data)
        data, _ = review_response.review(self.work, path)
        self.assertEqual(data['coverage'][0]['status'], 'pending')

    def test_numeric_withheld_still_blocks_export(self):
        self.data['claims'][0].update(value='', source_status='needs_pdf_review')
        path = self.root / 'response.json'
        profile.base.write(path, self.data)
        with self.assertRaises(ValueError):
            profile.export(self.work, [path], self.root / 'out')

    def test_classification_pending_blocks_profile_export(self):
        self.data['claims'][0]['decision'].update(
            classification_status='pending', ambiguity_note='Требуется смысловое решение')
        path = self.root / 'response.json'
        profile.base.write(path, self.data)
        _, stats = profile.check(self.work, path)
        self.assertEqual(stats['pending_classifications'], 1)
        self.assertEqual(stats['pending_claims'] + stats['pending_blocks'], 0)
        with self.assertRaises(ValueError):
            profile.export(self.work, [path], self.root / 'out')


if __name__ == '__main__':
    unittest.main()
