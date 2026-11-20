import importlib.util
from pathlib import Path
import unittest

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


if __name__ == '__main__':
    unittest.main()
