import importlib.util
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('corpus_controller', Path(__file__).with_name('run_corpus.py'))
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


class IntegrityTests(unittest.TestCase):
    def test_unfinished_batches_cannot_be_complete(self):
        self.assertEqual(controller.extraction_status(10, 9, 0, []), 'Частичное извлечение')

    def test_pending_pdf_is_visible_after_all_batches(self):
        self.assertIn('открытые блоки/PDF', controller.extraction_status(10, 10, 1, []))

    def test_fully_covered_md_does_not_claim_external_verification(self):
        self.assertIn('фактчекинг открыты', controller.extraction_status(10, 10, 0, []))

    def test_invalid_response_blocks_ready_status(self):
        self.assertEqual(controller.extraction_status(10, 10, 0, [{}]), 'Требуется разбор отклонённых ответов')

    def test_same_local_ids_in_different_batches_preserve_both_claims(self):
        def sample(batch):
            return {'batch_id': batch, 'claims': [{'id': 'c001', 'statement': 'exact quote'}],
                    'coverage': [{'claim_ids': ['c001']}]}
        first, second = sample('report_b1'), sample('report_b2')
        a, trace = controller.canonical_batch(first)
        b, _ = controller.canonical_batch(second)
        self.assertNotEqual(a['claims'][0]['id'], b['claims'][0]['id'])
        self.assertEqual(a['coverage'][0]['claim_ids'], [a['claims'][0]['id']])
        self.assertEqual(first['claims'][0]['id'], 'c001')
        self.assertEqual(a['claims'][0]['statement'], first['claims'][0]['statement'])
        self.assertEqual(trace[0]['original_id'], 'c001')

    def test_md_only_pending_classification_prevents_ready_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            accepted = root / 'cache/accepted'
            accepted.mkdir(parents=True)
            (accepted / 'report_b1.json').write_text('{}')
            (root / 'cache/prepared').mkdir()
            report = {'report_id': 'report', 'repository_path': 'source.md',
                      'packaged_md_sha256': 'hash', 'company': 'Company',
                      'company_id': 'company', 'physical_pages': 1}
            manifest = {'source_sha256': 'hash', 'prompt_sha256': 'prompt',
                        'batches': [{'id': 'report_b1'}]}
            data = {'batch_id': 'report_b1', 'claims': [
                {'id': 'c1', 'statement': 'Точная цитата', 'block': 'E', 'type': 'результат', 'source_status': 'md_only',
                 'decision': {'classification_status': 'pending'}}],
                'coverage': [{'block_id': 'b1', 'status': 'extracted', 'claim_ids': ['c1']}]}
            stats = {'pending_claims': 0, 'pending_blocks': 0, 'pending_classifications': 1}
            with patch.object(controller, 'cache_for', return_value=root / 'cache'), \
                    patch.object(controller, 'OUTPUT', root / 'output'), \
                    patch.object(controller.worker.base, 'sha', return_value='hash'), \
                    patch.object(controller.worker.base, 'workspace', return_value=(manifest, set())), \
                    patch.object(controller.worker.profile, 'policy_for'), \
                    patch.object(controller.worker.profile, 'check', return_value=(data, stats)):
                summary, _ = controller.inspect_report(report)
            self.assertEqual(summary['accepted_batches'], summary['total_batches'])
            self.assertEqual(summary['pending_claims'] + summary['pending_blocks'], 0)
            self.assertEqual(summary['pending_classifications'], 1)
            self.assertIn('неоднозначные классификации', summary['status'])
            self.assertNotIn('Охват MD заявлен', summary['status'])

    def test_pending_classifications_reach_totals_csv_and_company_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = {'report_id': 'report', 'company_id': 'company', 'company': 'Company'}
            summary = {**report, 'pages': 1, 'total_batches': 1, 'accepted_batches': 1,
                       'candidate_claims': 1, 'pending_blocks': 0, 'pending_claims': 0,
                       'pending_classifications': 2, 'status': 'Требуется классификация',
                       'pdf_review': 'Открыта', 'factcheck': 'Открыт'}
            with patch.object(controller, 'HERE', root), \
                    patch.object(controller, 'OUTPUT', root / 'output'), \
                    patch.object(controller, 'registry', return_value=[report]), \
                    patch.object(controller, 'inspect_report', return_value=(summary, {})):
                result = controller.snapshot()
            self.assertEqual(result['totals']['pending_classifications'], 2)
            with (root / 'Сводка_прогона.csv').open(encoding='utf-8-sig', newline='') as stream:
                row = next(csv.DictReader(stream, delimiter=';'))
            self.assertEqual(row['pending_classifications'], '2')
            markdown = (root / 'output/Company/Сводка_компании.md').read_text()
            self.assertIn('Неоднозначных классификаций', markdown)
            self.assertIn('| 0 | 0 | 2 |', markdown)

    def test_old_complete_result_without_mandatory_risk_checks_is_not_current(self):
        packet = controller.worker.base.read(controller.worker.FACT / 'examples/synthetic_response.json')
        self.assertTrue(controller.current_research_complete({'result': {'status': 'complete', 'packet': packet}, 'verification_policy_sha256': controller.verification_policy_sha256()}))
        packet.pop('risk_checks')
        self.assertFalse(controller.current_research_complete({'result': {'status': 'complete', 'packet': packet}, 'verification_policy_sha256': controller.verification_policy_sha256()}))

    def test_external_research_can_start_from_partial_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = {'report_id': 'report', 'company': 'Company', 'packaged_md_sha256': 'hash'}
            claim = {'id': 'batch::c1', 'statement': 'Точная цитата'}
            summary = {'accepted_batches': 1, 'total_batches': 100}
            packet = controller.worker.base.read(controller.worker.FACT / 'examples/synthetic_response.json')
            result = {'status': 'complete', 'packet': packet}
            with patch.object(controller, 'OUTPUT', root / 'output'), \
                    patch.object(controller, 'CONTROL', root / 'control'), \
                    patch.object(controller, 'registry', return_value=[report]), \
                    patch.object(controller, 'inspect_report', return_value=(summary, {'claims': [claim]})), \
                    patch.object(controller, 'source_review_for', return_value=None), \
                    patch.object(controller, 'snapshot'), \
                    patch.object(controller.worker, 'search_claim', return_value=result) as search:
                self.assertTrue(controller.research_step())
                search.assert_called_once()
                self.assertTrue(controller.research_path(report, claim).exists())
                self.assertFalse(controller.research_step())
                self.assertEqual(search.call_count, 1)


if __name__ == '__main__':
    unittest.main()
