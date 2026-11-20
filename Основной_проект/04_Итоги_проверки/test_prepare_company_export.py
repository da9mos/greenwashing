from pathlib import Path
import importlib.util
import unittest

spec = importlib.util.spec_from_file_location('company_export', Path(__file__).with_name('prepare_company_export.py'))
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class AgentInteroperabilityTests(unittest.TestCase):
    def record(self, page):
        return {'id': 'C000001', 'quote': 'Точная цитата',
                'original': {'statement': 'Точная цитата', 'type': 'результат', 'block': 'E', 'pdf_page': page},
                'research_status': 'complete',
                'assessment': {'verdict': 'insufficient_evidence', 'reason': 'Исследовано; сопоставимых данных нет.',
                               'sources': [{'url': 'https://example.org/unit-fixture'}]}}

    def test_native_fact_agent_pdf_page_survives_excel_adapter(self):
        report = {'report_id': 'UNIT', 'physical_pages': 84, 'pdf_source_url': 'https://example.org/unit-pdf'}
        row = exporter.display(self.record(14), report, 1)
        self.assertEqual(len(row), 6)
        self.assertIn('Страницы PDF 14', row[5])
        self.assertEqual(row[4], 'Недостаточно сопоставимых данных')

    def test_wrong_physical_page_is_not_silently_exported(self):
        report = {'report_id': 'UNIT', 'physical_pages': 84, 'pdf_source_url': 'https://example.org/unit-pdf'}
        with self.assertRaises(ValueError):
            exporter.display(self.record(85), report, 1)


if __name__ == '__main__':
    unittest.main()
