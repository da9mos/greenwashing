"""Synthetic evidence fixtures test the gate, not the quality of real reports."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import review_gate
import pymupdf as fitz
from review_gate import COMPONENTS, GateError, validate_review

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class ReviewGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        pdf = fitz.open()
        for number in (1, 2):
            page = pdf.new_page(width=300, height=200)
            page.insert_text((20, 40), f'Report page {number}; value 12.30')
        pdf.save(self.root/'source.pdf')
        pdf.close()
        self.output = self.root/'report.md'
        self.output.write_text(''.join(f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\nReport page {n}; value 12.30\n' for n in (1, 2)))
        self.manifest = self.root/'review.json'
        self.data = {'schema_version': 1,
                     'source': {'path': 'source.pdf', 'sha256': digest(self.root/'source.pdf'), 'pages': 2},
                     'output': {'path': 'report.md', 'sha256': digest(self.output)},
                     'artifacts': [],
                     'review': {'status': 'checked', 'reviewer': 'synthetic-unit-test',
                                'method': 'full_source_comparison', 'reviewed_at': '2026-11-16T00:00:00+00:00',
                                'issues': [], 'pages': []}}
        with fitz.open(self.root/'source.pdf') as source:
            for number in (1, 2):
                source[number-1].get_pixmap().save(self.root/f'source_{number}.png')
                # A different image represents an output-render fixture, never an audit of a real report.
                out = fitz.open()
                page = out.new_page(width=300, height=200)
                page.insert_text((20, 20), f'Rendered Markdown page {number}')
                page.insert_text((20, 40), f'Report page {number}; value 12.30')
                page.get_pixmap().save(self.root/f'render_{number}.png')
                out.close()
                components = {name: {'status': 'checked', 'evidence': [f's{number}', f'r{number}', f'c{number}']} for name in COMPONENTS}
                self.data['review']['pages'].append({'pdf_page': number, 'issues': [], 'components': components})
                comparison = {'schema_version': 1, 'pdf_page': number,
                              'source_sha256': self.data['source']['sha256'], 'output_sha256': self.data['output']['sha256'],
                              'components': {name: {'status': 'checked',
                                'finding': f'Synthetic fixture: the {name} observation is attached to this page only.',
                                'source_locator': {'pdf_page': number, 'bbox': [0, 0, 300, 200]},
                                'output_locator': {'anchor': f'pdf-page-{number}', 'excerpt': f'Report page {number}; value 12.30'}} for name in COMPONENTS}}
                (self.root/f'compare_{number}.json').write_text(json.dumps(comparison))
                for key, kind, path in [(f's{number}', 'source_image', f'source_{number}.png'),
                                        (f'r{number}', 'output_render', f'render_{number}.png'),
                                        (f'c{number}', 'comparison', f'compare_{number}.json')]:
                    self.data['artifacts'].append({'id': key, 'kind': kind, 'pdf_page': number, 'path': path, 'sha256': digest(self.root/path)})
                    if kind == 'source_image':self.data['artifacts'][-1]['render_scale'] = 1
                    if kind == 'output_render':self.data['artifacts'][-1]['output_sha256'] = self.data['output']['sha256']
        self.save()

    def save(self):
        self.manifest.write_text(json.dumps(self.data))

    def check(self):
        self.save()
        return validate_review(self.manifest)

    def reject(self, code):
        with self.assertRaises(GateError) as error:
            self.check()
        self.assertEqual(error.exception.code, code)

    def edit_comparison(self, number, edit):
        path = self.root/f'compare_{number}.json'
        data = json.loads(path.read_text())
        edit(data)
        path.write_text(json.dumps(data))
        next(a for a in self.data['artifacts'] if a['id'] == f'c{number}')['sha256'] = digest(path)

    def test_complete_fixture_passes_without_semantic_certification(self):
        result = self.check()
        self.assertEqual(result['gate'], 'pass')
        self.assertTrue(result['eligible_for_checked'])
        self.assertFalse(result['semantic_truth_verified_by_gate'])

    def test_partial_remains_partial_and_lists_missing_pages(self):
        self.data['review']['status'] = 'partial'
        self.data['review']['method'] = 'sample'
        self.data['review']['pages'] = self.data['review']['pages'][:1]
        result = self.check()
        self.assertEqual(result['gate'], 'partial')
        self.assertFalse(result['eligible_for_checked'])
        self.assertIn('page 2: no review record', result['missing'])

    def test_cover_only_cannot_promote_whole_document(self):
        self.data['review']['pages'] = self.data['review']['pages'][:1]
        self.reject('CHECKED_WITH_GAPS')

    def test_declared_page_count_must_match_actual_pdf(self):
        self.data['source']['pages'] = 1
        self.reject('SOURCE_PAGE_COUNT')

    def test_changed_saved_markdown_is_rejected(self):
        self.output.write_text(self.output.read_text().replace('12.30', '1230'))
        self.reject('SHA_MISMATCH')

    def test_changed_source_pdf_is_rejected(self):
        with (self.root/'source.pdf').open('ab') as stream:
            stream.write(b'\n% changed\n')
        self.reject('SHA_MISMATCH')

    def test_missing_evidence_file_is_rejected(self):
        (self.root/'source_2.png').unlink()
        self.reject('MISSING_FILE')

    def test_changed_evidence_hash_is_rejected(self):
        (self.root/'compare_2.json').write_text('{}')
        self.reject('SHA_MISMATCH')

    def test_empty_evidence_is_rejected_even_with_current_hash(self):
        path = self.root/'compare_1.json'
        path.write_text('')
        next(a for a in self.data['artifacts'] if a['id'] == 'c1')['sha256'] = digest(path)
        self.reject('EMPTY_EVIDENCE')

    def test_placeholder_observation_is_rejected(self):
        self.edit_comparison(1, lambda d: d['components']['numbers'].update(finding='checked'))
        self.reject('EMPTY_EVIDENCE')

    def test_fake_image_is_rejected_even_with_current_hash(self):
        path = self.root/'source_1.png'
        path.write_text('This file is not an actual source-page image.')
        next(a for a in self.data['artifacts'] if a['id'] == 's1')['sha256'] = digest(path)
        self.reject('INVALID_IMAGE')

    def test_page_binding_prevents_reusing_cover_evidence(self):
        self.data['review']['pages'][1]['components']['text']['evidence'] = ['s1', 'r1', 'c1']
        self.reject('EVIDENCE_PAGE')

    def test_comparison_must_bind_current_output(self):
        self.edit_comparison(1, lambda d: d.update(output_sha256='0'*64))
        self.reject('EVIDENCE_IDENTITY')

    def test_open_page_defect_blocks_checked(self):
        self.data['review']['pages'][0]['issues'] = ['One number is still illegible.']
        self.reject('CHECKED_WITH_GAPS')

    def test_open_document_defect_blocks_checked(self):
        self.data['review']['issues'] = ['Outstanding table ownership conflict.']
        self.reject('CHECKED_WITH_GAPS')

    def test_missing_component_blocks_checked(self):
        del self.data['review']['pages'][0]['components']['footnotes']
        self.reject('CHECKED_WITH_GAPS')

    def test_partial_can_retain_an_explicit_unresolved_component(self):
        self.data['review']['status'] = 'partial'
        component = self.data['review']['pages'][0]['components']['numbers']
        component.update(status='pending', evidence=[], reason='Source superscript remains ambiguous after enlargement.')
        self.assertFalse(self.check()['eligible_for_checked'])

    def test_display_cannot_be_waived(self):
        self.data['review']['pages'][0]['components']['display'].update(status='not_applicable', reason='No display was available in this execution environment.')
        self.reject('COMPONENT_COVERAGE')

    def test_named_absence_with_page_evidence_is_valid(self):
        self.data['review']['pages'][0]['components']['graphics'].update(status='not_applicable', reason='No graphics are present on this synthetic source page.')
        self.edit_comparison(1, lambda d: d['components']['graphics'].update(status='not_applicable', finding='The synthetic source page contains text only, with no graphics.'))
        self.assertTrue(self.check()['eligible_for_checked'])

    def test_unknown_evidence_reference_is_rejected(self):
        self.data['review']['pages'][0]['components']['text']['evidence'] = ['does-not-exist']
        self.reject('MISSING_EVIDENCE')

    def test_comparison_must_point_inside_actual_page(self):
        self.edit_comparison(1, lambda d: d['components']['numbers']['source_locator'].update(bbox=[0, 0, 900, 900]))
        self.reject('EVIDENCE_LOCATOR')

    def test_comparison_must_point_to_saved_output_text(self):
        self.edit_comparison(1, lambda d: d['components']['numbers']['output_locator'].update(excerpt='This sentence is not in the Markdown.'))
        self.reject('EVIDENCE_LOCATOR')

    def test_wrong_source_picture_cannot_be_relabelled_as_another_page(self):
        path = self.root/'source_2.png'
        path.write_bytes((self.root/'source_1.png').read_bytes())
        next(a for a in self.data['artifacts'] if a['id'] == 's2')['sha256'] = digest(path)
        self.reject('SOURCE_IMAGE_IDENTITY')

    def test_wrong_source_render_scale_is_rejected(self):
        self.data['artifacts'][0]['render_scale'] = 2
        self.reject('SOURCE_IMAGE_IDENTITY')

    def test_render_from_old_markdown_is_rejected(self):
        next(a for a in self.data['artifacts'] if a['id'] == 'r1')['output_sha256'] = '0'*64
        self.reject('EVIDENCE_IDENTITY')

    def test_metadata_object_cannot_be_used_as_an_evidence_id(self):
        self.data['review']['pages'][0]['components']['text']['evidence'] = [{'status': 'checked'}]
        self.reject('SCHEMA')

    def add_crop(self):
        with fitz.open(self.root/'source.pdf') as pdf:
            pdf[0].get_pixmap(matrix=fitz.Matrix(2, 2), clip=fitz.Rect(10, 20, 260, 60), alpha=False).save(self.root/'crop.png')
        self.data['artifacts'].append({'id': 'crop1', 'kind': 'source_crop', 'pdf_page': 1, 'path': 'crop.png',
                                       'sha256': digest(self.root/'crop.png'), 'render_scale': 2, 'clip': [10, 20, 260, 60]})
        self.data['review']['pages'][0]['components']['numbers']['evidence'].append('crop1')

    def test_zoom_crop_can_supplement_full_page_evidence(self):
        self.add_crop()
        self.assertTrue(self.check()['eligible_for_checked'])

    def test_crop_cannot_replace_full_page_evidence(self):
        self.add_crop()
        self.data['review']['pages'][0]['components']['numbers']['evidence'].remove('s1')
        self.reject('CHECKED_WITH_GAPS')

    def test_false_source_crop_geometry_is_rejected(self):
        self.add_crop()
        self.data['artifacts'][-1]['clip'] = [0, 0, 100, 100]
        self.reject('SOURCE_IMAGE_IDENTITY')

    def test_boolean_schema_version_is_not_an_integer_version(self):
        self.data['schema_version'] = True
        self.reject('SCHEMA')

    def test_comparison_boolean_page_number_is_rejected(self):
        self.edit_comparison(1, lambda d: d.update(pdf_page=True))
        self.reject('EVIDENCE_IDENTITY')

    def test_conversion_registry_cannot_be_substituted_for_review(self):
        self.data['pages'] = self.data.pop('review')['pages']
        self.reject('SCHEMA')

    def test_duplicate_review_page_is_rejected(self):
        self.data['review']['pages'].append(copy.deepcopy(self.data['review']['pages'][0]))
        self.reject('REVIEW_PAGE_COVERAGE')

    def test_output_page_marker_loss_is_rejected_even_with_current_md_hash(self):
        self.output.write_text(self.output.read_text().replace('<!-- pdf_page: 2 -->', ''))
        self.data['output']['sha256'] = digest(self.output)
        self.reject('OUTPUT_PAGE_COVERAGE')

    def test_path_traversal_is_rejected(self):
        self.data['artifacts'][0]['path'] = '../source_1.png'
        self.reject('UNSAFE_PATH')

    def test_output_modified_during_gate_is_rejected(self):
        real_sha = review_gate.sha
        modified = False
        def mutate(path):
            nonlocal modified
            result = real_sha(path)
            if path.resolve() == self.output.resolve() and not modified:
                modified = True
                path.write_text(path.read_text() + '\nChanged during validation.\n')
            return result
        self.save()
        with patch('review_gate.sha', side_effect=mutate):
            with self.assertRaises(GateError) as error:
                validate_review(self.manifest)
        self.assertEqual(error.exception.code, 'FILES_CHANGED_DURING_REVIEW')

    def test_manifest_modified_after_parse_is_rejected(self):
        real_sha = review_gate.sha
        modified = False
        def mutate(path):
            nonlocal modified
            result = real_sha(path)
            if path.resolve() == (self.root/'source.pdf').resolve() and not modified:
                modified = True
                newer = copy.deepcopy(self.data)
                newer['review']['status'] = 'partial'
                self.manifest.write_text(json.dumps(newer))
            return result
        self.save()
        with patch('review_gate.sha', side_effect=mutate):
            with self.assertRaises(GateError) as error:
                validate_review(self.manifest)
        self.assertEqual(error.exception.code, 'FILES_CHANGED_DURING_REVIEW')

    def test_require_checked_cli_returns_two_for_valid_partial(self):
        self.data['review']['status'] = 'partial'
        self.data['review']['pages'] = []
        self.save()
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('review_gate.py')), str(self.manifest), '--require-checked'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['gate'], 'partial')

if __name__ == '__main__':
    unittest.main()
