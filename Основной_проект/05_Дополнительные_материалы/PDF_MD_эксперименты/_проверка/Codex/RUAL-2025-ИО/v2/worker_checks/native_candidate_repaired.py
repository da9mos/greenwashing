"""Reusable local draft for Codex: source glyphs, table geometry and source images.

No LLM and no API. Character accounting proves native-text coverage, not visual
correctness of the PDF font map or semantic acceptance of page reading order.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import html
import csv
import io
import json
import statistics
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import unicodedata
sys.path.insert(0, '/private/tmp/sber-pdf-libs')
import pymupdf as fitz
from PIL import Image
sys.path.insert(0, '/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
IMPLEMENTATION_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.part')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def inside(box, x, y):
    return box[0] - .1 <= x <= box[2] + .1 and box[1] - .1 <= y <= box[3] + .1


def render_glyphs(units):
    lines = defaultdict(list)
    for unit in units:
        lines[unit['line']].append(unit)
    result = []
    for values in sorted(lines.values(), key=lambda v: min(u['sequence'] for u in v)):
        values.sort(key=lambda v: v['sequence'])
        pieces = []
        current_super = False
        for value in values:
            raised = bool(value['flags'] & 1)
            if raised != current_super:
                pieces.append('<sup>' if raised else '</sup>')
                current_super = raised
            pieces.append(html.escape(value['text']))
        if current_super:
            pieces.append('</sup>')
        result.append(''.join(pieces).strip())
    return '<br/>'.join(x for x in result if x)


def order_objects(objects):
    if len(objects) < 2:
        return objects
    def gaps(axis):
        ranges = sorted((o['bbox'][axis], o['bbox'][axis + 2]) for o in objects)
        end = ranges[0][1]
        out = []
        for left, right in ranges[1:]:
            if left - end > 12:
                out.append((left - end, (left + end) / 2))
            end = max(end, right)
        return out
    # Only split at truly empty strips; a table is an indivisible object here.
    for axis in (0, 1):
        candidates = gaps(axis)
        if not candidates:
            continue
        _, cut = max(candidates)
        before = [o for o in objects if o['bbox'][axis + 2] <= cut]
        after = [o for o in objects if o['bbox'][axis] >= cut]
        if before and after and len(before) + len(after) == len(objects):
            return order_objects(before) + order_objects(after)
    return sorted(objects, key=lambda o: (round(o['bbox'][1] / 3), o['bbox'][0]))


def convert_page(page):
    data = page.get_text('rawdict')
    units = []
    for bi, block in enumerate(data['blocks']):
        for li, line in enumerate(block.get('lines', [])):
            for si, span in enumerate(line['spans']):
                for ci, char in enumerate(span.get('chars', [])):
                    units.append({'id': len(units), 'sequence': len(units), 'block': bi, 'line': (bi, li),
                                  'text': char['c'], 'bbox': char['bbox'], 'size': span['size'], 'flags': span['flags']})
    assigned = set()
    objects = []
    ambiguous_assignments = []
    table_error = None
    try:
        tables = page.find_tables(strategy='lines').tables
    except Exception as exc:
        tables = []
        table_error = type(exc).__name__ + ': ' + str(exc)
    for ti, table in enumerate(tables):
        positions = defaultdict(list)
        for ri, row in enumerate(table.rows):
            for ci, cell in enumerate(row.cells):
                if cell:
                    positions[tuple(round(v, 3) for v in cell)].append((ri, ci))
        original_positions = positions
        ex = sorted({r[0] for r in positions} | {r[2] for r in positions})
        ey = sorted({r[1] for r in positions} | {r[3] for r in positions})
        owners = {}
        for yi in range(len(ey)-1):
            for xi in range(len(ex)-1):
                x, y = (ex[xi]+ex[xi+1])/2, (ey[yi]+ey[yi+1])/2
                candidates = [r for r in positions if r[0] < x < r[2] and r[1] < y < r[3]]
                if candidates:
                    owners[yi,xi] = min(candidates, key=lambda r: ((r[2]-r[0])*(r[3]-r[1]),r))
        tiles = {}
        for yi in range(len(ey)-1):
            xi=0
            while xi < len(ex)-1:
                owner=owners.get((yi,xi))
                if owner is None:
                    xi+=1
                    continue
                end=xi+1
                while end<len(ex)-1 and owners.get((yi,end))==owner:
                    end+=1
                key=(owner,xi,end)
                if key in tiles and tiles[key][-1][1]==yi:
                    tiles[key][-1][1]=yi+1
                else:
                    tiles.setdefault(key,[]).append([yi,yi+1])
                xi=end
        positions=defaultdict(list)
        for (owner,x0,x1), runs in tiles.items():
            for y0,y1 in runs:
                positions[(ex[x0],ey[y0],ex[x1],ey[y1])]=[(y0,x0)]
        values = {rect: [] for rect in positions}
        for unit in units:
            if unit['id'] in assigned:
                continue
            box = unit['bbox']
            candidates = [rect for rect in positions if inside(rect, (box[0] + box[2]) / 2, (box[1] + box[3]) / 2)]
            if len(candidates) > 1:
                scores = [(max(0, min(box[2], r[2])-max(box[0], r[0])) * max(0, min(box[3], r[3])-max(box[1], r[1])), r) for r in candidates]
                scores.sort(reverse=True)
                if abs(scores[0][0] - scores[1][0]) < .01:
                    ambiguous_assignments.append({'glyph_id': unit['id'], 'text': unit['text'], 'bbox': box,
                                                  'candidate_cells': candidates})
                    continue
                candidates = [scores[0][1]]
            if candidates:
                values[candidates[0]].append(unit)
                assigned.add(unit['id'])
        if not any(values.values()):
            continue
        # A detector-only gap with no source character in any row is not a column.
        def edges(axis):
            raw = sorted({r[axis] for r in positions} | {r[axis + 2] for r in positions})
            groups = []
            for point in raw:
                if groups and point - groups[-1][-1] < .8:
                    groups[-1].append(point)
                else:
                    groups.append([point])
            return [statistics.mean(group) for group in groups]
        xs, ys = edges(0), edges(1)
        locate = lambda coordinates, point: min(range(len(coordinates)), key=lambda i: abs(coordinates[i] - point))
        grid = {rect: (locate(ys, rect[1]), locate(ys, rect[3]), locate(xs, rect[0]), locate(xs, rect[2])) for rect in positions}
        # Emptiness alone cannot prove a column is an extraction artifact.
        kept_columns = list(range(len(xs) - 1))
        matrix = [[] for _ in range(len(ys) - 1)]
        emitted = []
        for rect, slots in positions.items():
            r0, r1, c0, c1 = grid[rect]
            cols = [c for c in kept_columns if c0 <= c < c1]
            if not cols:
                continue
            matrix[r0].append((c0, f'<td colspan="{len(cols)}" rowspan="{max(1, r1 - r0)}">' + render_glyphs(values[rect]) + '</td>'))
            emitted.extend(u['id'] for u in values[rect])
        assigned.difference_update(u['id'] for group in values.values() for u in group if u['id'] not in set(emitted))
        markup = '<table>\n' + '\n'.join('<tr>' + ''.join(cell for _, cell in sorted(row)) + '</tr>' for row in matrix) + '\n</table>'
        objects.append({'bbox': table.bbox, 'text': markup, 'kind': 'table', 'source_ids': emitted})
    remaining = defaultdict(list)
    for unit in units:
        if unit['id'] not in assigned:
            remaining[unit['line']].append(unit)
            assigned.add(unit['id'])
    for values in remaining.values():
        box = [min(u['bbox'][0] for u in values), min(u['bbox'][1] for u in values),
               max(u['bbox'][2] for u in values), max(u['bbox'][3] for u in values)]
        objects.append({'bbox': box, 'text': '<p>' + render_glyphs(values) + '</p>', 'kind': 'text', 'source_ids': [u['id'] for u in values]})
    ordered = order_objects(objects)
    identifiers = [i for obj in ordered for i in obj['source_ids']]
    body = '\n\n'.join(o['text'] for o in ordered if o['text'].strip())
    counts = Counter(identifiers)
    expected = set(range(len(units)))
    missing = sorted(expected - set(counts))
    duplicate = sorted(k for k, v in counts.items() if v != 1)
    if missing or duplicate:
        raise ValueError('Native source glyph coverage failed')
    source_chars = Counter(c for u in units for c in u['text'] if not c.isspace())
    rendered = BeautifulSoup(MarkdownIt('commonmark', {'html': True}).render(body), 'html.parser').get_text()
    rendered_chars = Counter(c for c in rendered if not c.isspace())
    if source_chars != rendered_chars:
        raise ValueError('Rendered native characters differ from source: ' + str({'missing': dict(source_chars-rendered_chars), 'extra': dict(rendered_chars-source_chars)}))
    return body, {'native_glyphs': len(units), 'native_nonspace_glyphs': sum(bool(u['text'].strip()) for u in units),
                  'all_native_glyphs_assigned_once': True, 'tables': sum(o['kind'] == 'table' for o in ordered),
                  'rendered_native_character_inventory_matches': True,
                  'ambiguous_cell_assignments': ambiguous_assignments,
                  'table_detection_error': table_error,
                  'objects': [{'kind': o['kind'], 'bbox': list(o['bbox']), 'glyph_count': len(o['source_ids'])} for o in ordered],
                  'unresolved_unicode': sum(any(c == '\ufffd' or unicodedata.category(c) in ('Co', 'Cs') or (unicodedata.category(c) == 'Cc' and not c.isspace()) for c in u['text']) for u in units)}


def source_links(page, names, page_count):
    lines, unresolved = [], []
    for link in page.get_links():
        caption = ' '.join(page.get_textbox(link['from']).split()) or 'Ссылка исходного PDF'
        target = link.get('uri')
        if not target and 0 <= link.get('page', -1) < page_count:
            target = f"#pdf-page-{link['page'] + 1}"
        if not target and link.get('nameddest'):
            name = link['nameddest']
            variants = [name]
            try:
                variants.append(name.encode('latin1').decode('utf8'))
            except (UnicodeError, AttributeError):
                pass
            for variant in variants:
                resolved = names.get(variant, {})
                if 0 <= resolved.get('page', -1) < page_count:
                    target = f"#pdf-page-{resolved['page'] + 1}"
                    break
        if target and target.startswith(('http://', 'https://', 'mailto:', '#')):
            lines.append('<li><a href="' + html.escape(target, quote=True) + '">' + html.escape(caption) + '</a></li>')
        else:
            unresolved.append({'caption': caption, 'named_destination': link.get('nameddest'), 'uri': link.get('uri')})
    return ('\n\n> Служебная информация: ссылки исходного PDF\n\n<ul>' + ''.join(lines) + '</ul>' if lines else ''), unresolved


def raster_text(page, asset):
    """OCR is explicit and pending; never called an exact native-text transfer."""
    command = ['tesseract', str(asset), 'stdout', '-l', 'rus+eng', '--psm', '3', 'tsv']
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return '', {'ocr_error': type(exc).__name__, 'ocr_verified': False}
    if result.returncode:
        return '', {'ocr_error': result.stderr[-500:]}
    flags = fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES
    native = [(c['bbox'][0] + (c['bbox'][2] - c['bbox'][0]) / 2,
               c['bbox'][1] + (c['bbox'][3] - c['bbox'][1]) / 2, c['c'])
              for b in page.get_text('rawdict', flags=flags)['blocks'] for line in b.get('lines', [])
              for span in line['spans'] for c in span.get('chars', []) if c['c'].strip()]
    with Image.open(asset) as image:
        width, height = image.size
    lines = defaultdict(list)
    confidences = []
    suppressed = 0
    conflicts = []
    for row in csv.DictReader(io.StringIO(result.stdout), delimiter='\t'):
        word = row.get('text', '').strip()
        if not word or float(row.get('conf', '-1')) < 40:
            continue
        x0, y0 = float(row['left']) / width * page.rect.width, float(row['top']) / height * page.rect.height
        x1 = (float(row['left']) + float(row['width'])) / width * page.rect.width
        y1 = (float(row['top']) + float(row['height'])) / height * page.rect.height
        rect = fitz.Rect(x0, y0, x1, y1) * page.derotation_matrix
        overlaps = [(x, y, char) for x, y, char in native if inside(rect, x, y)]
        native_word = ''.join(c for x, y, c in sorted(overlaps, key=lambda v: v[0]))
        if overlaps and re.sub(r'\s+', '', native_word).casefold() == re.sub(r'\s+', '', word).casefold():
            suppressed += 1
            continue
        if overlaps:
            conflicts.append({'ocr_text': word, 'native_text': native_word, 'bbox': list(rect)})
        lines[(row['block_num'], row['par_num'], row['line_num'])].append(word)
        confidences.append(float(row['conf']))
    text = '\n'.join(' '.join(words) for words in lines.values())
    return text, {'ocr_engine': 'local Tesseract rus+eng', 'ocr_chars': len(text), 'ocr_verified': False,
                  'native_overlap_words_suppressed': suppressed,
                  'overlapping_native_conflicts': conflicts,
                  'ocr_median_confidence': statistics.median(confidences) if confidences else None}


def convert(source, output, pages=None, image_source=None):
    output = Path(output)
    checks = output / '_проверка'
    checks.mkdir(parents=True, exist_ok=True)
    (output / 'assets').mkdir(exist_ok=True)
    source_sha = hashlib.sha256(Path(source).read_bytes()).hexdigest()
    source_receipt = checks / 'source_input.json'
    source_was_bound = source_receipt.exists()
    if source_receipt.exists() and json.loads(source_receipt.read_text())['source_sha256'] != source_sha:
        raise ValueError('Output folder belongs to a different source PDF')
    write_json(source_receipt, {'source_sha256': source_sha, 'implementation_sha256': IMPLEMENTATION_SHA})
    asset_manifest = checks / 'native_assets.json'
    if asset_manifest.exists() and not source_was_bound:
        shutil.copy2(asset_manifest, checks / ('unbound_assets_' + hashlib.sha256(asset_manifest.read_bytes()).hexdigest() + '.json'))
    try:
        asset_hashes = json.loads(asset_manifest.read_text()) if asset_manifest.exists() and source_was_bound else {}
    except ValueError:
        shutil.copy2(asset_manifest, checks / ('incomplete_assets_' + hashlib.sha256(asset_manifest.read_bytes()).hexdigest() + '.json'))
        asset_hashes = {}
    prepared_hashes = {}
    if image_source and (Path(image_source) / 'pages.json').is_file():
        prepared_index = json.loads((Path(image_source) / 'pages.json').read_text())
        if prepared_index.get('source_sha256') == source_sha:
            prepared_hashes = {p['pdf_page']: p.get('image_sha256') for p in prepared_index['pages']}
    records = []
    parts = []
    with fitz.open(source) as doc:
        names = doc.resolve_names()
        selected = pages or list(range(1, len(doc) + 1))
        for n in selected:
            page = doc[n - 1]
            try:
                body, info = convert_page(page)
            except Exception as exc:
                raw = page.get_text()
                body = '> Служебная пометка: точность переноса этой страницы не подтверждена; см. исходное изображение ниже.\n\n<pre>' + html.escape(raw) + '</pre>'
                info = {'native_glyphs': len(raw), 'native_nonspace_glyphs': sum(not c.isspace() for c in raw),
                        'all_native_glyphs_assigned_once': False, 'rendered_native_character_inventory_matches': False,
                        'tables': 0, 'objects': [], 'unresolved_unicode': 0,
                        'native_extraction_error': type(exc).__name__ + ': ' + str(exc)}
            asset = output / 'assets' / f'page_{n:04d}.png'
            prepared = Path(image_source) / f'page_{n:04d}.png' if image_source else None
            if asset.exists() and asset_hashes.get(asset.name) != hashlib.sha256(asset.read_bytes()).hexdigest():
                history = checks / 'untrusted_assets'
                history.mkdir(exist_ok=True)
                asset.rename(history / (hashlib.sha256(asset.read_bytes()).hexdigest() + '_' + asset.name))
            if not asset.exists():
                if prepared and prepared.is_file() and prepared_hashes.get(n) == hashlib.sha256(prepared.read_bytes()).hexdigest():
                    shutil.copy2(prepared, asset)
                else:
                    scale = min(2, 2600 / max(page.rect.width, page.rect.height))
                    page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(asset)
            asset_hashes[asset.name] = hashlib.sha256(asset.read_bytes()).hexdigest()
            write_json(asset_manifest, asset_hashes)
            issues = []
            if info.get('native_extraction_error'):
                issues.append(info['native_extraction_error'])
            if info.get('unresolved_unicode'):
                issues.append('Source font mapping has unresolved characters; inspect the source image.')
            if info.get('table_detection_error'):
                issues.append('Table detector failed; review source table geometry.')
            if info.get('ambiguous_cell_assignments'):
                issues.append('Some source glyphs have ambiguous table-cell ownership; inspect the source geometry.')
            large_raster = False
            for image in page.get_image_info():
                rect = fitz.Rect(image['bbox'])
                native_in_box = sum(1 for b in info['objects'] if b['kind'] == 'text' and fitz.Rect(b['bbox']).intersects(rect))
                if rect.get_area() > page.rect.get_area() * .35 and native_in_box < 20:
                    large_raster = True
            if info['native_nonspace_glyphs'] < 100 or large_raster:
                ocr, ocr_info = raster_text(page, asset)
                info.update(ocr_info)
                if ocr:
                    body += '\n\n> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена.\n\n' + html.escape(ocr).replace('\n', '<br/>')
                issues.append('Image-dominant or nearly empty page: OCR/visual transcription requires review.')
            links, unresolved = source_links(page, names, len(doc))
            body += links
            if unresolved:
                info['unresolved_source_links'] = unresolved
                issues.append('Some source link destinations are unresolved; do not invent URLs.')
            record = {'pdf_page': n, 'conversion_status': 'converted', 'review_status': 'pending' if issues else 'converted',
                      'semantic_source_review_completed': False, 'verification_scope': 'Native glyph and rendered-character accounting',
                      'issues': issues, **info}
            records.append(record)
            write_json(checks / 'pages.json', {'pages': records})
            parts.append(f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n{body}\n\n<details>\n<summary>Источник: PDF-страница {n}</summary>\n\n![Полная исходная страница {n}](assets/page_{n:04d}.png)\n\n</details>')
            print(n, info['native_glyphs'], info['tables'], flush=True)
    if (output / 'report.md').exists():
        versions = checks / 'previous_reports'
        versions.mkdir(exist_ok=True)
        shutil.copy2(output / 'report.md', versions / (hashlib.sha256((output / 'report.md').read_bytes()).hexdigest() + '.md'))
    temp_report = output / 'report.md.part'
    temp_report.write_text('> Служебная информация: механический исходный кандидат по текстовому слою и геометрии PDF. Не является завершённой визуальной сверкой.\n\n' + '\n\n'.join(parts) + '\n')
    temp_report.replace(output / 'report.md')
    write_json(checks / 'native_coverage.json', {'source_sha256': source_sha,
          'implementation_sha256': IMPLEMENTATION_SHA,
          'report_sha256': hashlib.sha256((output / 'report.md').read_bytes()).hexdigest(),
          'pages': len(records), 'all_native_glyphs_assigned_once': all(r['all_native_glyphs_assigned_once'] for r in records),
          'review_status': 'converted', 'semantic_source_review_completed': False,
          'pending_pages': [r['pdf_page'] for r in records if r['issues']],
          'scope': 'Native text glyph coverage, not full visual or semantic fidelity'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--pages', type=int, nargs='*')
    parser.add_argument('--image-source', type=Path)
    args = parser.parse_args()
    convert(args.source, args.output, args.pages, args.image_source)
