"""Structural/completion regression tests. No models, API, credentials or real PDFs used."""
from __future__ import annotations
import concurrent.futures
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import sys
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('runner_under_test', Path(__file__).with_name('run_models.py'))
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class BundleGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / 'bundle'
        self.folder.mkdir()
        self.index = {'pages': [{'pdf_page': 1}, {'pdf_page': 2}]}

    def bundle(self, text):
        (self.folder / 'report.md').write_text(text)
        return runner.validate_bundle(self.folder, self.index)

    def body(self):
        return '<!-- pdf_page: 1 -->\n<a id="pdf-page-1"></a>\nТекст\n<!-- pdf_page: 2 -->\n<a id="pdf-page-2"></a>\nТаблица'

    def test_valid_bundle_with_real_asset_and_internal_anchor(self):
        (self.folder / 'assets').mkdir()
        (self.folder / 'assets/page.png').write_bytes(b'fixture')
        result = self.bundle(self.body() + '\n![Источник](assets/page.png)\n[Переход](#pdf-page-2)')
        self.assertTrue(result['assembled'])
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['markers'], [1, 2])

    def test_missing_report_is_not_assembled(self):
        self.assertFalse(runner.validate_bundle(self.folder, self.index)['assembled'])

    def test_missing_asset_fails(self):
        result = self.bundle(self.body() + '\n![Логотип](assets/nonexistent-logo.png)')
        self.assertFalse(result['assembled'])
        self.assertTrue(any('missing_or_unsafe_asset' in v for v in result['errors']))

    def test_path_escape_fails_even_when_external_file_exists(self):
        (self.folder.parent / 'outside.png').write_bytes(b'fixture')
        result = self.bundle(self.body() + '\n![X](../outside.png)')
        self.assertFalse(result['assembled'])

    def test_percent_encoded_path_escape_fails(self):
        (self.folder.parent / 'outside.png').write_bytes(b'fixture')
        result = self.bundle(self.body() + '\n![X](%2e%2e/outside.png)')
        self.assertFalse(result['assembled'])

    def test_symlink_escape_fails(self):
        external = self.folder.parent / 'outside.png'
        external.write_bytes(b'fixture')
        (self.folder / 'escape.png').symlink_to(external)
        result = self.bundle(self.body() + '\n<img src="escape.png">')
        self.assertFalse(result['assembled'])

    def test_missing_marker_fails(self):
        result = self.bundle('<!-- pdf_page: 1 -->\nТолько первая страница')
        self.assertFalse(result['assembled'])

    def test_duplicate_marker_fails(self):
        self.assertFalse(self.bundle(self.body() + '\n<!-- pdf_page: 2 -->')['assembled'])

    def test_out_of_order_markers_fail(self):
        self.assertFalse(self.bundle('<!-- pdf_page: 2 -->\nB\n<!-- pdf_page: 1 -->\nA')['assembled'])

    def test_page_count_mismatch_fails(self):
        self.assertFalse(self.bundle(self.body() + '\n<!-- pdf_page: 3 -->\nC')['assembled'])

    def test_unresolved_internal_anchor_fails(self):
        self.assertFalse(self.bundle(self.body() + '\n[Нет назначения](#pdf-page-99)')['assembled'])

    def test_missing_reference_style_asset_fails(self):
        result = self.bundle(self.body() + '\n![Логотип][logo]\n\n[logo]: assets/nonexistent.png')
        self.assertFalse(result['assembled'], 'Reference-style assets need the same gate as inline assets')

    def test_external_urls_do_not_require_local_assets(self):
        self.assertTrue(self.bundle(self.body() + '\n[Источник](https://example.org/report.pdf)')['assembled'])


class WorkerRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'pages.json'

    def registry(self, records, total=2):
        self.path.write_text(json.dumps({'pages': records}))
        return runner.worker_page_states(self.path, total)

    @staticmethod
    def page(n, conversion='converted', issues=None):
        return {'pdf_page': n, 'conversion_status': conversion, 'review_status': 'pending', 'issues': issues or []}

    def test_missing_registry_is_not_complete(self):
        result = runner.worker_page_states(self.path, 2)
        self.assertFalse(result['transcription_complete'])
        self.assertEqual(result['pending_pages'], [1, 2])

    def test_unread_scan_is_not_complete(self):
        result = self.registry([self.page(1), self.page(2, 'pending', ['scan_body_not_transcribed'])])
        self.assertFalse(result['transcription_complete'])
        self.assertEqual(result['pending_pages'], [2])

    def test_converted_page_with_open_issue_is_not_complete(self):
        result = self.registry([self.page(1), self.page(2, issues=['missing_table_rows'])])
        self.assertFalse(result['transcription_complete'])

    def test_missing_page_registry_entry_fails(self):
        self.assertFalse(self.registry([self.page(1)])['transcription_complete'])

    def test_duplicate_page_registry_entry_fails(self):
        self.assertFalse(self.registry([self.page(1), self.page(1)])['transcription_complete'])

    def test_extra_page_registry_entry_fails(self):
        self.assertFalse(self.registry([self.page(1), self.page(2), self.page(3)])['transcription_complete'])

    def test_transcribed_is_distinct_from_source_verified(self):
        result = self.registry([self.page(1), self.page(2)])
        self.assertTrue(result['transcription_complete'])
        self.assertNotIn('checked', result)
        self.assertNotIn('verified', result)


class RunCompletionRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.patch = mock.patch.object(runner, 'BASE', self.base)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_unknown_report_filter_is_rejected(self):
        with mock.patch.object(runner, 'ROWS', [{'report_id': 'REAL'}]), \
             mock.patch.object(sys, 'argv', ['runner', '--reports', 'TYPO']):
            with self.assertRaises(SystemExit):
                runner.main()

    def test_stale_cached_answer_cannot_complete_after_current_request_error(self):
        """A fingerprint rejection must not be bypassed by assembly of the stale file."""
        row = {'report_id': 'FIXTURE', 'company_id': 'F', 'company': 'Fixture', 'year': '2023', 'report_type': 'test'}
        image = self.base / 'input.png'
        image.write_bytes(b'fixture-image')
        item = {'pdf_page': 1, 'image': 'input.png', 'image_sha256': runner.sha(image)}
        index = {'pages': [item], 'source_sha256': 'current-source'}
        cached = self.base / '_проверка/DeepSeek/FIXTURE' / runner.RUN_VERSION / 'page_0001.json'
        cached.parent.mkdir(parents=True)
        cached.write_text(json.dumps({'instruction_sha256': runner.INSTRUCTION_SHA,
            'request_sha256': 'stale-fingerprint', 'source_image_sha256': 'stale-image',
            'response': {'pdf_page': 1, 'markdown': 'Old answer', 'issues': []},
            'automatic_flags': [], 'review_status': 'converted'}))
        def copy_asset(source, target):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        with mock.patch.object(runner, 'deepseek_page', side_effect=ValueError('Cached response belongs to different input/prompt')), \
             mock.patch.object(runner, 'clone', side_effect=copy_asset), \
             concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            result = runner.run_deepseek(row, index, executor)
        self.assertEqual(result['errors'], 1)
        self.assertFalse(result['complete'], 'Stale result must not make a failed current run complete')
        self.assertFalse(result['transcription_complete'])


class RequestFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        patch = mock.patch.object(runner, 'BASE', self.base)
        patch.start()
        self.addCleanup(patch.stop)
        (self.base / 'input.png').write_bytes(b'image-fixture')
        packet = {'pdf_page': 1, 'text_blocks': [{'text': 'Source fixture'}], 'links': []}
        (self.base / 'packet.json').write_text(json.dumps(packet))
        self.row = {'report_id': 'FIXTURE'}
        self.item = {'pdf_page': 1, 'packet': 'packet.json', 'image': 'input.png',
                     'image_sha256': runner.sha(self.base / 'input.png'), 'text_chars': 14}
        self.client = mock.Mock()
        self.client.config = {'default_model': 'mock-model', 'base_url': 'https://not-called.invalid'}
        self.client.complete.return_value = {'choices': [{'finish_reason': 'stop', 'message': {
            'content': json.dumps({'pdf_page': 1, 'markdown': 'Source fixture', 'issues': []})}}],
            'model': 'mock-model', 'usage': {}}
        cp = mock.patch.object(runner, 'Client', return_value=self.client)
        cp.start()
        self.addCleanup(cp.stop)

    def test_identical_request_reuses_cache_without_model_call(self):
        first = runner.deepseek_page(self.row, self.item, correction='unchanged')
        second = runner.deepseek_page(self.row, self.item, correction='unchanged')
        self.assertEqual(first['request_sha256'], second['request_sha256'])
        self.assertEqual(self.client.complete.call_count, 1)

    def test_changed_correction_cannot_reuse_cache(self):
        runner.deepseek_page(self.row, self.item, correction='first')
        with self.assertRaises(ValueError):
            runner.deepseek_page(self.row, self.item, correction='changed')
        self.assertEqual(self.client.complete.call_count, 1)

    def test_changed_image_cannot_reuse_cache(self):
        runner.deepseek_page(self.row, self.item)
        (self.base / 'input.png').write_bytes(b'changed-image')
        with self.assertRaises(ValueError):
            runner.deepseek_page(self.row, self.item)

    def test_changed_packet_cannot_reuse_cache(self):
        runner.deepseek_page(self.row, self.item)
        packet = json.loads((self.base / 'packet.json').read_text())
        packet['text_blocks'][0]['text'] = 'Changed source fixture'
        (self.base / 'packet.json').write_text(json.dumps(packet))
        with self.assertRaises(ValueError):
            runner.deepseek_page(self.row, self.item)

    def test_changed_full_instruction_cannot_reuse_cache(self):
        runner.deepseek_page(self.row, self.item)
        with mock.patch.object(runner, 'INSTRUCTION_TEXT', runner.INSTRUCTION_TEXT + '\nChanged adapter instruction'):
            with self.assertRaises(ValueError):
                runner.deepseek_page(self.row, self.item)


class CachedSourcePacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        patch = mock.patch.object(runner, 'BASE', self.base)
        patch.start()
        self.addCleanup(patch.stop)
        self.row = {'report_id': 'FIXTURE'}
        source = self.base / '_источники/FIXTURE.pdf'
        source.parent.mkdir()
        with runner.fitz.open() as doc:
            doc.new_page().insert_text((30, 30), 'First fixture page')
            doc.new_page().insert_text((30, 30), 'Second fixture page')
            doc.save(source)
        packet_dir = self.base / '_проверка/входы/FIXTURE'
        packet_dir.mkdir(parents=True)
        self.index = packet_dir / 'pages.json'
        pages = []
        for n in (1, 2):
            packet = packet_dir / f'page_{n:04d}.json'
            image = packet_dir / f'page_{n:04d}.png'
            packet.write_text(json.dumps({'pdf_page': n, 'text_blocks': []}))
            image.write_bytes(f'fixture-image-{n}'.encode())
            pages.append({'pdf_page': n, 'packet': str(packet.relative_to(self.base)),
                          'packet_sha256': runner.sha(packet), 'image': str(image.relative_to(self.base)),
                          'image_sha256': runner.sha(image), 'text_chars': 20})
        self.cached = {'report_id': 'FIXTURE', 'source_sha256': runner.sha(source), 'pages': pages}

    def save_index(self):
        self.index.write_text(json.dumps(self.cached))

    def test_valid_cached_packets_are_reusable(self):
        self.save_index()
        result = runner.page_inputs(self.row)
        self.assertEqual([p['pdf_page'] for p in result['pages']], [1, 2])

    def test_truncated_cached_index_is_rejected_against_pdf_count(self):
        self.cached['pages'] = self.cached['pages'][:1]
        self.save_index()
        with self.assertRaises(ValueError):
            runner.page_inputs(self.row)

    def test_duplicate_cached_page_numbers_are_rejected(self):
        self.cached['pages'][1]['pdf_page'] = 1
        self.save_index()
        with self.assertRaises(ValueError):
            runner.page_inputs(self.row)

    def test_changed_packet_file_is_rejected(self):
        self.save_index()
        (self.base / self.cached['pages'][0]['packet']).write_text('Changed fixture packet')
        with self.assertRaises(ValueError):
            runner.page_inputs(self.row)

    def test_missing_cached_image_is_rejected(self):
        self.save_index()
        (self.base / self.cached['pages'][0]['image']).unlink()
        with self.assertRaises(ValueError):
            runner.page_inputs(self.row)


class AssemblerMetadataDedupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        patch = mock.patch.object(runner, 'BASE', self.base)
        patch.start()
        self.addCleanup(patch.stop)
        self.row = {'report_id': 'FIXTURE', 'company_id': 'F'}
        (self.base / 'input.png').write_bytes(b'image-fixture')
        self.packet = self.base / 'packet.json'
        self.packet.write_text(json.dumps({'pdf_page': 1, 'text_blocks': [{'text': 'Ordinary source text'}]}))
        self.item = {'pdf_page': 1, 'packet': 'packet.json', 'image': 'input.png',
                     'image_sha256': runner.sha(self.base / 'input.png')}
        self.index = {'pages': [self.item], 'source_sha256': 'fixture-source'}
        self.version_dir = self.base / '_проверка/DeepSeek/FIXTURE' / runner.RUN_VERSION
        self.version_dir.mkdir(parents=True)
        self.answer_file = self.version_dir / 'page_0001.json'
        self.raw_file = self.version_dir / 'raw/page_0001.json'
        self.raw_file.parent.mkdir()
        def copy_asset(source, target):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        patch = mock.patch.object(runner, 'clone', side_effect=copy_asset)
        patch.start()
        self.addCleanup(patch.stop)

    def save_answer(self, body):
        self.answer_file.write_text(json.dumps({'instruction_sha256': runner.INSTRUCTION_SHA,
            'response': {'pdf_page': 1, 'markdown': body, 'issues': []},
            'automatic_flags': [], 'review_status': 'converted'}))
        self.raw_file.write_text(json.dumps({'choices': [{'message': {'content': body}}]}))
        return self.answer_file.read_bytes(), self.raw_file.read_bytes()

    def assert_answers_unchanged(self, snapshots):
        self.assertEqual(self.answer_file.read_bytes(), snapshots[0])
        self.assertEqual(self.raw_file.read_bytes(), snapshots[1])

    def report(self):
        return (runner.report_dir('DeepSeek', self.row) / 'report.md').read_text()

    def test_own_duplicate_wrapper_metadata_removed_without_touching_answers(self):
        snapshots = self.save_answer('<!-- pdf_page: 1 -->\n<a id="pdf-page-1"></a>\nOriginal body 1,963')
        self.assertTrue(runner.assemble_deepseek(self.row, self.index))
        result = self.report()
        self.assertEqual(result.count('<!-- pdf_page: 1 -->'), 1)
        self.assertEqual(result.count('<a id="pdf-page-1"></a>'), 1)
        self.assertIn('Original body 1,963', result)
        edits = json.loads((self.version_dir / 'assembly_edits.json').read_text())
        self.assertEqual({e['kind'] for e in edits}, {'duplicate_page_marker', 'duplicate_page_anchor'})
        self.assertTrue(all(e['raw_answer_unchanged'] for e in edits))
        self.assert_answers_unchanged(snapshots)

    def test_literal_metadata_in_source_is_preserved_and_not_unconditionally_accepted(self):
        literal = '<!-- pdf_page: 1 -->\n<a id="pdf-page-1"></a>'
        self.packet.write_text(json.dumps({'pdf_page': 1, 'text_blocks': [{'text': 'Source example: '+literal}]}))
        snapshots = self.save_answer('Literal source example:\n'+literal)
        self.assertFalse(runner.assemble_deepseek(self.row, self.index))
        self.assertEqual(self.report().count('<!-- pdf_page: 1 -->'), 2)
        self.assertEqual(self.report().count('<a id="pdf-page-1"></a>'), 2)
        edits = json.loads((self.version_dir / 'assembly_edits.json').read_text())
        self.assertEqual(edits, [])
        self.assert_answers_unchanged(snapshots)

    def test_missing_model_image_becomes_service_note_with_real_source_page(self):
        snapshots = self.save_answer('Text before\n![Логотип компании](assets/made-up-logo.png)\nText after')
        self.assertTrue(runner.assemble_deepseek(self.row, self.index))
        result = self.report()
        self.assertNotIn('![Логотип компании](assets/made-up-logo.png)', result)
        self.assertIn('Служебная пометка: отдельное изображение «Логотип компании» не создавалось.', result)
        self.assertIn('полном исходном изображении PDF-страницы ниже', result)
        self.assertIn('Text before', result)
        self.assertIn('Text after', result)
        self.assertIn('![Исходная PDF-страница 1](assets/page_0001.png)', result)
        real_asset = runner.report_dir('DeepSeek', self.row) / 'assets/page_0001.png'
        self.assertEqual(real_asset.read_bytes(), b'image-fixture')
        edits = json.loads((self.version_dir / 'assembly_edits.json').read_text())
        edit = next(e for e in edits if e['kind'] == 'unmaterialized_model_image_reference')
        self.assertEqual(edit['target'], 'assets/made-up-logo.png')
        self.assertEqual(edit['fallback'], 'full_original_page_below_not_a_crop')
        self.assertTrue(edit['raw_answer_unchanged'])
        self.assert_answers_unchanged(snapshots)

    def test_source_literal_image_reference_is_preserved_and_gate_rejects_dangling_link(self):
        literal = '![Пример иллюстрации](assets/source-example.png)'
        self.packet.write_text(json.dumps({'pdf_page': 1, 'text_blocks': [{'text': 'Literal PDF example: '+literal}]}))
        snapshots = self.save_answer('Literal PDF example:\n'+literal)
        self.assertFalse(runner.assemble_deepseek(self.row, self.index))
        self.assertIn(literal, self.report())
        self.assertNotIn('отдельное изображение «Пример иллюстрации» не создавалось', self.report())
        edits = json.loads((self.version_dir / 'assembly_edits.json').read_text())
        self.assertFalse(any(e['kind'] == 'unmaterialized_model_image_reference' for e in edits))
        gate = json.loads((self.version_dir / 'bundle_check.json').read_text())
        self.assertTrue(any('missing_or_unsafe_asset:assets/source-example.png' == e for e in gate['errors']))
        self.assert_answers_unchanged(snapshots)

    def test_other_page_metadata_is_not_deleted_and_bundle_gate_fails(self):
        snapshots = self.save_answer('Body\n<!-- pdf_page: 99 -->\n<a id="pdf-page-99"></a>')
        self.assertFalse(runner.assemble_deepseek(self.row, self.index))
        self.assertIn('<!-- pdf_page: 99 -->', self.report())
        self.assertIn('<a id="pdf-page-99"></a>', self.report())
        gate = json.loads((self.version_dir / 'bundle_check.json').read_text())
        self.assertFalse(gate['assembled'])
        self.assertIn('page_markers_missing_duplicated_or_out_of_order', gate['errors'])
        edits = json.loads((self.version_dir / 'assembly_edits.json').read_text())
        self.assertEqual(edits, [])
        self.assert_answers_unchanged(snapshots)


if __name__ == '__main__':
    unittest.main(verbosity=2)
