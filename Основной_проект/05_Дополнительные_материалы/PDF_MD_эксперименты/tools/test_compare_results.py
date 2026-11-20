import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from compare_results import (inspect_markdown, split_pages, compare_text, run, fitz, Image,
                             decimal_span_reference, compare_decimals_to_spans)


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def markdown(self,text):
        p=self.root/'report.md';p.write_text(text);return p

    def test_incomplete_duplicate_and_out_of_order_markers(self):
        for text in ('<!-- pdf_page: 1 --> a',
                     '<!-- pdf_page: 1 --> a <!-- pdf_page: 1 --> b <!-- pdf_page: 2 --> c',
                     '<!-- pdf_page: 2 --> b <!-- pdf_page: 1 --> a'):
            with self.subTest(text=text):
                _,issues,_=split_pages(text,2)
                self.assertTrue(any(i['code']=='page_markers' for i in issues))
        _,issues,_=split_pages('<!-- pdf_page: 1 --> a <!-- pdf_page: 2 --> b',2)
        self.assertFalse(issues)

    def test_corrupt_image_is_not_accepted_as_present(self):
        (self.root/'bad.png').write_bytes(b'not actually a PNG')
        r=inspect_markdown(self.markdown('<!-- pdf_page: 1 -->\n![figure](bad.png)'),1)
        self.assertEqual(r['state'],'structural_issues')
        self.assertTrue(any(i['code']=='undecodable_image' for i in r['issues']))

    def test_missing_and_correct_anchor(self):
        bad=inspect_markdown(self.markdown('<!-- pdf_page: 1 -->\n<a id="pdf-page-1"></a> [Next](#pdf-page-2)'),1)
        self.assertTrue(any(i['code']=='broken_anchor' for i in bad['issues']))
        good=inspect_markdown(self.markdown('<!-- pdf_page: 1 -->\n<a id="pdf-page-1"></a> [Here](#pdf-page-1)'),1)
        self.assertEqual(good['state'],'structurally_valid_unreviewed')

    def test_decodable_image_and_html_table_numbers(self):
        Image.new('RGB',(3,4),'white').save(self.root/'good.png')
        r=inspect_markdown(self.markdown('<!-- pdf_page: 1 -->\n![figure](good.png)'),1)
        self.assertFalse(r['issues']);self.assertEqual(r['images'][0]['size'],[3,4])
        comparison=compare_text('<table><tr><td>Объем</td><td>12,5%</td></tr></table>','Объем 12,5%')
        self.assertTrue(comparison['text_equal'])
        self.assertEqual(comparison['numeric_left_only'],{})

    def test_numeric_multiplicity_reveals_lost_repeated_value(self):
        r=compare_text('5 5 7','5 7')
        self.assertEqual(r['numeric_left_only'],{'5':1})
        self.assertFalse(r['text_equal'])

    def decimal_fixture(self):
        def span(text,x,size=8,flags=4,y=20):
            return {'text':text,'size':size,'flags':flags,'font':'Fixture',
                    'origin':[x,y],'bbox':[x,y-size,x+len(text)*size*.5,y+2]}
        return {'blocks':[{'lines':[
            {'spans':[span('1,963',10)]},
            {'spans':[span('0,173',10),span('2',30,4.6,5,17.3)]},
            {'spans':[span('76,6',10),span('2',26,4.6,5,17.3)]},
        ]}]}

    def test_decimal_reference_does_not_append_separate_superscript(self):
        reference=decimal_span_reference(self.decimal_fixture())
        self.assertEqual(dict(reference['counts']),{'1.963':1,'0.173':1,'76.6':1})
        self.assertNotIn('0.1732',reference['counts'])
        self.assertNotIn('76.62',reference['counts'])
        source=next(e for e in reference['evidence'] if e['token']=='0.173')
        self.assertEqual(source['font_size'],8)
        self.assertEqual(source['line_spans'][1]['flags'],5)
        self.assertEqual(source['line_spans'][1]['text'],'2')
        self.assertIn('bbox',source)

    def test_decimal_diff_preserves_actual_pdf_span_evidence(self):
        reference=decimal_span_reference(self.decimal_fixture())
        correct=compare_decimals_to_spans('1,963 | 0,173<sup>2</sup> | 76,6²',reference)
        self.assertEqual(correct['pdf_only'],{})
        self.assertEqual(correct['markdown_only'],{})
        wrong=compare_decimals_to_spans('1,96³ | 0,17³² | 76,64',reference)
        self.assertEqual(wrong['pdf_only'],{'1.963':1,'0.173':1,'76.6':1})
        self.assertEqual(wrong['markdown_only'],{'1.96':1,'0.17':1,'76.64':1})
        self.assertEqual(len(wrong['pdf_span_evidence']),3)

    def test_table_cells_are_not_joined_as_thousands(self):
        reference={'counts':{'402.82':1,'697.12':1,'786.11':1,'+12.8':1},'evidence':[],
                   'excluded_superscript_decimal_spans':[]}
        md='| 2022 | 402,82 |\n| Энергетика | 676 | 697,12 | 786,11 | +12,8 |'
        result=compare_decimals_to_spans(md,reference)
        self.assertEqual(result['pdf_only'],{})
        # A real leading plus sign is preserved; it is not a cell-joining artifact.
        self.assertNotIn('2022402.82',result['markdown_only'])
        self.assertNotIn('676697.12',result['markdown_only'])
        self.assertEqual(result['markdown_decimal_tokens'],4)

    def test_html_cell_boundary_and_service_notes_do_not_hide_values(self):
        reference={'counts':{'402.82':1},'evidence':[], 'excluded_superscript_decimal_spans':[]}
        md='> Служебная пометка: страница 9\n\n<table><tr><td>2022</td><td>402,82</td></tr></table>\n'
        result=compare_decimals_to_spans(md,reference)
        self.assertEqual(result['pdf_only'],{})
        self.assertEqual(result['markdown_only'],{})

    def test_absent_outputs_remain_pending_and_not_fabricated(self):
        (self.root/'_источники').mkdir()
        doc=fitz.open();doc.new_page();doc.save(self.root/'_источники/TEST-2025.pdf');doc.close()
        registry=self.root/'registry.csv'
        with registry.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,['report_id','company_id'],delimiter=';');w.writeheader();w.writerow({'report_id':'TEST-2025','company_id':'TEST'})
        with contextlib.redirect_stdout(io.StringIO()):summary=run(self.root,registry)
        self.assertEqual(summary['reports_expected'],1)
        self.assertEqual(summary['report_states'],{'pending':1})
        self.assertEqual(summary['pair_pages_compared'],0)
        self.assertFalse(summary['checked_authorized'])
        self.assertFalse(list(self.root.rglob('report.md')))
        with (self.root/'_проверка/comparison.csv').open(encoding='utf-8-sig') as f:
            self.assertEqual(len(list(csv.DictReader(f,delimiter=';'))),1)


if __name__=='__main__':unittest.main()
