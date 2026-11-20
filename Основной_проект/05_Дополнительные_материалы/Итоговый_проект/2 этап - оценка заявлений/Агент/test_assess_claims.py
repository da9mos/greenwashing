import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from assess_claims import validate


class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.report = Path(self.temp.name) / "report.md"
        self.report.write_text("<!-- pdf_page: 1 -->Компания сократила выбросы на 5 %.<!-- pdf_page: 2 -->Другой текст.", encoding="utf-8")
        self.claim = dict(claim_id="TEST-2023-001", company="Тест", report_id="TEST-2023", pdf_page=1, printed_page=1, quote="Компания сократила выбросы на 5 %.", claim_type="результат", esg_block="E", verdict="недостаточно данных", reason="Независимых данных нет", limitation="Синтетический тест, не gold", source_url="https://example.org/report", assessment_method="synthetic_fixture", evidence=[], entity_scope="Тест", metric="выбросы", period="2023", boundary="вся компания", assessment_target="истинность результата")
        self.data = dict(schema_version="1.0", report_id="TEST-2023", company="Тест", source_sha256=hashlib.sha256(self.report.read_bytes()).hexdigest(), claims=[self.claim])

    def decisive(self):
        self.claim["verdict"] = "подтверждено"
        self.claim["evidence"] = [dict(entity_scope="Тест", metric="выбросы", period="2023", boundary="вся компания", assessment_target="истинность результата", source_url="https://example.org/fact", publication_date="2024-03-01", event_period="2023", quote="Снижение 5 %", locator="стр.1", independent=True, reviewed=True, relation="supports")]

    def test_open_assessment_valid(self):
        self.assertEqual(validate(self.data, self.report), [])

    def test_wrong_quote_rejected(self):
        self.claim["quote"] = "Компания сократила выбросы на 99 %."
        self.assertTrue(validate(self.data, self.report))

    def test_wrong_page_rejected(self):
        self.claim["pdf_page"] = 2
        self.assertTrue(validate(self.data, self.report))

    def test_changed_source_rejected(self):
        self.data["source_sha256"] = "wrong"
        self.assertTrue(validate(self.data, self.report))

    def test_missing_evidence_rejected(self):
        self.claim["verdict"] = "противоречит фактам"
        self.assertTrue(validate(self.data, self.report))

    def test_comparable_evidence_contract_accepted(self):
        self.decisive()
        self.assertEqual(validate(self.data, self.report), [])

    def test_wrong_evidence_dimensions_rejected(self):
        for field in ("entity_scope", "metric", "period", "boundary", "assessment_target"):
            with self.subTest(field=field):
                self.decisive()
                self.claim["evidence"][0][field] = "несопоставимо"
                self.assertTrue(validate(self.data, self.report))

    def test_self_report_is_not_independent(self):
        self.decisive()
        self.claim["evidence"][0]["independent"] = False
        self.assertTrue(validate(self.data, self.report))

    def test_unreviewed_evidence_rejected(self):
        self.decisive()
        self.claim["evidence"][0]["reviewed"] = False
        self.assertTrue(validate(self.data, self.report))

    def test_same_source_cannot_be_independent(self):
        self.decisive()
        self.claim["evidence"][0]["source_url"] = self.claim["source_url"] + "#page=5"
        self.assertTrue(validate(self.data, self.report))

    def test_invalid_calendar_date_rejected(self):
        self.decisive()
        self.claim["evidence"][0]["publication_date"] = "2024-99-99"
        self.assertTrue(validate(self.data, self.report))

    def test_result_not_declaration_when_evidence_missing(self):
        self.claim["verdict"] = "декларативно"
        self.assertTrue(validate(self.data, self.report))

    def test_duplicate_id_rejected(self):
        self.data["claims"].append(copy.deepcopy(self.claim))
        self.assertTrue(validate(self.data, self.report))

    def test_boolean_page_rejected(self):
        self.claim["pdf_page"] = True
        self.assertTrue(validate(self.data, self.report))

    def test_empty_quote_rejected(self):
        self.claim["quote"] = " "
        self.assertTrue(validate(self.data, self.report))

    def test_conflicting_evidence_rejected(self):
        self.decisive()
        evidence = copy.deepcopy(self.claim["evidence"][0])
        evidence["relation"] = "contradicts"
        self.claim["evidence"].append(evidence)
        self.assertTrue(validate(self.data, self.report))

    def test_nonobject_root_rejected(self):
        self.assertTrue(validate([], self.report))


if __name__ == "__main__":
    unittest.main(verbosity=2)
