"""Exercise the real extraction contract with mocked model subprocesses only."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('extraction_worker_under_test', Path(__file__).with_name('worker.py'))
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class ExtractionRetryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        source = self.repo / 'source.md'
        source.write_text('<!-- pdf_page: 1 -->Мы снизили выбросы.')
        self.report = {'report_id': 'RETRY', 'repository_path': 'source.md',
                       'packaged_md_sha256': worker.base.sha(source)}
        self.calls = []

    def fake_run(self, args, **kwargs):
        self.calls.append((args, kwargs))
        scratch = Path(args[args.index('-C') + 1])
        batch = worker.base.read(scratch / 'batch.json')
        bid = batch['target_block_ids'][0]
        exact = 'Мы снизили выбросы.'
        statement = exact if len(self.calls) in self.valid_attempts else 'Переписанное моделью заявление.'
        data = {
            'schema_version': worker.base.VERSION, 'source_sha256': batch['source_sha256'],
            'batch_id': batch['batch_id'], 'reviewer': 'Mocked model; actual project validator',
            'claims': [{'id': 'c1', 'type': 'результат', 'block': 'E', 'topic': 'климат',
                        'block2': '', 'statement': statement, 'source_kind': 'text',
                        'source_status': 'md_only', 'quantitative': False, 'reason': 'Совершённое действие',
                        'evidence': [{'block_id': bid, 'quote': exact, 'role': 'statement'}],
                        'decision': {'inclusion_rule': 'I1', 'classification_rule': 'E1',
                                     'subject': 'Мы', 'proposition': 'Снизили выбросы', 'esg_object': 'Выбросы',
                                     'source_refs': ['ESRS2023', 'GRI2021'], 'secondary_blocks': [],
                                     'classification_status': 'resolved', 'ambiguity_note': ''}}],
            'coverage': [{'block_id': bid, 'status': 'extracted', 'reason': 'Самостоятельное заявление',
                          'claim_ids': ['c1']}]}
        worker.base.write(scratch / 'response.json', data)
        return None

    def execute(self, valid_attempts, clock=(100, 100, 103), timeout=900):
        self.valid_attempts = valid_attempts
        with patch.object(worker, 'REPO', self.repo), \
                patch.object(worker.Path, 'home', return_value=self.root), \
                patch.object(worker.subprocess, 'run', side_effect=self.fake_run), \
                patch.object(worker.time, 'monotonic', side_effect=clock):
            return worker.process(self.report, 1, batch_timeout=timeout)

    def cached(self, name):
        return list((self.root / '.local/state/sber-esg-worker').rglob(name))

    def test_invalid_then_valid_preserves_first_and_accepts_second(self):
        result = self.execute({2})
        self.assertEqual(result['status'], 'extracted')
        self.assertEqual(result['processed'], 1)
        self.assertEqual(len(self.calls), 2)
        invalid = self.cached('attempt-1-response.json')
        self.assertEqual(len(invalid), 1)
        self.assertEqual(worker.base.read(invalid[0])['claims'][0]['statement'], 'Переписанное моделью заявление.')
        error = worker.base.read(invalid[0].with_name('attempt-1-error.json'))
        self.assertEqual(error['error'], 'Statement отличается от точных цитат')
        self.assertEqual(error['response_sha256'], worker.base.sha(invalid[0]))
        accepted = [p for p in self.cached('RETRY_b0001.json') if p.parent.name == 'accepted']
        self.assertEqual(len(accepted), 1)
        self.assertEqual(worker.base.read(accepted[0])['claims'][0]['statement'], 'Мы снизили выбросы.')
        retry_prompt = self.calls[1][0][-1]
        self.assertIn(error['error'], retry_prompt)
        self.assertIn('previous_invalid_response.json', retry_prompt)
        self.assertIn('statement', retry_prompt)
        for name in ('esg_agent_v3_1.md', 'decision_rules_v3_1.json', 'taxonomy_v3_1.csv', 'batch.json'):
            self.assertIn(name, retry_prompt)

    def test_twice_invalid_rejects_and_preserves_both(self):
        result = self.execute(set(), timeout=10000)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['processed'], 0)
        self.assertEqual(result['rows'], [])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(self.cached('attempt-1-response.json')), 1)
        self.assertEqual(len(self.cached('attempt-2-response.json')), 1)
        self.assertEqual(len(self.cached('attempt-1-error.json')), 1)
        self.assertEqual(len(self.cached('attempt-2-error.json')), 1)
        accepted = [p for p in self.cached('RETRY_b0001.json') if p.parent.name == 'accepted']
        self.assertEqual(accepted, [])
        self.assertEqual(self.calls[0][1]['timeout'], 900)
        self.assertEqual(self.calls[1][1]['timeout'], 897)

    def test_exhausted_shared_budget_does_not_start_second_model(self):
        result = self.execute(set(), clock=(100, 100, 1001))
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.cached('attempt-1-response.json')), 1)
        self.assertEqual(self.cached('attempt-2-response.json'), [])
        self.assertFalse(any(p.parent.name == 'accepted' for p in self.cached('RETRY_b0001.json')))


if __name__ == '__main__':
    unittest.main()
