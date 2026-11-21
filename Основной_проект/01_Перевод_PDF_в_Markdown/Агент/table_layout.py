"""Сверка обычных HTML-таблиц с сеткой и текстом физической PDF-страницы."""
from collections import Counter
from dataclasses import dataclass
import html
import re

import pymupdf

TABLE = re.compile(r'<table>\s*(.*?)\s*</table>', re.I | re.S)
ROW = re.compile(r'\s*<tr>\s*(.*?)\s*</tr>\s*', re.I | re.S)
CELL = re.compile(r'\s*<(td|th)([^>]*)>(.*?)</\1>\s*', re.I | re.S)
SPAN = re.compile(r'\s+(colspan|rowspan)="([1-9][0-9]*)"', re.I)
PLAIN_PARAGRAPH = re.compile(r'\s*<p>([^<>]*?)</p>', re.S)
BREAK = re.compile(r'<br\s*/?>', re.I)
TOKEN = re.compile(r'\w+|[^\w\s]')
YEAR = re.compile(r'(?:19|20)\d{2}')
PURE_VALUE = re.compile(r'[\d\s.,%()<>+−—–-]+')
NUMERIC = re.compile(r'(?<!\w)[+−–-]?\d+(?:[ ,.]\d+)*%?(?!\w)')


@dataclass(frozen=True)
class Cell:
    tag: str
    width: int
    text: str


def read_rows(markup):
    rows = []
    end = 0
    for row in ROW.finditer(markup):
        if row.start() != end:
            return []
        end = row.end()
        cells = []
        last = 0
        for match in CELL.finditer(row[1]):
            attributes = dict(SPAN.findall(match[2].lower()))
            if (match.start() != last or SPAN.sub('', match[2]).strip()
                    or attributes.get('rowspan', '1') != '1'):
                return []
            last = match.end()
            plain = BREAK.sub('\n', match[3])
            if '<' in plain or '>' in plain:
                return []
            cells.append(Cell(match[1].lower(), int(attributes.get('colspan', '1')), html.unescape(plain).strip()))
        if not cells or last != len(row[1]):
            return []
        rows.append(cells)
    return rows if end == len(markup) else []


def text_key(value):
    return ' '.join(value.replace('\u00ad', '').split())


def inventory(rows):
    return Counter(TOKEN.findall(' '.join(text_key(value) for row in rows for value in row)))


def numeric_inventory(rows):
    numbers = []
    for row in rows:
        for value in row:
            words = text_key(value).split()
            if len(words) > 1 and all(YEAR.fullmatch(word) for word in words):
                numbers.extend(words)
            else:
                numbers.extend(NUMERIC.findall(text_key(value)))
    return Counter(numbers)


def anomalies(rows):
    if len(rows) < 3:
        return []
    widths = [sum(cell.width for cell in row) for row in rows]
    details = []
    if max(widths) >= 3 and any(1 < width < max(widths) for width in widths):
        details.append('разное число столбцов')
    for row in rows:
        text = [text_key(cell.text) for cell in row if cell.text.strip()]
        if any(len(value.split()) >= 2 and all(YEAR.fullmatch(word) for word in value.split())
               for value in text):
            details.append('несколько лет в одной ячейке')
            break
    if (sum(len(row) == 1 or sum(bool(cell.text.strip()) for cell in row) <= 1 for row in rows) >= 2
            and any(sum(bool(cell.text.strip()) for cell in row) >= 3 for row in rows)):
        details.append('часть строк содержит только один заполненный столбец')
    if (any(len(row) >= 3 and text_key(row[0].text) and PURE_VALUE.fullmatch(text_key(row[0].text))
            and all(not cell.text or PURE_VALUE.fullmatch(text_key(cell.text)) for cell in row)
            for row in rows[1:])
            and any(len(row) >= 3 and any(char.isalpha() for char in row[0].text) for row in rows[1:])):
        details.append('число вместо подписи строки')
    return details


def join_continuation_rows(rows, pairs):
    """Reattach a label continuation when exactly one of its two rows contains data."""
    if not rows or any(cell.width != 1 for row in rows for cell in row):
        return rows, 0
    if len({len(row) for row in rows}) != 1 or len(rows[0]) < 2:
        return rows, 0

    output = []
    joined = 0
    previous_part = ''
    for i, row in enumerate(rows):
        current = text_key(row[0].text)
        if i >= 2 and (previous_part, current) in pairs:
            previous = output[-1]
            first_has_data = any(cell.text for cell in previous[1:])
            second_has_data = any(cell.text for cell in row[1:])
            if first_has_data != second_has_data and all(cell.tag == 'td' for cell in previous + row):
                label = text_key(previous[0].text) + ' ' + current
                values = previous[1:] if first_has_data else row[1:]
                output[-1] = [Cell('td', 1, label), *values]
                joined += 1
            else:
                output.append(row)
        else:
            output.append(row)
        previous_part = current
    return output, joined


def remove_year_spacers(rows):
    """Collapse repeated wholly empty columns between consecutive year labels."""
    if len(rows) < 4 or any(cell.width != 1 for row in rows for cell in row):
        return rows, 0
    if len({len(row) for row in rows}) != 1 or len(rows[0]) < 11:
        return rows, 0
    used = [any(cell.text for cell in column) for column in zip(*rows)]
    for header in rows[:3]:
        years = [(i, int(cell.text)) for i, cell in enumerate(header) if YEAR.fullmatch(cell.text)]
        if len(years) < 4 or len({year for _, year in years}) != len(years):
            continue
        gaps = [
            range(left + 1, right)
            for (left, start), (right, end) in zip(years, years[1:])
            if abs(end - start) == 1 and right - left >= 3 and not any(used[left + 1:right])
        ]
        if len(gaps) != len(years) - 1:
            continue
        spacers = {i for gap in gaps for i in gap}
        first_year = years[0][0]
        if first_year >= 3 and used[0] and not any(used[1:first_year]):
            spacers.update(range(1, first_year))
        return [[cell for i, cell in enumerate(row) if i not in spacers] for row in rows], len(spacers)
    return rows, 0


def complete_gaps(page, table):
    """Read missing cell rectangles only if intact rows give one unambiguous lattice."""
    rows = [row.cells for row in table.rows]
    full = [row for row in rows if all(cell is not None for cell in row)]
    if len(full) < 2 or len(full) == len(rows) or len(rows) < 4:
        return None
    columns = [(round(cell[0], 1), round(cell[2], 1)) for cell in full[0]]
    if any(abs(left[1] - right[0]) > .2 for left, right in zip(columns, columns[1:])):
        return None
    grid = []
    last_bottom = None
    for row in rows:
        real = [cell for cell in row if cell is not None]
        if not real:
            return None
        top, bottom = real[0][1], real[0][3]
        if last_bottom is not None and abs(last_bottom - top) > .2:
            return None
        last_bottom = bottom
        values = []
        for (left, right), cell in zip(columns, row, strict=True):
            if cell is not None and max(abs(cell[0] - left), abs(cell[2] - right),
                                       abs(cell[1] - top), abs(cell[3] - bottom)) > .2:
                return None
            clip = pymupdf.Rect(left, top, right, bottom)
            values.append(text_key(page.get_text('text', clip=clip)))
        grid.append(values)
    return grid


def pdf_grids(page, include_gaps=False):
    complete = []
    incomplete = []
    for strategy in ('lines_strict', 'lines'):
        try:
            tables = page.find_tables(strategy=strategy).tables
            for table in tables:
                if table.row_count < 3 or not 2 <= table.col_count <= 24:
                    continue
                if all(all(cell is not None for cell in row.cells) for row in table.rows):
                    grid = table.extract()
                    if (len(grid) == table.row_count and all(len(row) == table.col_count for row in grid)
                            and all(any(row) for row in grid)):
                        complete.append([[text_key(value or '') for value in row] for row in grid])
                elif include_gaps and strategy == 'lines' and (grid := complete_gaps(page, table)):
                    incomplete.append(grid)
        except (ValueError, RuntimeError, IndexError, TypeError, ZeroDivisionError):
            continue
    return complete, incomplete


def displaced_cells(old, grids, tail):
    """Accept a candidate only if all displaced cells are the next plain paragraphs."""
    if not tail.lstrip().startswith('<p>'):
        return None
    old_rows = [[text_key(cell.text) for cell in row if cell.text] for row in old]
    choices = set()
    for grid in grids:
        if len(grid) != len(old_rows):
            continue
        missing = []
        for observed, expected in zip(old_rows, grid, strict=True):
            seen = iter(observed)
            value = next(seen, None)
            # Empty source cells do not carry transferable content.
            for cell in filter(None, expected):
                if cell == value:
                    value = next(seen, None)
                else:
                    missing.append(cell)
            if value is not None:
                break
        else:
            if not missing:
                continue
            end = 0
            for value in missing:
                match = PLAIN_PARAGRAPH.match(tail, end)
                if not match or text_key(html.unescape(match[1])) != value:
                    break
                end = match.end()
            else:
                # A single, exact assignment must preserve all numeric values.
                choices.add((tuple(tuple(row) for row in grid), end))
    return next(iter(choices)) if len(choices) == 1 else None


def candidate(old, grids):
    old_grid = [[cell.text for cell in row] for row in old]
    old_tokens = inventory(old_grid)
    numeric = numeric_inventory(old_grid)
    # The PDF lattice decides placement. Equal text alone is insufficient:
    # require an unambiguous geometric result and preserve every numeric spelling.
    if old_tokens.total() < 12 or not numeric:
        return None
    old_anomalies = anomalies(old)
    choices = set()
    for new in grids:
        if (inventory(new) != old_tokens or numeric_inventory(new) != numeric
                or any(not any(row) for row in zip(*new))):
            continue
        proposed = [[Cell('td', 1, value) for value in row] for row in new]
        if len(anomalies(proposed)) < len(old_anomalies):
            choices.add(tuple(tuple(row) for row in new))
    return next(iter(choices)) if len(choices) == 1 else None


def table_markup(rows):
    def render_cell(cell):
        value = '<br/>'.join(html.escape(line, quote=False) for line in cell.text.split('\n'))
        return f'<{cell.tag}>{value}</{cell.tag}>'

    body = ['<tr>' + ''.join(render_cell(cell) for cell in row) + '</tr>' for row in rows]
    return '<table>\n' + '\n'.join(body) + '\n</table>'


def has_simple_header(rows):
    return len({cell.tag for cell in rows[0]}) == 1 and all(
        cell.tag == 'td' for row in rows[1:] for cell in row
    )


def review_tables(text, page, pairs=()):
    items = []
    for match in TABLE.finditer(text):
        if not (rows := read_rows(match[1])):
            continue
        compact, spacers = remove_year_spacers(rows)
        joined, count = join_continuation_rows(compact, pairs)
        issues = anomalies(joined)
        if count or spacers or issues:
            items.append((match, joined, count or spacers, issues))
    if not items:
        return text, 0, []

    eligible = [(match, joined, issues) for match, rows, joined, issues in items
                if issues and has_simple_header(rows) and all(cell.width == 1 for row in rows for cell in row)]
    include_gaps = any(not joined and 'разное число столбцов' in issues
                       and text[match.end():].lstrip().startswith('<p>')
                       for match, joined, issues in eligible)
    grids, incomplete = pdf_grids(page, include_gaps) if eligible else ([], [])
    changes = []
    review = Counter()
    for match, rows, joined, issues in items:
        # Preserve link/rich markup and existing merged headings.
        grid = None
        end = match.end()
        if issues and has_simple_header(rows) and all(cell.width == 1 for row in rows for cell in row):
            grid = candidate(rows, grids)
            if grid is None and not joined and 'разное число столбцов' in issues:
                restored = displaced_cells(rows, incomplete, text[end:])
                if restored is not None:
                    grid, consumed = restored
                    end += consumed
        if grid is not None:
            header = rows[0][0].tag
            replacement = [[Cell(header if i == 0 else 'td', 1, value) for value in row]
                           for i, row in enumerate(grid)]
            changes.append((match.start(), end, table_markup(replacement)))
        elif joined:
            changes.append((match.start(), end, table_markup(rows)))
        if issues and grid is None:
            review.update(issues)
    for start, end, replacement in reversed(changes):
        text = text[:start] + replacement + text[end:]
    return text, len(changes), sorted(review)
