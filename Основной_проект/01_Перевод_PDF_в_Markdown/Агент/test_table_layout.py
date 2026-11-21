import unittest
from unittest.mock import patch

import pymupdf

from table_layout import Cell, candidate, displaced_cells, read_rows, remove_year_spacers, review_tables, table_markup


def cells(rows):
    return [[Cell('th' if i == 0 else 'td', 1, text) for text in row] for i, row in enumerate(rows)]


class TableLayoutTests(unittest.TestCase):
    def test_rebuild_with_same_spelling_and_unique_grid(self):
        raw = cells([
            ['Показатель по объекту', '2025 2024'],
            ['Всего, тыс. т', '40,7', '32,2'],
            ['Итого, тыс. т', '403,7', '412,2'],
        ])
        grid = [
            ['Показатель по объекту', '2025', '2024'],
            ['Всего, тыс. т', '40,7', '32,2'],
            ['Итого, тыс. т', '403,7', '412,2'],
        ]
        self.assertEqual(candidate(raw, [grid, grid]), tuple(map(tuple, grid)))
        wrong_spelling = [grid[0], ['Всего, тыс. т', '40.7', '32,2'], grid[2]]
        self.assertIsNone(candidate(raw, [wrong_spelling]))
        ambiguous = [grid[0], ['Всего, тыс. т', '32,2', '40,7'], grid[2]]
        self.assertIsNone(candidate(raw, [grid, ambiguous]))

    def test_continuation_requires_unique_source_and_only_one_row_with_values(self):
        raw = cells([
            ['Показатель', '2025', '2024'],
            ['Расход первичных', '', ''],
            ['энергоресурсов', '12', '8'],
        ])
        original = table_markup(raw)
        pair = {('Расход первичных', 'энергоресурсов')}
        with patch('table_layout.pdf_grids', return_value=([], [])):
            after, repaired, issues = review_tables(original, None, pair)
            self.assertEqual(repaired, 1)
            self.assertFalse(issues)
            self.assertEqual(
                read_rows(after.removeprefix('<table>').removesuffix('</table>').strip()),
                [raw[0], [Cell('td', 1, 'Расход первичных энергоресурсов'), *raw[2][1:]]],
            )
            self.assertEqual(review_tables(original, None)[0], original)
            raw[1][1] = Cell('td', 1, '16')
            self.assertEqual(review_tables(table_markup(raw), None, pair)[1], 0)

    def test_pull_cells_only_from_consecutive_adjacent_paragraphs(self):
        raw = cells([['Год', 'Объект'], ['2024', 'Цех'], ['2025', 'Завод', '31']])
        grid = [['Год', 'Объект', 'Объём'], ['2024', 'Цех', '29'], ['2025', 'Завод', '31']]
        tail = '\n\n<p>Объём</p>\n<p>29</p>'
        self.assertEqual(displaced_cells(raw, [grid], tail + '\n<p>Сноска</p>'),
                         (tuple(map(tuple, grid)), len(tail)))
        self.assertIsNone(displaced_cells(raw, [grid], tail.replace('29', '28')))
        self.assertIsNone(displaced_cells(raw, [grid], tail.replace('<p>29', '<p>Сноска</p><p>29')))
        self.assertIsNone(displaced_cells(raw, [grid[::-1]], tail))

    def test_preserve_rich_tables(self):
        for body in ('<td rowspan="2">Цех</td>', '<td><a href="#x">Цех</a></td>'):
            original = '<table><tr>' + body + '</tr></table>'
            with patch('table_layout.pdf_grids') as grids:
                self.assertEqual(review_tables(original, None), (original, 0, []))
                grids.assert_not_called()

    def test_remove_repeated_empty_year_spacers_only(self):
        source = cells([
            ['Показатель', '', '', '2021', '', '', '2022', '', '', '2023', '', '', '2024'],
            ['Расход воды', '', '', '10', '', '', '12', '', '', '11', '', '', '9'],
            ['Расход газа', '', '', '5', '', '', '7', '', '', '8', '', '', '6'],
            ['Примечание', '', '', '', '', '', '', '', '', '', '', '', ''],
        ])
        fixed, removed = remove_year_spacers(source)
        self.assertEqual(removed, 8)
        self.assertEqual(fixed[1], [source[1][i] for i in (0, 3, 6, 9, 12)])
        self.assertEqual(remove_year_spacers(fixed), (fixed, 0))
        source[2][4] = Cell('td', 1, 'Сноска')
        self.assertEqual(remove_year_spacers(source), (source, 0))

    def test_pdf_grid_repairs_a_real_layout_without_moving_other_text(self):
        with pymupdf.open() as pdf:
            page = pdf.new_page(width=380, height=230)
            data = [
                ['Indicator by location', '2025', '2024'],
                ['Plant A, tons', '42.1', '45.6'],
                ['Plant B, tons', '14.0', '19.8'],
            ]
            page.draw_rect(pymupdf.Rect(20, 20, 360, 140))
            for x in (235, 295):
                page.draw_line((x, 20), (x, 140))
            for y in (60, 100):
                page.draw_line((20, y), (360, y))
            for i, row in enumerate(data):
                for x, item in zip((26, 243, 304), row, strict=True):
                    page.insert_text((x, 45 + 40 * i), item)
            damaged = [['Indicator by location', '2025 2024'], *data[1:]]
            good = table_markup(cells(data))
            surrounding = '\n\n<p>Independent note</p>\n'
            result = review_tables(table_markup(cells(damaged)) + surrounding, page)
            self.assertEqual(result, (good + surrounding, 1, []))
            self.assertEqual(review_tables(result[0], page), (result[0], 0, []))


if __name__ == '__main__':
    unittest.main()
