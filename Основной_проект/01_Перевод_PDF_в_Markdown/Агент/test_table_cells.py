import csv
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import pymupdf

from convert_pdf import markdown_tables, page_parts
from table_cells import TABLE, cell_text, review_cells, table_rows

HEADER = ('Indicator, tons', '2023', '2024')
ROWS = [('Water', '1 235', '2 461'), ('Waste', '(197)', '+309'), ('Heat', '11', '10')]
SWAPS = [('Water', '2 461', '1 235'), ('Waste', '+309', '(197)'), ROWS[2]]
NOTE = '\n\n<p>Independent note: totals and source remain here.</p>'


def markup(rows, headings=HEADER):
    all_rows = [headings, *rows]
    tags = ['<tr>' + ''.join(f'<td>{value}</td>' for value in row) + '</tr>' for row in all_rows]
    return '<table style="min-width:720px;">\n' + '\n'.join(tags) + '\n</table>' + NOTE


class TableCellTests(unittest.TestCase):
    def setUp(self):
        self.doc = pymupdf.open()
        self.addCleanup(self.doc.close)
        self.page = self.doc.new_page(width=670, height=700)
        self.draw(HEADER, ROWS)

    def draw(self, header, rows, offset=0):
        for i, row in enumerate([header, *rows]):
            for x, value in zip((40, 300, 426), row, strict=True):
                self.page.insert_text((x, 65 + 30 * i + offset), value, fontsize=14)

    def test_repair_swaps_from_source_without_changing_markup(self):
        before = markup([SWAPS[0], ROWS[1], SWAPS[2]])
        fixed, compared, findings = review_cells(before, self.page)
        self.assertEqual(fixed, markup(ROWS))
        self.assertEqual(compared, 6)
        self.assertEqual([(item['row'], item['column'], item['status']) for item in findings], [
            ('Water', '2023', 'repaired'), ('Water', '2024', 'repaired'),
        ])
        self.assertEqual([
            self.page.get_text(clip=pymupdf.Rect(item['bbox']) + (-.1, -.1, .1, .1)).strip()
            for item in findings
        ], ['1 235', '2 461'])
        self.assertEqual(review_cells(fixed, self.page), (fixed, 6, []))

    def test_swap_preserves_plus_and_accounting_negative(self):
        before = markup([ROWS[0], SWAPS[1], ROWS[2]])
        fixed, compared, findings = review_cells(before, self.page)
        self.assertEqual((fixed, compared), (markup(ROWS), 6))
        self.assertEqual([item['expected'] for item in findings], ['(197)', '+309'])

    def test_repair_requires_unit_in_the_correct_pdf_column(self):
        headings = ('Indicator', 'Ед. изм.', '2023', '2024')
        rows = [('Water', 'm3', '123', '456'), ('Waste', 'tons', '789', '900')]
        page = self.doc.new_page(width=670, height=420)
        page.insert_font(fontname='unicode', fontbuffer=pymupdf.Font('helv').buffer)
        for i, row in enumerate([headings, *rows]):
            for x, value in zip((40, 206, 315, 427), row, strict=True):
                page.insert_text((x, 55 + 28 * i), value, fontname='unicode', fontsize=13)
        swapped = markup([('Water', 'm3', '456', '123'), rows[1]], headings)
        fixed, compared, findings = review_cells(swapped, page)
        self.assertEqual((fixed, compared), (markup(rows, headings), 4))
        self.assertEqual([item['column'] for item in findings], ['2023', '2024'])
        wrong_unit = swapped.replace('>m3<', '>tons<')
        preserved, compared, findings = review_cells(wrong_unit, page)
        self.assertEqual((preserved, compared), (wrong_unit, 2))
        self.assertTrue(all(item['status'] == 'manual' for item in findings))

    def test_do_not_cross_into_correctly_labeled_row_of_next_table(self):
        self.page = self.doc.new_page(width=670, height=700)
        self.draw(HEADER, [('Control', '7', '8'), ('Ground', '101', '202')])
        self.page.insert_text((40, 143), 'water', fontsize=14)
        self.draw(('Indicator, tons', '2025', '2026'), [('Ground water', '202', '101')], offset=130)
        before = markup([('Control', '7', '8'), ('Ground water', '101', '202')])
        fixed, compared, findings = review_cells(before, self.page)
        self.assertEqual((fixed, compared), (before, 2))
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['status'], 'manual')
        self.assertNotIn('bbox', findings[0])

    def test_send_changed_sign_or_number_to_manual_review(self):
        before = markup([ROWS[0], ('Waste', '197', '+309'), ROWS[2]])
        fixed, _, findings = review_cells(before, self.page)
        self.assertEqual(fixed, before)
        self.assertEqual([(item['observed'], item['expected'], item['status']) for item in findings],
                         [('197', '(197)', 'manual')])

    def test_do_not_move_superscripts_or_merged_headers(self):
        rich = markup([('Water', '2 461<sup></sup>', '1 235'), *ROWS[1:]])
        saved, compared, findings = review_cells(rich, self.page)
        self.assertEqual((saved, compared), (rich, 4))
        self.assertEqual(findings[0]['status'], 'manual')
        merged = markup(SWAPS).replace('<td>2023</td>', '<td colspan="2">2023</td>')
        fixed, compared, findings = review_cells(merged, self.page)
        self.assertEqual((fixed, compared), (merged, 0))
        self.assertEqual(findings[0]['status'], 'manual')

    def test_pdf_superscript_is_not_a_digit_of_value(self):
        self.page = self.doc.new_page(width=670, height=700)
        self.draw(HEADER, [('Water', '', '456'), ('Waste', '789', '900')])
        self.page.insert_htmlbox(pymupdf.Rect(299, 80, 398, 108), '<span style="font-size:13pt">12<sup>3</sup></span>')
        before = markup([('Water', '456', '123'), ('Waste', '789', '900')])
        fixed, compared, findings = review_cells(before, self.page)
        self.assertEqual((fixed, compared), (before, 2))
        self.assertEqual(findings[0]['status'], 'manual')

    def test_ambiguous_second_source_table_blocks_repair(self):
        self.draw(HEADER, ROWS, offset=200)
        before = markup([SWAPS[0], *ROWS[1:]])
        fixed, compared, findings = review_cells(before, self.page)
        self.assertEqual((fixed, compared), (before, 0))
        self.assertEqual(findings[0]['status'], 'manual')

    def test_identical_headers_with_merged_neighbor_block_cell_findings(self):
        merged = markup(ROWS).replace('<td>1 235</td><td>2 461</td>', '<td colspan="2">3 696</td>')
        before = merged + '\n\n' + markup([SWAPS[0], *ROWS[1:]])
        fixed, compared, findings = review_cells(before, self.page)
        self.assertEqual((fixed, compared), (before, 0))
        self.assertEqual([item['status'] for item in findings], ['manual', 'manual'])
        for item in findings:
            self.assertIn('одинаковые заголовки', item['reason'])
            self.assertNotIn('bbox', item)

    def test_repeated_pdf_labels_block_mismatch_from_wrong_table(self):
        self.page = self.doc.new_page(width=1130, height=420)
        self.draw(HEADER, ROWS)
        for row, values in enumerate([HEADER, SWAPS[0], *ROWS[1:]]):
            for column, (x, value) in enumerate(zip((560, 820, 946), values, strict=True)):
                # Years in the second header are on a separate baseline.
                y = 65 + 30 * row + (13 if row == 0 and column > 0 else 0)
                self.page.insert_text((x, y), value, fontsize=14)
        before = markup([SWAPS[0], *ROWS[1:]])
        fixed, compared, findings = review_cells(before, self.page)
        self.assertEqual((fixed, compared), (before, 0))
        self.assertTrue(any(note.get('row') == 'Water' for note in findings))
        self.assertTrue(all(note['status'] == 'manual' and 'bbox' not in note for note in findings))

    def test_open_finding_if_local_reread_disagrees(self):
        before = markup([SWAPS[0], *ROWS[1:]])
        extract = self.page.get_text

        def get_text(*args, **kwargs):
            return '' if 'clip' in kwargs else extract(*args, **kwargs)

        with patch.object(self.page, 'get_text', side_effect=get_text):
            fixed, compared, findings = review_cells(before, self.page)
        self.assertEqual((fixed, compared), (before, 4))
        self.assertEqual([item['status'] for item in findings], ['manual'])
        self.assertNotIn('bbox', findings[0])

    def test_markdown_pipe_table_keeps_format_and_reports_exact_cell(self):
        before = ('| Indicator, tons | 2023 | 2024 |\n| :--- | ---: | --- |\n'
                  '| Water | 2 461 | 1 235 |\n| Waste | (197) | +309 |\n| Heat | 11 | 10 |\n')
        fixed, compared, findings = review_cells(before, self.page, markdown_tables(before))
        self.assertEqual((fixed, compared), (before, 6))
        self.assertEqual([(item['column'], item['format'], item['status']) for item in findings],
                         [('2023', 'markdown', 'manual'), ('2024', 'markdown', 'manual')])


@unittest.skipUnless(os.environ.get('GREENWASHING_TEST_PDF_DIR'), 'нужны исходные PDF корпуса')
class RealTableCellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = Path(__file__).resolve().parents[2]
        cls.pdf_dir = Path(os.environ['GREENWASHING_TEST_PDF_DIR'])
        with (cls.project / '00_Отчёты/Реестр_отчётов.csv').open(encoding='utf-8-sig', newline='') as stream:
            cls.registry = {row['report_id']: row for row in csv.DictReader(stream, delimiter=';')}

    def load_page(self, report, number):
        entry = self.registry[report]
        document = (self.project / entry['repository_path']).read_text(encoding='utf-8')
        _, pages = page_parts(document, int(entry['physical_pages']))
        pdf = pymupdf.open(self.pdf_dir / f'{report}.pdf')
        self.addCleanup(pdf.close)
        return pages[number - 1], pdf[number - 1]

    def test_restore_permutations_in_original_reports(self):
        samples = (
            ('SIBR-2024-ИО', 42, 'Выручка1', ('2023', '2024'), ('1 086 987', '1 170 895')),
            ('MAGN-2024-ИО', 112, 'Нормативно очищенные сточные воды', ('Группа ММК', 'ММК'), ('13 249', '3 139')),
            ('MAGN-2023-ИО', 231, '20%', ('2023 год', '2022 год'), ('128 342 494', '58 693 005')),
        )
        for report, number, label, headings, values in samples:
            with self.subTest(report=report, page=number):
                content, page = self.load_page(report, number)
                candidates = []
                for table in TABLE.finditer(content):
                    rows = table_rows(table)
                    if not rows or tuple(cell_text(cell[3]) for cell in rows[0][1:3]) != headings:
                        continue
                    candidates.extend([(table.start(1), row[1], row[2]) for row in rows[1:]
                                       if cell_text(row[0][3]) == label])
                self.assertEqual(len(candidates), 1)
                offset, left, right = candidates[0]
                self.assertEqual((cell_text(left[3]), cell_text(right[3])), values)
                altered = (content[:offset + left.start(3)] + right[3]
                           + content[offset + left.end(3):offset + right.start(3)] + left[3]
                           + content[offset + right.end(3):])
                fixed, _, findings = review_cells(altered, page, markdown_tables(altered))
                self.assertEqual(fixed, content)
                self.assertEqual([(note['column'], note['expected']) for note in findings
                                  if note['status'] == 'repaired'], list(zip(headings, values, strict=True)))

    def test_duplicate_headers_on_akron_spread(self):
        content, page = self.load_page('AKRN-2025-ИО', 74)
        fixed, _, findings = review_cells(content, page, markdown_tables(content))
        self.assertEqual(fixed, content)
        self.assertEqual(sum('одинаковые заголовки' in note.get('reason', '') for note in findings), 3)
        self.assertFalse(any('bbox' in note for note in findings))

    def test_energy_table_with_units_in_lukoil_report(self):
        content, page = self.load_page('LKOH-2024-ОУР', 21)
        original = re.compile(r'(<td[^>]*>млн ГДж</td><td[^>]*>)471(</td><td[^>]*>)459(</td>)')
        altered, count = original.subn(r'\g<1>459\g<2>471\g<3>', content)
        self.assertEqual(count, 1)
        fixed, _, findings = review_cells(altered, page, markdown_tables(altered))
        self.assertEqual(fixed, content)
        self.assertEqual([(note['column'], note['expected']) for note in findings
                          if note['status'] == 'repaired'], [('2023', '471'), ('2024', '459')])


if __name__ == '__main__':
    unittest.main()
