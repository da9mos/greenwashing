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
                        'presentation_quote': exact, 'presentation_block_id': bid,
                        'source_status': 'md_only', 'quantitative': False, 'reason': 'Совершённое действие',
                        'evidence': [{'block_id': bid, 'quote': exact, 'role': 'statement'}],
                        'decision': {'inclusion_rule': 'I1', 'classification_rule': 'E1',
                                     'subject': 'Мы', 'proposition': 'Снизили выбросы', 'esg_object': 'Выбросы',
                                     'source_refs': ['ESRS2023', 'GRI2021'], 'secondary_blocks': [],
                                     'classification_status': 'resolved', 'ambiguity_note': ''}}],
            'coverage': [{'block_id': bid, 'status': 'extracted', 'reason': 'Самостоятельное заявление',
                          'claim_ids': ['c1']}]}
        previous = scratch / 'previous_analytical_response.json'
        if previous.exists():
            data = worker.base.read(previous)
            for claim in data['claims']:
                claim.update(presentation_quote=exact, presentation_block_id=bid)
        if getattr(self, 'omit_presentation', False):
            data['claims'][0].pop('presentation_quote');data['claims'][0].pop('presentation_block_id')
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

    def seed_legacy(self):
        revision = worker.base.sha(worker.AGENT / 'agent/esg_agent_v3_1.md')[:10]
        cache = self.root / '.local/state/sber-esg-worker' / (
            f"RETRY-{self.report['packaged_md_sha256'][:10]}-{revision}")
        work = cache / 'prepared'
        manifest = worker.profile.prepare(self.repo / 'source.md', work, 'RETRY')
        scratch = cache / 'model'
        scratch.mkdir()
        batch = worker.base.read(work / manifest['batches'][0]['file'])
        worker.base.write(scratch / 'batch.json', batch)
        self.valid_attempts = {1}
        self.omit_presentation = True
        self.fake_run(['codex', '-C', str(scratch)])
        self.omit_presentation = False
        self.calls.clear()
        accepted = cache / 'accepted/RETRY_b0001.json'
        accepted.parent.mkdir()
        legacy = worker.base.read(scratch / 'response.json')
        legacy['migration_note'] = {'preserve': 'all unknown metadata too'}
        accepted.write_text(json.dumps(legacy, ensure_ascii=False, indent=4) + '\n')
        worker.profile.check(work, accepted)
        return accepted

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
        args = self.calls[0][0]
        self.assertIn('web_search="disabled"', args)
        scratch = Path(args[args.index('-C') + 1])
        policy = worker.base.read(scratch / 'decision_rules_v3_1.json')
        self.assertNotIn('sources', policy)
        self.assertNotIn('source_refs', policy['classification_rules']['E1'])
        taxonomy = (scratch / 'taxonomy_v3_1.csv').read_text(encoding='utf-8-sig')
        self.assertNotIn('источник', taxonomy.splitlines()[0])

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

    def test_new_model_response_cannot_use_legacy_missing_display_quote(self):
        self.omit_presentation = True
        result = self.execute({1, 2})
        self.assertEqual(result['status'], 'failed')
        self.assertFalse([p for p in self.cached('RETRY_b0001.json') if p.parent.name == 'accepted'])
        error = worker.base.read(self.cached('attempt-2-error.json')[0])
        self.assertIn('presentation_quote', error['error'])

    def test_exhausted_shared_budget_does_not_start_second_model(self):
        result = self.execute(set(), clock=(100, 100, 1001))
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.cached('attempt-1-response.json')), 1)
        self.assertEqual(self.cached('attempt-2-response.json'), [])
        self.assertFalse(any(p.parent.name == 'accepted' for p in self.cached('RETRY_b0001.json')))

    def test_legacy_adds_only_quotes_and_archives_exact_original(self):
        accepted = self.seed_legacy()
        original = accepted.read_bytes()
        original_data = worker.base.read(accepted)
        # The non-normalizing profile path must serve the legacy repair.
        with patch.object(worker, 'review', side_effect=AssertionError('Repair must not normalize analytics')):
            result = self.execute({1})
        self.assertEqual(result['processed'], 1)
        self.assertEqual(len(self.calls), 1)
        self.assertIn('previous_analytical_response.json', self.calls[0][0][-1])
        archived = self.cached('previous_accepted.json')
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0].read_bytes(), original)
        revised = worker.base.read(accepted)
        self.assertEqual(revised['coverage'], original_data['coverage'])
        self.assertEqual(revised['migration_note'], original_data['migration_note'])
        self.assertEqual(revised['claims'][0]['presentation_quote'], 'Мы снизили выбросы.')
        stripped = copy.deepcopy(revised)
        for claim in stripped['claims']:
            claim.pop('presentation_quote');claim.pop('presentation_block_id')
        self.assertEqual(stripped, original_data)
        provenance = worker.base.read(self.cached('provenance.json')[0])
        self.assertEqual(provenance['original_sha256'], worker.base.sha(archived[0]))
        self.assertEqual(provenance['new_sha256'], worker.base.sha(accepted))

    def test_legacy_class_change_or_claim_removal_keeps_original_accepted(self):
        accepted = self.seed_legacy()
        original = accepted.read_bytes()
        fake_run = self.fake_run
        for mutation in ('class', 'delete'):
            self.calls.clear()
            def changed(args, **kwargs):
                fake_run(args, **kwargs)
                scratch = Path(args[args.index('-C') + 1])
                data = worker.base.read(scratch / 'response.json')
                if mutation == 'class':
                    data['claims'][0]['type'] = 'декларация'
                else:
                    data['claims'] = []
                    data['coverage'][0].update(status='pending', claim_ids=[])
                worker.base.write(scratch / 'response.json', data)
            self.fake_run = changed
            with self.subTest(mutation=mutation):
                result = self.execute({1, 2})
                self.assertEqual(accepted.read_bytes(), original)
                self.assertEqual(len(self.calls), 2)
                self.assertIn('требует разбора', result['reason'])
        self.assertEqual(self.cached('accepted_revision.json'), [])
        self.assertEqual(len(self.cached('attempt-2-error.json')), 2)


if __name__ == '__main__':
    unittest.main()
