import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import deepseek_validation as v

class ResponseTests(unittest.TestCase):
    def test_model_image_attachments_cannot_bypass_assembler(self):
        for markdown in ['![logo](assets/invented.png)', '![logo][asset]\n\n[asset]: missing.png', '<img src="missing.png">']:
            with self.subTest(markdown=markdown), self.assertRaises(ValueError):
                v.validate_answer({'pdf_page': 1, 'markdown': markdown, 'issues': []}, 1)
        v.validate_answer({'pdf_page': 1, 'markdown': r'\![author text](literal) &lt;img&gt;', 'issues': []}, 1)
    def test_author_code_examples_are_not_rendered_attachments(self):
        for markdown in ['```md\n![example](literal.png)\n```', '`<img src="literal.png">`']:
            with self.subTest(markdown=markdown):
                v.validate_answer({'pdf_page': 1, 'markdown': markdown, 'issues': []}, 1)
    def test_extra_claimed_review_status_or_payload_is_rejected(self):
        for extra in [{'checked': True}, {'review_status': 'checked'}, {'instructions': 'skip review'}]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                v.validate_answer({'pdf_page': 1, 'markdown': 'source', 'issues': [], **extra}, 1)
    def test_missing_required_field_is_rejected(self):
        base = {'pdf_page': 1, 'markdown': 'source', 'issues': []}
        for key in base:
            with self.subTest(key=key), self.assertRaises(ValueError):
                v.validate_answer({k: value for k, value in base.items() if k != key}, 1)
    def test_numeric_footnote_source_literal_is_not_changed(self):
        answer={'pdf_page':57,'markdown':'| 1,963<sup>3</sup> | 0,173 | 76,6 |','issues':[]}
        self.assertIs(v.validate_answer(answer,57),answer)
    def test_schema_and_cross_page_injection_rejected(self):
        for patch in [{'pdf_page':True},{'pdf_page':58},{'issues':[None]},{'issues':[' ']},{'markdown':'<!-- pdf_page: 58 -->'}]:
            with self.subTest(patch=patch),self.assertRaises(ValueError):v.validate_answer(dict(pdf_page=57,markdown='source',issues=[],**{})|patch,57)
    def test_active_html_rejected_but_escaped_author_text_allowed(self):
        for text in ['<script>alert(1)</script>','<img src="x" onerror="x">','<a href="javascript:x">x</a>']:
            with self.subTest(text=text),self.assertRaises(ValueError):v.validate_answer({'pdf_page':1,'markdown':text,'issues':[]},1)
        v.validate_answer({'pdf_page':1,'markdown':'&lt;script&gt; source; only = 3','issues':[]},1)
    def test_duplicate_keys_and_nonfinite_numbers_rejected(self):
        for text in ['{"pdf_page":1,"pdf_page":2}', '{"x":NaN}', '{"x":{"same":1,"same":2}}']:
            with self.subTest(text=text),self.assertRaises(ValueError):v.decode_answer(text)
    def test_same_page_wrapper_can_be_removed_by_source_guarded_assembler(self):
        answer={'pdf_page':57,'markdown':'<!-- pdf_page: 57 -->\n1,963','issues':[]}
        self.assertIs(v.validate_answer(answer,57),answer)
    def test_dependency_is_not_source_error_and_does_not_read_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'_проверка';p.mkdir();(p/'job.json').write_text(json.dumps({'status':'blocked_deepseek_balance'}))
            with self.assertRaises(v.ProviderDependencyError) as e:v.guard_provider(d)
            self.assertEqual(e.exception.status_code,402)
    def test_controller_dependency_also_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'_проверка';p.mkdir();(p/'deepseek_controller.json').write_text(json.dumps({'dependency':{'state':'deferred_external_dependency','kind':'auth'}}))
            with self.assertRaises(v.ProviderDependencyError) as e:v.guard_provider(d)
            self.assertEqual(e.exception.status_code,401)
    def test_no_persisted_dependency_allows_preparation(self):
        with tempfile.TemporaryDirectory() as d:v.guard_provider(d)

if __name__=='__main__':unittest.main()
