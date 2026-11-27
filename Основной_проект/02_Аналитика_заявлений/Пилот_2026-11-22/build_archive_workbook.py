"""Build the reader workbook from the unchanged archived v1 CSV and coverage."""
import csv
import re
import textwrap
from pathlib import Path

from xlsxwriter import Workbook

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PROJECT = HERE.parents[1]
ARCHIVE = REPO / 'Старая_версия/03_итерация_3_пайплайн/data'


def read_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream, delimiter=';'))


def main():
    companies = {row['company_id']: row['company']
                 for row in read_rows(PROJECT / '00_Отчёты/Реестр_отчётов.csv')}
    claims = read_rows(ARCHIVE / 'out/claims.csv')
    rows = [['Компания', 'Год', 'Отчёт', 'Стр.', 'ESG', 'Тип', 'Тема', 'Заявление', 'ID']]
    for claim in claims:
        quote = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]', ' ', claim['text'])
        rows.append([companies[claim['company_id']], int(claim['year']), claim['report_id'],
                     int(claim['page']), claim['esg_block'], claim['type'], claim['topic'],
                     quote, claim['claim_id']])
    coverage = [['Компания', 'Заявлений', 'Отчётов', 'Блоки', 'Годы']]
    coverage.extend([companies[row['company_id']], int(row['n_claims']), int(row['n_reports']),
                     row['blocks'], row['years']] for row in read_rows(ARCHIVE / 'extract/v1/coverage.csv'))
    with Workbook(HERE / 'ESG_30_компаний_v1.xlsx',
                  {'strings_to_formulas': False, 'strings_to_urls': False}) as book:
        header = book.add_format({'bg_color': '#155B75', 'font_color': '#FFFFFF', 'bold': True,
                                  'valign': 'vcenter', 'font_size': 11})
        body = [book.add_format({'bg_color': color, 'text_wrap': True,
                                 'valign': 'vcenter', 'font_size': 11})
                for color in ('#FFFFFF', '#EDF6F9')]
        for name, table, widths in [
            ('Архив v1', rows, [172, 70, 158, 64, 65, 120, 160, 535, 136]),
            ('Охват', coverage, [282, 130, 112, 108, 209]),
        ]:
            sheet = book.add_worksheet(name)
            sheet.hide_gridlines(2)
            sheet.freeze_panes(1, 0)
            sheet.autofilter(0, 0, len(table) - 1, len(widths) - 1)
            sheet.write_row(0, 0, table[0], header)
            sheet.set_row(0, 29)
            for column, width in enumerate(widths):
                sheet.set_column_pixels(column, column, width)
            for index, row in enumerate(table[1:], 1):
                lines = 1
                if table is rows:
                    lines = sum(max(1, len(textwrap.wrap(line, width=66)))
                                for line in row[7].splitlines())
                sheet.set_row(index, max(33, lines * 15 + 12))
                sheet.write_row(index, 0, row, body[index % 2])


if __name__ == '__main__':
    main()
