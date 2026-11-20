"""Guard against promoting incomplete or unsupported review conclusions."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from build_review_v2 import apply_review


class ReviewV2Tests(unittest.TestCase):
    def setUp(self):
        self.row = {
            'target_id': 'T-TEST-001', 'company_id': 'TEST',
            'status': 'нет данных', 'comment': 'Исходная проверка',
            'value_2023': '10', 'value_2024': '11', 'value_2025': '',
            'page_2023': '1', 'page_2024': '2', 'page_2025': '',
        }
        self.observation = {
            'year': 2025, 'value': 12, 'comparison_valid': True,
            'report_id': 'TEST-2025-ОУР', 'page': 3,
            'quote': 'В 2025 году показатель составил 12 тонн.',
            'source_url': 'https://drive.google.com/file/d/test-report/view',
        }

    def test_unfinished_review_cannot_change_status_or_series(self):
        for marker in ({'review_complete': False}, {'review_status': 'pending'}, {}):
            with self.subTest(marker=marker):
                review = dict(marker, new_status='выполнена',
                              observations=[self.observation], reason='Предварительно')
                result = apply_review(self.row, review)
                self.assertEqual(result['status'], self.row['status'])
                for field in ('value_2023', 'value_2024', 'value_2025',
                              'page_2023', 'page_2024', 'page_2025', 'comment'):
                    self.assertEqual(result[field], self.row[field])
                self.assertEqual(result['review_status'], 'не завершена')

    def test_noncomparable_observations_never_replace_annual_values(self):
        observations = [dict(self.observation, year=year, value=999,
                             page=99, comparison_valid=False)
                        for year in (2023, 2024, 2025)]
        result = apply_review(self.row, {'review_complete': True,
                              'new_status': 'нет данных', 'observations': observations})
        for year in (2023, 2024, 2025):
            for prefix in ('value_', 'page_'):
                self.assertEqual(result[prefix + str(year)], self.row[prefix + str(year)])

    def test_status_change_without_observations_is_error(self):
        for observations in ([],):
            with self.assertRaises(ValueError):
                apply_review(self.row, {'review_complete': True,
                             'new_status': 'выполнена', 'observations': observations})

    def test_empty_observation_is_not_evidence_for_status_change(self):
        with self.assertRaises(ValueError):
            apply_review(self.row, {'review_complete': True,
                         'new_status': 'выполнена', 'observations': [{}]})

    def test_completed_supported_result_copies_only_matching_year(self):
        original = copy.deepcopy(self.row)
        review = {'review_complete': True, 'new_status': 'выполнена',
                  'observations': [self.observation], 'reason': 'Найден сопоставимый результат'}
        result = apply_review(self.row, review)
        self.assertEqual(result['status'], 'выполнена')
        self.assertEqual(result['old_status'], 'нет данных')
        self.assertEqual(result['review_status'], 'завершена')
        self.assertEqual(result['value_2025'], 12)
        self.assertEqual(result['page_2025'], 3)
        self.assertEqual(result['value_2023'], '10')
        self.assertEqual(result['value_2024'], '11')
        self.assertEqual(self.row, original)


if __name__ == '__main__':
    unittest.main()
