"""Exercise queue, audit and evidence state with a temporary SQLite database."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app


class ReviewWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        path = root / "report.md"
        path.write_text("<!-- pdf_page: 1 -->\nЗаявление.")
        registry = {"REPORT": {"report_id": "REPORT", "repository_path": "report.md",
                               "packaged_md_sha256": app.sha256(path.read_bytes()).hexdigest(),
                               "physical_pages": 1, "visual_reference_count": 0}}
        self.enterContext(patch.multiple(app, DATA=root, STATE=root, REGISTRY=registry, PILOT={}))
        app.init()

    def test_audit_detects_changed_text(self):
        self.assertTrue(app.audit("REPORT")["hash"])
        (app.DATA / "report.md").write_text("<!-- pdf_page: 2 -->\nЗаявление.")
        result = app.audit("REPORT")
        self.assertFalse(result["hash"])
        self.assertFalse(result["positions"])

    def test_queue_is_idempotent_and_continues_partial(self):
        app.enqueue(["REPORT", "REPORT"])
        self.assertEqual(app.claim()["report_id"], "REPORT")
        self.assertIsNone(app.claim())
        app.finish("REPORT", {"status":"partial", "processed":1, "batches":2, "continue":True,
                              "rows":[{"id":"c","statement":"Заявление"}]})
        self.assertEqual(app.rows_for("REPORT")[0]["id"], "c")
        self.assertEqual(app.claim()["report_id"], "REPORT")

    def test_claim_review_updates_visible_evidence(self):
        app.enqueue(["REPORT"])
        app.claim()
        app.finish("REPORT", {"status":"extracted", "queue_research":True, "rows":[{"id":"c","statement":"Заявление"}]})
        self.assertEqual(app.claim_review()["claim"]["id"], "c")
        app.finish_review({"report_id":"REPORT","claim_id":"c","status":"complete",
                           "display":{"status":"Недостаточно сопоставимых данных","searched":True}})
        self.assertTrue(app.rows_for("REPORT")[0]["searched"])
        self.assertIsNone(app.claim_review())


if __name__ == "__main__":
    unittest.main()
