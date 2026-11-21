"""Сверка числовых ячеек простых HTML-таблиц по координатам текста PDF."""
from collections import Counter, defaultdict
from dataclasses import dataclass
import html
import re
import unicodedata

import pymupdf

from table_layout import CELL, ROW, SPAN, text_key

NUMBER = r'[+−–-]?(?:\d{1,3}(?: \d{3})+|\d+)(?:[,.]\d+)?(?: ?%)?'
VALUE = re.compile(rf'(?:{NUMBER}|\({NUMBER}\)|[—–-])')
TABLE = re.compile(r'<table\b[^>]*>\s*(.*?)\s*</table>', re.I | re.S)
WRAPPERS = re.compile(r'\s*(?:</?(?:thead|tbody|tfoot)>\s*)*', re.I)
ALIGNMENT = re.compile(r'\s+style="text-align:\s*(?:left|right|center);?"', re.I)
NUMERIC_CELL = re.compile(
    r'<t[dh]\b[^>]*>\s*(?:<(?:strong|em|b|i)>\s*)*(?:[+(−–-]?\d|&minus;\d)', re.I,
)
INLINE = re.compile(r'</?(?:sup|sub|strong|em|b|i)>', re.I)
SEMANTIC_INLINE = re.compile(r'<(?:sup|sub|br)\b', re.I)
BREAK = re.compile(r'<br\s*/?>', re.I)
UNIT_HEADINGS = {'ед. изм.', 'ед. изм', 'ед. измерения', 'единица измерения', 'единицы измерения'}
TEXT_FLAGS = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES


def key(value):
    return text_key(unicodedata.normalize('NFC', value))


def cell_text(markup):
    return key(html.unescape(INLINE.sub('', BREAK.sub(' ', markup))))


def is_number(value):
    return bool(VALUE.fullmatch(value) and any(char.isdigit() for char in value))


@dataclass(frozen=True)
class Line:
    text: str
    bbox: tuple[float, float, float, float]
    has_index: bool = False

    @property
    def x(self):
        return (self.bbox[0] + self.bbox[2]) / 2

    @property
    def y(self):
        return (self.bbox[1] + self.bbox[3]) / 2

    @property
    def height(self):
        return self.bbox[3] - self.bbox[1]


def same_line(first, second):
    return abs(first.y - second.y) <= .42 * min(first.height, second.height)


def source_lines(page):
    lines = []
    for block in page.get_text('dict', flags=TEXT_FLAGS)['blocks']:
        for line in block.get('lines', ()):
            if line['dir'][0] < .99:
                continue
            spans = [span for span in line['spans'] if span['text'].strip()]
            value = key(''.join(span['text'] for span in line['spans']))
            if value:
                main = max(spans, key=lambda span: span['size'])
                has_index = any(
                    span['flags'] & pymupdf.TEXT_FONT_SUPERSCRIPT
                    or (span['size'] < .9 * main['size']
                        and abs(span['origin'][1] - main['origin'][1]) > .10 * main['size'])
                    for span in spans
                )
                lines.append(Line(value, tuple(line['bbox']), has_index))
    return lines


def header_positions(names, by_text):
    # A heading split over two consecutive lines may keep its right edge or centre.
    candidates = []
    for name in names:
        options = [line for line in by_text.get(name, ()) if not line.has_index]
        if not options:
            for index, char in enumerate(name):
                if char != ' ':
                    continue
                for first in by_text.get(name[:index], ()):
                    for second in by_text.get(name[index + 1:], ()):
                        if (not first.has_index and not second.has_index
                                and .55 * first.height <= second.y - first.y <= 1.45 * first.height
                                and min(abs(first.x - second.x),
                                        abs(first.bbox[2] - second.bbox[2])) <= .5 * first.height):
                            options.append(Line(name, (
                                min(first.bbox[0], second.bbox[0]), second.bbox[1],
                                max(first.bbox[2], second.bbox[2]), second.bbox[3],
                            )))
        candidates.append(options)
    for first in candidates[0]:
        group = [first]
        for options in candidates[1:]:
            hits = [line for line in options if same_line(first, line) and line.bbox[0] > group[-1].bbox[2]]
            if len(hits) != 1:
                break
            group.append(hits[0])
        else:
            yield group


def table_rows(table):
    """Keep raw cell spans so a repair can move just scalar contents."""
    markup = table[1]
    rows = []
    end = 0
    for row in ROW.finditer(markup):
        if not WRAPPERS.fullmatch(markup, end, row.start()):
            return []
        end = row.end()
        cells = []
        last = 0
        for cell in CELL.finditer(markup, row.start(1), row.end(1)):
            if cell.start() != row.start(1) + last:
                return []
            attrs = ALIGNMENT.sub('', cell[2])
            if any(width != '1' for _, width in SPAN.findall(attrs)) or SPAN.sub('', attrs).strip():
                return []
            last = cell.end() - row.start(1)
            cells.append(cell)
        if not cells or row.start(1) + last != row.end(1):
            return []
        rows.append(cells)
    if not WRAPPERS.fullmatch(markup, end) or len(rows) < 2 or len({len(row) for row in rows}) != 1:
        return []
    return rows


def read_row(label, headings, numbers, units=None):
    axes = [heading.x for heading in headings]
    gaps = [b - a for a, b in zip(axes, axes[1:])]
    cuts = [(a + b) / 2 for a, b in zip(axes, axes[1:])]
    left = max(label.bbox[2], axes[0] - gaps[0] / 2)
    right = axes[-1] + gaps[-1] / 2
    regions = [[] for _ in headings]
    if units is not None:
        regions[0] = [
            line for line in units
            if not line.has_index and same_line(label, line) and line.bbox[0] >= label.bbox[2]
            and left < line.bbox[2] < cuts[0] - .25 * line.height
        ]
    for line in numbers:
        if same_line(label, line) and line.bbox[0] >= label.bbox[2] and left < line.bbox[2] < right:
            column = sum(line.bbox[2] >= cut for cut in cuts)
            if any(abs(line.bbox[2] - cut) <= .25 * line.height for cut in cuts):
                return ()
            if column or units is None:
                regions[column].append(line)
    if any(len(region) != 1 for region in regions):
        return ()
    ordered = tuple(region[0] for region in regions)
    return ordered if all(a.bbox[2] < b.bbox[0] for a, b in zip(ordered, ordered[1:])) else ()


def match_rows(rows, labels, headings, by_text, numbers, first_heading, unit_values=None):
    headers = list(header_positions(headings, by_text))
    for header in headers:
        anchor = header[0]
        label_head = [line for line in by_text.get(first_heading, ())
                      if same_line(line, anchor) and line.bbox[2] < anchor.bbox[0]]
        if first_heading and len(label_head) != 1:
            continue
        boundary = [other[0].y for other in headers
                    if other[0].y > anchor.y and abs(other[0].x - anchor.x) < anchor.height]
        if label_head:
            left = label_head[0]
            boundary.extend(line.y for line in by_text[first_heading]
                            if line.y > anchor.y and abs(line.bbox[0] - left.bbox[0]) < anchor.height)
        next_header = min(boundary, default=float('inf'))
        matched = {}
        previous_y = anchor.y
        for i in rows:
            possible = [
                line for line in by_text.get(labels[i], ())
                if previous_y < line.y < next_header and line.bbox[2] < header[0].x
                and line.y - previous_y <= 4 * max(anchor.height, line.height)
                and (not label_head or abs(line.bbox[0] - label_head[0].bbox[0]) < 2 * anchor.height)
            ]
            units = by_text.get(unit_values[i], ()) if unit_values is not None else None
            if len(possible) == 1 and (cells := read_row(possible[0], header, numbers, units)):
                matched[i] = cells
                previous_y = possible[0].y
        yield matched


def neighboring_control(index, cells, controls):
    for neighbor in (index - 1, index + 1):
        if neighbor not in controls:
            continue
        other = controls[neighbor]
        if all(
            abs(first.y - second.y) <= 3 * max(first.height, second.height)
            and min(abs(first.bbox[0] - second.bbox[0]), abs(first.x - second.x),
                    abs(first.bbox[2] - second.bbox[2])) < .5 * min(first.height, second.height)
            for first, second in zip(cells, other, strict=True)
        ):
            return True
    return False


def issue(table, status, **details):
    return {'table': table, 'status': status, **details}


def header_signature(table):
    first_row = ROW.search(table[1])
    return tuple(cell_text(cell[3]) for cell in CELL.finditer(first_row[1])) if first_row else ()


def review_table(page, table, index, by_text, numbers, repair):
    rows = table_rows(table)
    if not rows:
        return [], 0, [issue(index, 'manual', reason='сложная или неполная сетка')]
    texts = [[cell_text(cell[3]) for cell in row] for row in rows]
    first, *headings = texts[0]
    has_units = bool(headings and headings[0].casefold() in UNIT_HEADINGS)
    numeric_start = 2 if has_units else 1
    if (len(texts[0]) < numeric_start + 2 or not all(headings) or len(set(headings)) != len(headings)
            or any(SEMANTIC_INLINE.search(cell[3]) for cell in rows[0][1:])):
        return [], 0, [issue(index, 'manual', reason='нет однозначных заголовков столбцов')]

    labels = [row[0] for row in texts]
    counts = Counter(labels[1:])
    unit_values = [row[1] for row in texts] if has_units else None
    numeric_rows = [i for i, row in enumerate(texts[1:], 1) if any(map(is_number, row[numeric_start:]))]
    anchors = [i for i, row in enumerate(texts[1:], 1)
               if row[0] and counts[row[0]] == 1 and all(not value or VALUE.fullmatch(value)
                                                        for value in row[numeric_start:])]
    eligible = {i for i in numeric_rows if not any(SEMANTIC_INLINE.search(cell[3]) for cell in rows[i][1:])}
    groups = [
        {i: cells for i, cells in group.items() if i in eligible}
        for group in match_rows(anchors, labels, headings, by_text, numbers, first, unit_values)
    ]
    groups = [group for group in groups if group]
    if len(groups) != 1:
        return [], 0, [issue(index, 'manual', reason='положение ячеек PDF не подтверждено однозначно')]

    matched = groups[0]
    # At least one untouched row must corroborate the table before any repair.
    controls = {i: cells[numeric_start - 1:] for i, cells in matched.items()
                if len(by_text[labels[i]]) == 1 and [line.text for line in cells] == texts[i][1:]}
    edits = []
    checked = 0
    findings = []
    for i, source in matched.items():
        if len(by_text[labels[i]]) != 1:
            findings.append(issue(index, 'manual', row=labels[i],
                                  reason='подпись строки повторяется в PDF на этой странице'))
            continue
        expected = [line.text for line in source]
        actual = texts[i][1:]
        if expected == actual:
            checked += len(source) - (numeric_start - 1)
            continue
        numeric_source = source[numeric_start - 1:]
        if not neighboring_control(i, numeric_source, controls):
            findings.append(issue(index, 'manual', row=labels[i],
                                  reason='границы спорной строки не подтверждены соседней контрольной строкой'))
            continue
        reread = [key(page.get_text('text', clip=pymupdf.Rect(line.bbox))) for line in source]
        if reread != expected:
            findings.append(issue(index, 'manual', row=labels[i],
                                  reason='повторное чтение области PDF не подтвердило значения'))
            continue
        checked += len(numeric_source)
        expected = expected[numeric_start - 1:]
        actual = texts[i][numeric_start:]
        repaired = False
        # Only a pure permutation is eligible for automatic repair. Move original
        # cell contents verbatim, including their signs, spacing and HTML entities.
        numeric_cells = rows[i][numeric_start:]
        raw_by_value = dict(zip(actual, (cell[3] for cell in numeric_cells), strict=True))
        if repair and len(raw_by_value) == len(numeric_source) and raw_by_value.keys() == set(expected):
            replacements = [raw_by_value[value] for value in expected]
            if all('<' not in raw and '>' not in raw for raw in replacements):
                edits.extend((table.start(1) + cell.start(3), table.start(1) + cell.end(3), raw)
                             for cell, raw in zip(numeric_cells, replacements, strict=True))
                repaired = True
        for heading, before, line in zip(texts[0][numeric_start:], actual, numeric_source, strict=True):
            if before != line.text:
                findings.append(issue(index, 'repaired' if repaired else 'manual', row=labels[i],
                                      column=heading, observed=before, expected=line.text,
                                      bbox=[round(coord, 2) for coord in line.bbox]))
    if len(matched) < len(numeric_rows):
        findings.append(issue(index, 'manual', reason='часть строк вне однозначной числовой сетки',
                              unverified_rows=len(numeric_rows) - len(matched)))
    return edits, checked, findings


def review_cells(text, page, rendered_markdown_tables=()):
    tables = [(match, 'html') for match in TABLE.finditer(text)]
    tables.extend((match, 'markdown') for snippet in rendered_markdown_tables
                  for match in TABLE.finditer(snippet))
    numeric = [(i, match, kind) for i, (match, kind) in enumerate(tables, 1)
               if NUMERIC_CELL.search(match[1])]
    if not numeric:
        return text, 0, []
    signatures = Counter(header_signature(table) for table, _ in tables)
    lines = source_lines(page)
    by_text = defaultdict(list)
    for line in lines:
        by_text[line.text].append(line)
    numbers = [line for line in lines if not line.has_index and VALUE.fullmatch(line.text)]
    edits = []
    checked = 0
    findings = []
    for index, table, kind in numeric:
        signature = header_signature(table)
        if signature and signatures[signature] > 1:
            findings.append(issue(index, 'manual', format=kind,
                                  reason='одинаковые заголовки у нескольких таблиц на странице'))
            continue
        changes, cells, notes = review_table(page, table, index, by_text, numbers, repair=kind == 'html')
        edits.extend(changes)
        checked += cells
        findings.extend({**note, 'format': kind} for note in notes)
    for start, end, replacement in reversed(edits):
        text = text[:start] + replacement + text[end:]
    return text, checked, findings
