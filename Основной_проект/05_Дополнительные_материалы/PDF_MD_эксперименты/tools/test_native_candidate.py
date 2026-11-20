"""No API/model/CLI tests of glyph transfer; semantic acceptance remains separate."""
from __future__ import annotations
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
import tempfile
import hashlib
import json
from unittest.mock import patch

MODULE = Path(__file__).with_name('native_candidate.py')
spec = importlib.util.spec_from_file_location('native_candidate_under_test', MODULE)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def line(text, x, y, flags=0, size=10, step=4):
    chars = [{'c': c, 'bbox': (x+i*step, y, x+(i+1)*step, y+8)} for i,c in enumerate(text)]
    return {'spans': [{'size': size, 'flags': flags, 'chars': chars}]}


def table(rows):
    cells = [c for row in rows for c in row if c]
    bbox = (min(c[0] for c in cells), min(c[1] for c in cells), max(c[2] for c in cells), max(c[3] for c in cells))
    return SimpleNamespace(rows=[SimpleNamespace(cells=r) for r in rows], bbox=bbox)


class FakePage:
    def __init__(self, lines, tables=()):
        self.data = {'blocks': [{'lines': lines}]}
        self.tables = list(tables)
    def get_text(self, mode, **kw):
        return self.data
    def find_tables(self, strategy):
        return SimpleNamespace(tables=self.tables)


def cells(body):
    return [x.get_text() for x in native.BeautifulSoup(body, 'html.parser').find_all('td')]


class NativeGlyphTests(unittest.TestCase):
    def assert_inventory(self, info):
        self.assertTrue(info['all_native_glyphs_assigned_once'])
        self.assertTrue(info['rendered_native_character_inventory_matches'])

    def test_repeated_equal_values_preserve_multiplicity(self):
        t=table([[(0,0,50,20)],[(0,20,50,40)],[(0,40,50,60)]])
        body,info=native.convert_page(FakePage([line('1,25',3,y) for y in [2,22,42]],[t]))
        self.assertEqual(cells(body),['1,25','1,25','1,25'])
        self.assert_inventory(info)

    def test_html_md_reserved_characters_survive_render(self):
        source='<tag>& \"quotes\" | *bold* _x_ `code` [a](b) # !'
        body,info=native.convert_page(FakePage([line(source,3,3)]))
        rendered=native.BeautifulSoup(native.MarkdownIt('commonmark',{'html':True}).render(body),'html.parser').get_text()
        self.assertEqual(rendered.strip(),source)
        self.assertIn('&lt;tag&gt;&amp;',body)
        self.assert_inventory(info)

    def test_reserved_characters_in_table_not_markdown_syntax(self):
        source='a|b < c & d > e'
        body,info=native.convert_page(FakePage([line(source,3,3)],[table([[(0,0,100,20)]])]))
        self.assertEqual(cells(body),[source])
        self.assert_inventory(info)

    def test_values_keep_rows_and_columns(self):
        t=table([[(0,0,50,20),(50,0,100,20)],[(0,20,50,40),(50,20,100,40)],[(0,40,50,60),(50,40,100,60)]])
        ls=[line('2022',3,2),line('2023',53,2),line('1,2',3,22),line('3,4',53,22),line('5,6',3,42),line('7,8',53,42)]
        body,info=native.convert_page(FakePage(ls,[t]))
        soup=native.BeautifulSoup(body,'html.parser')
        self.assertEqual([[x.get_text() for x in row.find_all('td')] for row in soup.find_all('tr')],[['2022','2023'],['1,2','3,4'],['5,6','7,8']])
        self.assert_inventory(info)

    def test_blank_data_cell_kept_when_header_identifies_column(self):
        t=table([[(0,0,50,20),(50,0,100,20)],[(0,20,50,40),(50,20,100,40)]])
        body,info=native.convert_page(FakePage([line('2022',3,2),line('2023',53,2),line('9,1',53,22)],[t]))
        self.assertEqual(cells(body),['2022','2023','','9,1'])
        self.assert_inventory(info)

    def test_ordinary_last_decimal_digit_not_superscript(self):
        body,info=native.convert_page(FakePage([line('1,963',3,3,flags=4)]))
        self.assertIn('1,963',body)
        self.assertNotIn('<sup>',body)
        self.assert_inventory(info)

    def test_superscript_not_merged_into_decimal(self):
        ls=[line('0,173',3,5,flags=4),line('2',23,2,flags=5,size=6)]
        ls[0]['spans']+=ls[1]['spans']
        body,info=native.convert_page(FakePage([ls[0]]))
        self.assertIn('0,173<sup>2</sup>',body)
        self.assertNotIn('0,1732',body)
        self.assert_inventory(info)

    def test_colspan_repeated_rectangle_emits_once(self):
        merged=(0,0,100,20)
        t=table([[merged,merged],[(0,20,50,40),(50,20,100,40)]])
        body,info=native.convert_page(FakePage([line('Years',3,2),line('2022',3,22),line('2023',53,22)],[t]))
        soup=native.BeautifulSoup(body,'html.parser');top=soup.find('td')
        self.assertEqual(top['colspan'],'2')
        self.assertEqual(cells(body),['Years','2022','2023'])
        self.assert_inventory(info)

    def test_rowspan_repeated_rectangle_emits_once(self):
        merged=(0,0,50,40)
        t=table([[merged,(50,0,100,20)],[merged,(50,20,100,40)]])
        body,info=native.convert_page(FakePage([line('Gas',3,2),line('1,2',53,2),line('3,4',53,22)],[t]))
        self.assertEqual(native.BeautifulSoup(body,'html.parser').find('td')['rowspan'],'2')
        self.assertEqual(cells(body),['Gas','1,2','3,4'])
        self.assert_inventory(info)

    def test_overlapping_tables_do_not_duplicate_glyphs(self):
        t=table([[(0,0,50,20)]])
        body,info=native.convert_page(FakePage([line('3,14',3,3)],[t,t]))
        self.assertEqual(cells(body),['3,14'])
        self.assertEqual(info['tables'],1)
        self.assert_inventory(info)

    def test_native_extraction_sequence_is_not_semantic_reordering(self):
        # PDF extraction order may be reversed relative to left-to-right x positions.
        body,info=native.convert_page(FakePage([line('B',30,3),line('A',3,3)]))
        self.assertLess(body.index('A'),body.index('B')) # object geometry determines order
        self.assert_inventory(info)
        # Inventory says nothing about which reading direction is correct for the document.

    def test_missing_unicode_remains_visible_and_is_counted(self):
        body,info=native.convert_page(FakePage([line('A\ufffdB',3,3)]))
        self.assertIn('\ufffd',body)
        self.assertEqual(info['unresolved_unicode'],1)
        self.assert_inventory(info)

    def test_empty_native_page_is_not_proof_of_readability(self):
        body,info=native.convert_page(FakePage([]))
        self.assertEqual(body,'')
        self.assertEqual(info['native_glyphs'],0)
        self.assert_inventory(info)

    def test_boundary_tie_stays_in_text_and_reports_ambiguity(self):
        # Centre on shared border is inside both cells: never silently choose the first.
        t=table([[(0,0,50,20),(50,0,100,20)]])
        body,info=native.convert_page(FakePage([line('L',3,3),line('R',48,3),line('x',75,3)],[t]))
        self.assertEqual(cells(body),['L','x'])
        self.assertIn('<p>R</p>',body)
        self.assertEqual(len(info['ambiguous_cell_assignments']),1)
        self.assertEqual(info['ambiguous_cell_assignments'][0]['text'],'R')
        self.assert_inventory(info)

    def test_empty_geometry_column_preserved_even_without_header(self):
        # A genuinely blank middle column and a detector gap are indistinguishable here.
        t=table([[(0,0,30,20),(30,0,60,20),(60,0,90,20)]])
        body,info=native.convert_page(FakePage([line('L',3,3),line('R',65,3)],[t]))
        self.assertEqual(cells(body),['L','','R'])
        self.assert_inventory(info)



    def test_overlap_assigns_largest_bbox_intersection(self):
        t=table([[(0,0,51,20),(50,0,100,20)]])
        body,info=native.convert_page(FakePage([line('L',3,3),line('R',49,3),line('x',75,3)],[t]))
        self.assertEqual(cells(body),['L','Rx'])
        self.assertEqual(info['ambiguous_cell_assignments'],[])
        self.assert_inventory(info)

    def test_same_line_source_sequence_can_disagree_with_spatial_order(self):
        combined=line('B',30,3)
        combined['spans']+=line('A',3,3)['spans']
        body,info=native.convert_page(FakePage([combined]))
        self.assertIn('<p>BA</p>',body)
        self.assert_inventory(info)

    def test_source_links_escape_caption_and_preserve_internal_target(self):
        page=SimpleNamespace(get_links=lambda:[{'from':(0,0,10,10),'page':1}],get_textbox=lambda rect:'A < B & C')
        markup,unresolved=native.source_links(page,{},3)
        self.assertIn('href="#pdf-page-2"',markup)
        self.assertIn('A &lt; B &amp; C',markup)
        self.assertEqual(unresolved,[])

    def test_ocr_is_pending_and_does_not_call_real_command(self):
        page=FakePage([])
        page.rect=native.fitz.Rect(0,0,100,100)
        page.derotation_matrix=native.fitz.Matrix(1,1)
        tsv='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t1\t10\t10\t20\t10\t88\t1,28\n'
        fake_image=SimpleNamespace(size=(100,100))
        with patch.object(native.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=tsv,stderr='')) as command, patch.object(native.Image,'open') as opened:
            opened.return_value.__enter__.return_value=fake_image
            text,info=native.raster_text(page,Path('never_read.png'))
        self.assertEqual(text,'1,28')
        self.assertFalse(info['ocr_verified'])
        self.assertEqual(info['ocr_median_confidence'],88)
        command.assert_called_once()

    def test_partial_native_overlap_must_not_suppress_extra_ocr_digits(self):
        page=FakePage([line('1',12,12)])
        page.rect=native.fitz.Rect(0,0,100,100)
        page.derotation_matrix=native.fitz.Matrix(1,1)
        tsv='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t1\t10\t10\t20\t10\t88\t1,28\n'
        with patch.object(native.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=tsv,stderr='')), patch.object(native.Image,'open') as opened:
            opened.return_value.__enter__.return_value=SimpleNamespace(size=(100,100))
            text,info=native.raster_text(page,Path('never_read.png'))
        self.assertEqual(text,'1,28')
        self.assertEqual(info['native_overlap_words_suppressed'],0)
        self.assertEqual(info['overlapping_native_conflicts'][0]['native_text'],'1')
        self.assertFalse(info['ocr_verified'])

    def test_complete_native_overlap_is_not_duplicated_by_ocr(self):
        page=FakePage([line('1,28',12,12)])
        page.rect=native.fitz.Rect(0,0,100,100)
        page.derotation_matrix=native.fitz.Matrix(1,1)
        tsv='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t1\t10\t10\t30\t15\t88\t1,28\n'
        with patch.object(native.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=tsv,stderr='')), patch.object(native.Image,'open') as opened:
            opened.return_value.__enter__.return_value=SimpleNamespace(size=(100,100))
            text,info=native.raster_text(page,Path('never_read.png'))
        self.assertEqual(text,'')
        self.assertEqual(info['native_overlap_words_suppressed'],1)
        self.assertEqual(info['overlapping_native_conflicts'],[])



class AssetIsolationTests(unittest.TestCase):
    def test_asset_manifest_without_source_receipt_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=self.make_source(tmp)
            output=Path(tmp)/'out';assets=output/'assets';checks=output/'_проверка'
            assets.mkdir(parents=True);checks.mkdir()
            native.Image.new('RGB',(5,5),'green').save(assets/'page_0001.png')
            old_digest=hashlib.sha256((assets/'page_0001.png').read_bytes()).hexdigest()
            (checks/'native_assets.json').write_text(json.dumps({'page_0001.png':old_digest}))
            with patch('builtins.print'),patch.object(native,'raster_text',side_effect=AssertionError('OCR must not run')):
                native.convert(source,output)
            self.assertNotEqual(hashlib.sha256((assets/'page_0001.png').read_bytes()).hexdigest(),old_digest)
            self.assertTrue(list((checks/'untrusted_assets').glob(old_digest+'_*')))
            self.assertTrue(list(checks.glob('unbound_assets_*.json')))

    def make_source(self,folder,name='source.pdf',suffix=''):
        path=Path(folder)/name
        with native.fitz.open() as doc:
            page=doc.new_page()
            page.insert_textbox(native.fitz.Rect(20,20,500,500),('A'*25+'\n')*6+suffix)
            doc.save(path)
        return path

    def test_different_pdf_cannot_reuse_output_folder(self):
        with tempfile.TemporaryDirectory(prefix='native-fixture-',dir=MODULE.parent) as temp:
            source=self.make_source(temp)
            other=self.make_source(temp,'other.pdf','DIFFERENT')
            output=Path(temp)/'draft'
            with patch('builtins.print'):
                native.convert(source,output)
            before=(output/'report.md').read_bytes()
            with self.assertRaisesRegex(ValueError,'different source PDF'):
                native.convert(other,output)
            self.assertEqual((output/'report.md').read_bytes(),before)

    def test_untrusted_existing_asset_is_archived_and_rerendered(self):
        with tempfile.TemporaryDirectory(prefix='native-fixture-',dir=MODULE.parent) as temp:
            source=self.make_source(temp)
            output=Path(temp)/'draft';assets=output/'assets';assets.mkdir(parents=True)
            wrong=b'not-the-source-page'
            (assets/'page_0001.png').write_bytes(wrong)
            with patch('builtins.print'),patch.object(native,'raster_text',side_effect=AssertionError('OCR must not run')):
                native.convert(source,output)
            self.assertNotEqual((assets/'page_0001.png').read_bytes(),wrong)
            archived=list((output/'_проверка/untrusted_assets').glob('*'))
            self.assertEqual(len(archived),1)
            self.assertEqual(archived[0].read_bytes(),wrong)
            manifest=json.loads((output/'_проверка/native_assets.json').read_text())
            self.assertEqual(manifest['page_0001.png'],hashlib.sha256((assets/'page_0001.png').read_bytes()).hexdigest())

    def test_prepared_asset_wrong_source_hash_not_copied(self):
        with tempfile.TemporaryDirectory(prefix='native-fixture-',dir=MODULE.parent) as temp:
            source=self.make_source(temp)
            prepared=Path(temp)/'prepared';prepared.mkdir()
            wrong=b'wrong-prepared-image'
            (prepared/'page_0001.png').write_bytes(wrong)
            (prepared/'pages.json').write_text(json.dumps({'source_sha256':'wrong-source','pages':[{'pdf_page':1,'image_sha256':hashlib.sha256(wrong).hexdigest()}]}))
            output=Path(temp)/'draft'
            with patch('builtins.print'),patch.object(native,'raster_text',side_effect=AssertionError('OCR must not run')):
                native.convert(source,output,image_source=prepared)
            self.assertNotEqual((output/'assets/page_0001.png').read_bytes(),wrong)
            record=json.loads((output/'_проверка/pages.json').read_text())['pages'][0]
            self.assertEqual(record['review_status'],'converted')
            self.assertFalse(record['semantic_source_review_completed'])

    def test_prepared_asset_changed_bytes_not_copied(self):
        with tempfile.TemporaryDirectory(prefix='native-fixture-',dir=MODULE.parent) as temp:
            source=self.make_source(temp)
            prepared=Path(temp)/'prepared';prepared.mkdir()
            wrong=b'changed-after-index'
            (prepared/'page_0001.png').write_bytes(wrong)
            (prepared/'pages.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'pages':[{'pdf_page':1,'image_sha256':'old-image-hash'}]}))
            output=Path(temp)/'draft'
            with patch('builtins.print'):
                native.convert(source,output,image_source=prepared)
            self.assertNotEqual((output/'assets/page_0001.png').read_bytes(),wrong)


class SourceRegressionTests(unittest.TestCase):
    def test_actual_gazprom57_decimal_notes(self):
        source=MODULE.parent.parent/'_источники/GAZP-2023-ОУР.pdf'
        if not source.is_file(): self.skipTest('Local original PDF not present')
        with native.fitz.open(source) as doc:
            body,info=native.convert_page(doc[56])
        self.assertIn('0,173<sup>2</sup>',body)
        self.assertIn('76,6<sup>2</sup>',body)
        self.assertIn('1,23<sup>12</sup>',body)
        self.assertIn('1,963',body)
        self.assertNotIn('1,963<sup>',body)
        self.assertTrue(info['all_native_glyphs_assigned_once'])
        self.assertTrue(info['rendered_native_character_inventory_matches'])


    def test_actual_gazprom115_amount_notes(self):
        source=MODULE.parent.parent/'_источники/GAZP-2023-ОУР.pdf'
        if not source.is_file(): self.skipTest('Local original PDF not present')
        with native.fitz.open(source) as doc:
            body,info=native.convert_page(doc[114])
        self.assertRegex(body,r'26[ \xa0]882,57<sup>5</sup>')
        self.assertRegex(body,r'17[ \xa0]806,48<sup>5</sup>')
        self.assertNotIn('882,575',body)
        self.assertNotIn('806,485',body)
        self.assertTrue(info['rendered_native_character_inventory_matches'])


if __name__=='__main__': unittest.main()
