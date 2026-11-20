"""Semantic regressions discovered in the actual review-v2 builder/data.

All build tests use an isolated miniature corpus; production artifacts are read-only.
"""
import contextlib
import csv
import io
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import build_review_v2 as builder


class ReviewV3Tests(unittest.TestCase):
    def row(self):
        return {'target_id': 'T-TEST-001', 'company_id': 'TEST', 'status': 'нет данных',
                'comment': 'Исходная запись', 'value_2023': '1', 'value_2024': '',
                'value_2025': '', 'page_2023': '1', 'page_2024': '', 'page_2025': ''}

    def observation(self, **changes):
        o = {'year': 2025, 'value': 5, 'comparison_valid': True,
             'report_id': 'TEST-2025-ОУР', 'page': 1,
             'quote': 'В 2025 году показатель составил 5, ранее 4; травм 0.',
             'source_url': 'https://drive.google.com/file/d/drive-test/view'}
        o.update(changes)
        return o

    def review(self, **changes):
        r = {'target_id': 'T-TEST-001', 'review_complete': True,
             'new_status': 'нет данных', 'observations': [self.observation()]}
        r.update(changes)
        return r

    def build_fixture(self, reviews=None, stale_error=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / 'pipeline'
        source = root / 'data/review_v2'
        source.mkdir(parents=True)
        (root / 'data/out').mkdir(parents=True)
        (root / 'data/pages').mkdir(parents=True)
        (root / 'llm/nikita_dynamics/v2').mkdir(parents=True)
        registry = root.parent / '01_итерация_1_сбор_данных/выборка_30/reports.csv'
        registry.parent.mkdir(parents=True)
        self.write_csv(root/'data/out/metrics_dynamics.csv', [self.row()])
        self.write_csv(registry, [{'report_id': 'TEST-2025-ОУР', 'company_id': 'TEST',
                                  'year': '2025', 'drive_id': 'drive-test'}])
        (root/'data/pages/TEST-2025-ОУР.jsonl').write_text(json.dumps({
            'report_id':'TEST-2025-ОУР','page':1,
            'text':self.observation()['quote']},ensure_ascii=False)+'\n')
        for group, data in [('A', reviews if reviews is not None else [self.review()]), ('B', [])]:
            (root/f'llm/nikita_dynamics/v2/review_{group}.json').write_text(
                json.dumps({'reviews':data},ensure_ascii=False))
        output = root/'output'
        if stale_error:
            output.mkdir();(output/'validation_errors.json').write_text('["old failed run"]')
        return root, output

    @staticmethod
    def write_csv(path, rows):
        with path.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,list(rows[0]),delimiter=';');w.writeheader();w.writerows(rows)

    def run_build(self, root, output):
        with patch.object(builder, 'P', root), contextlib.redirect_stdout(io.StringIO()):
            return builder.build(output)

    def test_actual_zero_reported_value_survives_export(self):
        # T-CHMF-003 in actual review_A has reported_value=0 and value=null.
        root, output=self.build_fixture([self.review(observations=[
            self.observation(value=None, reported_value=0, comparison_valid=False)])])
        self.run_build(root,output)
        with (output/'evidence_review.csv').open(encoding='utf-8-sig') as f:
            evidence=list(csv.DictReader(f,delimiter=';'))
        self.assertEqual(evidence[0]['reported_value'],'0')

    def test_conflicting_comparable_values_same_year_are_rejected(self):
        with self.assertRaises(ValueError):
            builder.apply_review(self.row(),self.review(observations=[
                self.observation(value=4),self.observation(value=5)]))

    def test_identical_same_year_repeated_evidence_is_allowed(self):
        result=builder.apply_review(self.row(),self.review(observations=[
            self.observation(value=5),self.observation(value=5)]))
        self.assertEqual(result['value_2025'],5)

    def test_unknown_target_id_must_not_disappear_silently(self):
        root,output=self.build_fixture([self.review(target_id='T-TYPO-999')])
        with self.assertRaises(ValueError):self.run_build(root,output)

    def test_nonfinite_and_non_numeric_comparable_values_are_rejected(self):
        for value in (math.nan,math.inf,-math.inf,True,'5','not measured'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                builder.apply_review(self.row(),self.review(observations=[self.observation(value=value)]))

    def test_comparison_valid_requires_boolean_when_present(self):
        for marker in ('true','false',1,0):
            with self.subTest(marker=marker),self.assertRaises(ValueError):
                builder.apply_review(self.row(),self.review(observations=[
                    self.observation(comparison_valid=marker)]))

    def test_measurement_year_is_not_rolled_into_assessment_year(self):
        # PHOR002 is assessed in2025 using a2024 measurement, not a new2025 survey.
        result=builder.apply_review(self.row(),self.review(assessment_year=2025,
            measurement_year=2024,observations=[self.observation(year=2024,value=76,
                quote='По результатам измерения 2024 года показатель составил 76%.')]))
        self.assertEqual(result['measurement_year'],2024)
        self.assertEqual(result['assessment_year'],2025)
        self.assertEqual(result['value_2024'],76)
        self.assertEqual(result['value_2025'],'')

    def test_comparable_number_missing_from_quote_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'not supported by quote'):
            builder.apply_review(self.row(), self.review(observations=[
                self.observation(value=9999)]))

    def test_explicit_rasp_annual_clear_preserves_other_years_and_status(self):
        row=dict(self.row(), target_id='T-RASP-001', status='несопоставимая база',
                 old_status='нет данных', value_2024='59', page_2024='30',
                 value_2025='56', page_2025='71')
        patch={'reason': 'Показатель2025 рассчитан по иной методике; убрать из сопоставимого ряда',
               'observations': [self.observation(value=None, comparison_valid=False)],
               'clear_annual_values': [2025]}
        result=builder.apply_audit_patch(row,patch)
        self.assertEqual(result['value_2025'],'')
        self.assertEqual(result['page_2025'],'')
        for field in ('value_2023','page_2023','value_2024','page_2024',
                      'status','old_status','target_id'):
            self.assertEqual(result[field],row[field])
        self.assertEqual(row['value_2025'],'56')

    def test_original_old_status_survives_reapplication(self):
        row=dict(self.row(),status='выполнена',old_status='нет данных')
        result=builder.apply_review(row,self.review(new_status='выполнена'))
        self.assertEqual(result['old_status'],'нет данных')

    def test_manifest_hashes_all_consumed_base_inputs_and_fallback_page(self):
        root,output=self.build_fixture()
        result=self.run_build(root,output)
        keys=list(result['inputs_sha256'])
        for suffix in ('data/out/metrics_dynamics.csv','reports.csv','data/pages/TEST-2025-ОУР.jsonl'):
            with self.subTest(input=suffix):self.assertTrue(any(k.endswith(suffix) for k in keys),keys)

    def test_successful_rebuild_removes_stale_error_file(self):
        root,output=self.build_fixture(stale_error=True)
        result=self.run_build(root,output)
        self.assertEqual(result['state'],'passed')
        self.assertFalse((output/'validation_errors.json').exists())

    def test_failed_quote_cannot_leave_passed_marker(self):
        root,output=self.build_fixture([self.review(observations=[
            self.observation(quote='Цитата которой в первоисточнике совершенно нет')])])
        output.mkdir();(output/'validation_review.json').write_text('{"state":"passed"}')
        with self.assertRaises(ValueError):self.run_build(root,output)
        marker=json.loads((output/'validation_review.json').read_text())
        self.assertNotEqual(marker.get('state'),'passed')
        self.assertFalse((output/'metrics_dynamics.csv').exists())


if __name__=='__main__':unittest.main()
