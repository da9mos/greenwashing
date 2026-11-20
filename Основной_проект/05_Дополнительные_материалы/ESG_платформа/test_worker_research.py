"""Real ledger integration, with explicit UNIT FIXTURES for subprocess/search.

No model, SSH or actual external research is invoked. HOME is temporary.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import worker


class ProjectResearchWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='esg-worker-unit-fixtures-')
        self.addCleanup(self.tmp.cleanup)
        self.enterContext(patch.dict(os.environ, {'HOME': self.tmp.name}))
        self.fixture = json.loads((worker.FACT / 'examples/synthetic_response.json').read_text())
        self.job = {
            'report': {'report_id': 'UNIT-FIXTURE-REPORT', 'packaged_md_sha256': 'unit-fixture-md-hash'},
            'claim': {'id': 'unit-fixture-original-id', 'statement': 'Emissions 10 tonnes',
                      'entity_scope': 'Test Co', 'period': '2023', 'boundary': 'one plant'},
        }

    def model(self, *, complete=True, verdict='insufficient_evidence', revision=None,
              events=None, wrong_hash=False, self_ingest=False, conflicting_response=False):
        """Mock model output, binding a synthetic fixture to the actual created plan."""
        if events is None:
            events = [{'type': 'item.completed', 'item': {'id': 'unit-fixture-search',
                       'type': 'web_search', 'status': 'completed',
                       'action': {'type': 'search', 'queries': ['UNIT FIXTURE, NOT LIVE RESEARCH']}}}]

        def run(args, **kwargs):
            self.assertEqual(args[0:3], ['codex', '--search', 'exec'])
            self.assertNotIn('synthetic_response', args[-1])
            root = Path(args[args.index('-C') + 1])
            plan = worker.factcheck.load(root / 'run')
            old = worker.factcheck.results(root / 'run', plan).get('C000001')
            expected_revision = old['revision'] + 1 if old else 1
            self.assertIn(f'revision={expected_revision}', args[-1])
            self.assertEqual((root / 'contract.md').read_text(), (worker.FACT / 'README.md').read_text())
            packet = copy.deepcopy(self.fixture)
            packet.update(source_sha256='wrong-unit-hash' if wrong_hash else plan['source_sha256'],
                          claim_id=plan['claims'][0]['id'], quote=plan['claims'][0]['quote'],
                          revision=expected_revision if revision is None else revision,
                          research_status='complete' if complete else 'partial',
                          verdict=verdict, reason='UNIT FIXTURE: mocked subprocess, not actual research')
            if verdict not in {'true', 'false', 'partial'}:
                packet['aspects'][0]['status'] = 'unresolved'
            worker.base.write(root / 'response.json', packet)
            if self_ingest:
                # The project agent contract authorizes its own ingest before returning.
                worker.factcheck.ingest(root / 'run', root / 'response.json')
                if conflicting_response:
                    # Same claim/revision, valid schema, different semantic content.
                    packet['reason'] = 'UNIT FIXTURE CONFLICT: response differs from accepted checkpoint'
                    worker.base.write(root / 'response.json', packet)
            for event in events:
                kwargs['stdout'].write(json.dumps(event) + '\n')
            kwargs['stdout'].flush()
            return subprocess.CompletedProcess(args, 0)
        return run

    def invoke(self, **options):
        with patch.object(worker.subprocess, 'run', side_effect=self.model(**options)):
            return worker.search_claim(self.job)

    def assert_rejected(self, result, message):
        self.assertEqual(result['status'], 'failed')
        run = Path(result['research_run'])
        self.assertEqual(worker.factcheck.results(run, worker.factcheck.load(run)), {})
        attempts = list((run.parent / 'attempts').iterdir())
        self.assertEqual(len(attempts), 1)
        error = json.loads((attempts[0] / 'error.json').read_text())
        self.assertIn(message, error['message'])
        self.assertTrue((attempts[0] / 'native_events.jsonl').is_file())
        return attempts[0]

    def test_accepted_packet_history_and_native_journal_survive_return(self):
        result = self.invoke()
        self.assertEqual(result['status'], 'complete')
        run = Path(result['research_run'])
        self.assertTrue(run.is_relative_to(Path(self.tmp.name)))
        accepted = worker.factcheck.results(run, worker.factcheck.load(run))['C000001']
        self.assertEqual(accepted, result['packet'])
        self.assertEqual(accepted['revision'], 1)
        self.assertTrue((run / 'results/C000001.r000001.sha256').is_file())
        attempt = next((run.parent / 'attempts').iterdir())
        self.assertEqual(json.loads((attempt / 'response.json').read_text()), accepted)
        native = [json.loads(line) for line in (attempt / 'native_events.jsonl').read_text().splitlines()]
        self.assertEqual(native[0]['item']['id'], 'unit-fixture-search')
        self.assertEqual(worker.factcheck.queue(run), [])

    def test_completed_result_does_not_launch_model_again(self):
        first = self.invoke()
        root = Path(first['research_run']).parent
        before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        with patch.object(worker.subprocess, 'run', side_effect=AssertionError('model relaunched')):
            second = worker.search_claim(self.job)
        self.assertEqual(first['packet'], second['packet'])
        self.assertEqual(first['research_run'], second['research_run'])
        after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_text_mention_without_completed_web_search_event_is_rejected(self):
        result = self.invoke(events=[{'type': 'item.completed', 'item': {
            'type': 'agent_message', 'text': 'UNIT FIXTURE claims web_search happened'}}])
        self.assert_rejected(result, 'Событие внешнего веб-поиска не зафиксировано')

    def test_categorical_fixture_without_incoming_source_review_is_rejected(self):
        result = self.invoke(verdict='true')
        attempt = self.assert_rejected(result, 'Категорический вывод без отдельной проверки')
        self.assertEqual(json.loads((attempt / 'response.json').read_text())['source_review']['status'], 'verified')

    def test_partial_retry_uses_next_revision_and_preserves_first_history(self):
        first = self.invoke(complete=False, verdict='not_verifiable')
        self.assertEqual(first['status'], 'partial')
        run = Path(first['research_run'])
        first_history = (run / 'results/C000001.r000001.json').read_bytes()
        first_journal = next((run.parent / 'attempts').glob('*/native_events.jsonl'))
        first_journal_bytes = first_journal.read_bytes()
        second = self.invoke()
        self.assertEqual(second['research_run'], first['research_run'])
        self.assertEqual(second['packet']['revision'], 2)
        self.assertEqual((run / 'results/C000001.r000001.json').read_bytes(), first_history)
        self.assertEqual(first_journal.read_bytes(), first_journal_bytes)
        self.assertEqual(len(list((run.parent / 'attempts').iterdir())), 2)
        self.assertEqual(worker.factcheck.results(run, worker.factcheck.load(run))['C000001']['revision'], 2)

    def test_wrong_revision_and_wrong_plan_hash_cannot_be_ingested(self):
        for tag, options, message in [('revision', {'revision': 2}, 'неверную ревизию'),
                                      ('hash', {'wrong_hash': True}, 'wrong input hash')]:
            with self.subTest(tag=tag):
                self.job['report']['report_id'] = 'UNIT-FIXTURE-' + tag
                self.assert_rejected(self.invoke(**options), message)

    def test_null_incoming_review_fails_closed_instead_of_crashing(self):
        self.job['source_review'] = None
        self.assert_rejected(self.invoke(verdict='true'), 'Категорический вывод без отдельной проверки')

    def test_malformed_native_event_fails_closed_instead_of_crashing(self):
        self.assert_rejected(self.invoke(events=[{'type': 'item.completed', 'item': None}]),
                             'Событие внешнего веб-поиска не зафиксировано')


    def test_model_self_ingest_is_accepted_once_without_overwriting_history(self):
        with patch.object(worker.factcheck, 'ingest', wraps=worker.factcheck.ingest) as ingest:
            result = self.invoke(complete=False, verdict='not_verifiable', self_ingest=True)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(ingest.call_count, 1, 'Only the project agent should ingest the identical packet')
        run = Path(result['research_run'])
        self.assertEqual(len(list((run / 'results').glob('*.json'))), 1)
        accepted = worker.factcheck.results(run, worker.factcheck.load(run))['C000001']
        self.assertEqual(accepted, result['packet'])
        self.assertEqual(accepted['revision'], 1)
        attempt = next((run.parent / 'attempts').iterdir())
        self.assertEqual(json.loads((attempt / 'response.json').read_text()), accepted)
        self.assertTrue((attempt / 'native_events.jsonl').is_file())
        self.assertFalse((attempt / 'error.json').exists())

    def test_unreviewed_categorical_checkpoint_cannot_bypass_gate_via_cache(self):
        # Agent ingests true, then the outer gate correctly rejects absent incoming PDF review.
        rejected = self.invoke(verdict='true', self_ingest=True)
        self.assertEqual(rejected['status'], 'failed')
        run = Path(rejected['research_run'])
        r1_path = run / 'results/C000001.r000001.json'
        r1_bytes = r1_path.read_bytes()
        r1 = worker.factcheck.results(run, worker.factcheck.load(run))['C000001']
        self.assertEqual(r1['verdict'], 'true')
        self.assertNotIn('source_review', self.job)
        # A later call must research revision 2 rather than returning the unreviewed cached true.
        with patch.object(worker.subprocess, 'run', side_effect=self.model(verdict='not_verifiable')) as model:
            corrected = worker.search_claim(self.job)
        model.assert_called_once()
        self.assertEqual(corrected['research_run'], rejected['research_run'])
        self.assertEqual(corrected['status'], 'complete')
        self.assertEqual(corrected['packet']['verdict'], 'not_verifiable')
        self.assertEqual(corrected['packet']['revision'], 2)
        self.assertEqual(r1_path.read_bytes(), r1_bytes)
        self.assertEqual(len(list((run / 'results').glob('*.json'))), 2)
        latest = worker.factcheck.results(run, worker.factcheck.load(run))['C000001']
        self.assertEqual(latest, corrected['packet'])
        attempts = sorted((run.parent / 'attempts').iterdir())
        self.assertEqual(len(attempts), 2)
        self.assertTrue(all((attempt / 'native_events.jsonl').is_file() for attempt in attempts))
        self.assertEqual(json.loads((attempts[1] / 'response.json').read_text()), latest)

    def test_model_self_ingest_conflicting_same_revision_is_rejected(self):
        result = self.invoke(complete=False, verdict='not_verifiable',
                             self_ingest=True, conflicting_response=True)
        self.assertEqual(result['status'], 'failed')
        run = Path(result['research_run'])
        self.assertEqual(len(list((run / 'results').glob('*.json'))), 1)
        accepted = worker.factcheck.results(run, worker.factcheck.load(run))['C000001']
        self.assertEqual(accepted['revision'], 1)
        self.assertNotIn('CONFLICT', accepted['reason'])
        attempt = next((run.parent / 'attempts').iterdir())
        response = json.loads((attempt / 'response.json').read_text())
        self.assertIn('CONFLICT', response['reason'])
        self.assertNotEqual(response, accepted)
        error = json.loads((attempt / 'error.json').read_text())
        self.assertEqual(error['type'], 'ValueError')
        self.assertTrue(error['message'])
        self.assertTrue((attempt / 'native_events.jsonl').is_file())


if __name__ == '__main__':
    unittest.main()
