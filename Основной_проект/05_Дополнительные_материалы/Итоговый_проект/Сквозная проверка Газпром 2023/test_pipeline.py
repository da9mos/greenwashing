import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline import audit_quote, display_statement, evidence_verdict, load_md, normalize


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 18)
        self.dimensions = dict(entity="завод", metric="погибшие", period="2023", unit="человек", boundary="работники")
        self.proof = {
            **self.dimensions, "url": "https://example.org/report", "quote": "Сведения из акта",
            "locator": "с. 4", "publication_date": "2024-01-01", "reviewed": True,
            "independent": True, "original_source": True, "relation": "supports",
        }

    def part(self, *items):
        return {**self.dimensions, "evidence": list(items)}

    def test_supported_and_contradicted_parts(self):
        contrary = {**self.proof, "relation": "contradicts"}
        self.assertEqual(evidence_verdict([self.part(self.proof)], self.today), "Подтверждено")
        self.assertEqual(evidence_verdict([self.part(contrary)], self.today), "Опровергнуто")
        self.assertEqual(evidence_verdict([self.part(self.proof), self.part(contrary)], self.today),
                         "Частично подтверждено")
        self.assertEqual(evidence_verdict([self.part(self.proof, contrary)], self.today), "Недостаточно данных")

    def test_scope_metric_or_independence_mismatch(self):
        for change in [{"boundary": "все"}, {"metric": "пострадавшие"}, {"independent": False},
                       {"original_source": False}, {"publication_date": "2027-01-01"}]:
            with self.subTest(change=change):
                self.assertEqual(evidence_verdict([self.part({**self.proof, **change})], self.today),
                                 "Недостаточно данных")

    def test_missing_part_and_future_deadline(self):
        self.assertEqual(evidence_verdict([self.part(self.proof), self.part()], self.today), "Недостаточно данных")
        self.assertEqual(evidence_verdict([], self.today, "2027-01-01"), "Срок ещё не наступил")
        self.assertEqual(evidence_verdict([], self.today, "2025-01-01"), "Недостаточно данных")
        self.assertEqual(evidence_verdict([], self.today, has_criterion=False), "Нет проверяемого критерия")

    def test_ocr_stays_provisional(self):
        self.assertEqual(audit_quote("85,06", ["", "", "85,06"]), "Совпало по OCR. Нужна визуальная сверка")
        self.assertEqual(audit_quote("85,06", ["85,60", ""]), "Нужна визуальная сверка PDF")
        self.assertEqual(normalize("нару-\n  шения"), "нарушения")

    def test_duplicate_physical_page_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "report.md"
            path.write_text("<!-- pdf_page: 1 --><!-- pdf_page: 1 -->", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unique and contiguous"):
                load_md(path)

    def test_table_does_not_turn_dash_into_zero(self):
        statement = display_statement({"page": 13}, "| 1. | Выбросы, т | Завод | — | 0 | Цель достигнута |")
        self.assertIn("Базовый показатель — —.", statement)
        self.assertIn("В 2023 г. — 0.", statement)


if __name__ == "__main__":
    unittest.main()
