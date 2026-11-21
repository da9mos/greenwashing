"""Локальный PDF → Markdown. Существующие таблицы, OCR и ссылки сохраняются при повторном прогоне."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import html
from io import StringIO
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote

from markdown_it import MarkdownIt
import pymupdf

from table_layout import review_tables

PAGE = re.compile(r'^<!--\s*pdf_page:\s*(\d+)\s*-->[ \t]*$', re.M)
VERSION = 'проверка вёрстки'
ANCHOR = re.compile(r'''<a\s+id=["'](pdf-page-\d+)["']\s*></a>''')
PARAGRAPHS = re.compile(r'(?m)^(?:<p>[^\n]*?</p>[ \t]*\n(?:[ \t]*\n)*){2,}')
PARAGRAPH = re.compile(r'<p>(.*?)</p>')
CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
ANCHOR_TAG = re.compile(r'<a\b[^>]*>', re.I)
ATTR = re.compile('\\b(id|href)=["\']([^"\']+)["\']', re.I)
FENCE = re.compile(r'(?m)^ {0,3}(?:`{3,}|~{3,})')
MATH = re.compile(r'(?<![\w.,])[-−+]?\d+(?:[,.]\d+)*(?![\w.,])')
WORD = re.compile(r'[^\W\d_]{3,}', re.UNICODE)
NEW_ITEM = re.compile(r'^(?:[•●▪◦·]|[-–—]\s|\(?\d+[.)]\s|\d+\s+(?=[А-ЯЁA-Z]))')
HYPHENS = ('-', '‐', '‑', '–', '\u00ad')
ENGINE = MarkdownIt('gfm-like', options_update={'linkify': False})
TEXT_FLAGS = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def normalized(value):
    value = unicodedata.normalize('NFC', html.unescape(value)).replace('\u00ad', '')
    return ' '.join(value.split())


def native_blocks(page):
    blocks = []
    for block in page.get_text('dict', flags=TEXT_FLAGS)['blocks']:
        lines = []
        for line in block.get('lines', []):
            spans = [span for span in line['spans'] if span['text'].strip()]
            if not spans:
                continue
            text = ''.join(span['text'] for span in line['spans']).strip()
            x, _, _, _ = line['bbox']
            lines.append((text, x, spans[0]['origin'][1], max(s['size'] for s in spans), line['dir']))
        if lines:
            blocks.append(lines)
    return blocks


def following_line(previous, current):
    first, first_x, first_y, first_size, first_dir = previous
    second, second_x, second_y, second_size, second_dir = current
    return (
        first_dir[0] > .99 and second_dir[0] > .99
        and abs(first_size - second_size) <= .6
        and abs(first_x - second_x) <= max(5, first_size * .6)
        and first_size * .85 <= second_y - first_y <= first_size * 1.55
        and len(first) >= 18 and len(second) >= 4
        and not first.endswith(HYPHENS + (':',))
        and second[0].islower() and not NEW_ITEM.match(second)
        and not re.match(r'^\s*(?:[A-ZА-ЯЁ]{2,}|\d)', first)  # Заголовки, номерные примечания и короткие значения.
    )


def continuation_pairs(blocks):
    occurrences = Counter(normalized(line[0]) for block in blocks for line in block)
    pairs = set()
    for block in blocks:
        for first, second in zip(block, block[1:]):
            a, b = normalized(first[0]), normalized(second[0])
            if (following_line(first, second) and occurrences[a] == occurrences[b] == 1
                    and not a.endswith(('.', '!', '?', ';', ':'))):
                pairs.add((a, b))
    return pairs

def reflow(text, blocks):
    if '<p>' not in text:
        return text, 0
    pairs = Counter()
    occurrences = Counter()
    for block in blocks:
        occurrences.update(normalized(line[0]) for line in block)
        for previous, current in zip(block, block[1:]):
            if following_line(previous, current):
                pairs[normalized(previous[0]), normalized(current[0])] += 1
    changed = 0

    def merge(match):
        nonlocal changed
        matches = list(PARAGRAPH.finditer(match[0]))
        previous = None
        output = []
        for fragment in matches:
            raw = fragment[1]
            current = normalized(raw) if '<' not in raw and '>' not in raw else None
            if (previous and current and pairs[previous, current] == 1
                    and occurrences[previous] == occurrences[current] == 1):
                output[-1] += ' ' + raw.strip()
                changed += 1
            else:
                output.append(raw)
            previous = current
        suffix = match[0][matches[-1].end():]
        return '\n\n'.join(f'<p>{value}</p>' for value in output) + suffix

    # Не меняем ячейки таблиц, fenced-блоки, сложные inline-элементы и служебные секции.
    if FENCE.search(text):
        return text, 0
    parts = re.split(r'(?is)(<table\b[^>]*>.*?</table>|<details\b[^>]*>.*?</details>|<pre\b[^>]*>.*?</pre>)', text)
    for index in range(0, len(parts), 2):
        parts[index] = PARAGRAPHS.sub(merge, parts[index])
    return ''.join(parts), changed


def page_parts(text, count):
    markers = list(PAGE.finditer(text))
    expected = list(range(1, count + 1))
    if [int(marker[1]) for marker in markers] != expected:
        raise ValueError('маркеры физических страниц не совпадают с реестром')
    pages = []
    for i, marker in enumerate(markers):
        section = text[marker.end():markers[i + 1].start() if i + 1 < count else len(text)]
        anchors = ANCHOR.findall(section)
        if anchors != [f'pdf-page-{i + 1}']:
            raise ValueError(f'страница {i + 1}: неверный или повторный якорь')
        pages.append(ANCHOR.sub('', section, count=1).strip('\n'))
    return text[:markers[0].start()].rstrip(), pages


def fix_markup(text):
    if FENCE.search(text):
        return text
    # Повторяющиеся плюсы в табличной строке нельзя интерпретировать как вложенные списки.
    text = re.sub(r'(?m)^[ \t]*\+(?:[ \t]+\+){2,}[ \t]*$',
                  lambda match: match[0].replace('+', r'\+'), text)
    text = re.sub(r'(?m)^&gt; (?=Служебная (?:информация|пометка):)', '> ', text)
    text = re.sub(r'(?m)^>[ \t]*\n(?=<!-- corpus_note_end:)', '', text)
    # Убираем лишние пустые строки только вне HTML-блоков и примеров с отступами.
    parts = re.split(r'(?is)(<pre\b[^>]*>.*?</pre>|<table\b[^>]*>.*?</table>)', text)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r'\n(?:[ \t]*\n){2,}(?![ \t])', '\n\n', parts[i])
    return ''.join(parts)


def apply_fixes(content, fixes, pdf_sha, number):
    count = 0
    for fix in fixes:
        if fix['page'] != number or fix['pdf_sha256'] != pdf_sha:
            continue
        before, after = fix['before'], fix['after']
        if content.count(before) == 1:
            content = content.replace(before, after, 1)
            count += 1
        elif content.count(after) != 1:
            raise ValueError(f'страница {number}: не найден единственный фрагмент правки «{fix["finding"]}»')
    return content, count


def rendered_text(markup):
    text = re.sub(r'(?is)<(?:script|style)\b[^>]*>.*?</(?:script|style)>', '', markup)
    return normalized(re.sub(r'<[^>]*>', ' ', text))


def assess(source, markup):
    damaged_source = CONTROL.search(source) is not None or '\ufffd' in source
    source = normalized(source)
    output = rendered_text(markup)
    expected_words = Counter(word.casefold() for word in WORD.findall(source))
    actual_words = Counter(word.casefold() for word in WORD.findall(output))
    # Повторы колонтитулов и переносы дают ложные срабатывания. Это очередь сверки, а не мера полноты.
    words = expected_words.total()
    overlap = (expected_words & actual_words).total() / words if words else 0
    absent_numbers = len(set(MATH.findall(source)) - set(MATH.findall(output)))
    flags = []
    if len(source) < 100:
        flags.append('слабый текстовый слой, проверить растр и OCR')
    if damaged_source or '\ufffd' in output:
        flags.append('проверить повреждённые символы по растру')
    if words >= 30 and overlap < .75:
        flags.append('различие текстового слоя и Markdown')
    if absent_numbers >= 3:
        flags.append('часть исходных чисел не найдена в таком же написании')
    return flags, absent_numbers


def display_page(number, content):
    content = content.strip('\n')
    return f'<!-- pdf_page: {number} -->\n<a id="pdf-page-{number}"></a>\n\n{content}\n'


def check_display(number, content):
    document = display_page(number, content)
    result = ENGINE.render(document)
    if not result.lstrip().startswith(f'<!-- pdf_page: {number} -->') or f'id="pdf-page-{number}"' not in result:
        raise ValueError(f'страница {number}: якорь или маркер теряется при отображении')
    if [item[1] for item in ANCHOR.finditer(result)] != [f'pdf-page-{number}']:
        raise ValueError(f'страница {number}: якорь продублирован при отображении')
    return result


def verify_document(text, count):
    rendered = ENGINE.render(text)
    page_parts(rendered, count)
    ids = Counter()
    links = set()
    for tag in ANCHOR_TAG.findall(rendered):
        for attribute, value in ATTR.findall(tag):
            if attribute.lower() == 'id':
                ids[value] += 1
            if attribute.lower() == 'href' and value.startswith('#'):
                links.add(unquote(value[1:]))
    if duplicate := [name for name, total in ids.items() if total > 1]:
        raise ValueError(f'дублирующиеся якоря: {duplicate[:6]}')
    return sorted(links - ids.keys())


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name('.' + path.name + '.part')
    staging.write_bytes(data)
    staging.replace(path)


def save_figure(fix, page, original, dest, report_id, markup):
    figure = fix['figure']
    filename = figure['filename']
    if not re.fullmatch(re.escape(report_id) + r'-p\d+-[a-z][a-z0-9-]*\.png', filename):
        raise ValueError('недопустимое имя графики из PDF')
    relative_path = Path('assets') / filename
    if f'src="{relative_path.as_posix()}"' not in unquote(markup):
        return None
    if page is None:
        data = (original.parent / relative_path).read_bytes()
    else:
        rect = pymupdf.Rect(figure['rect'])
        if rect.is_empty or not page.rect.contains(rect):
            raise ValueError('границы изображения выходят за пределы страницы PDF')
        image = page.get_pixmap(matrix=pymupdf.Matrix(1.15, 1.15), clip=rect, alpha=False)
        data = image.tobytes('png')
    atomic_write(dest.parent / relative_path, data)
    return relative_path


def report(task):
    row, root, pdf_dir, out, fixes = task
    rid = row['report_id']
    count = int(row['physical_pages'])
    original = root / row['repository_path']
    dest = out / row['repository_path']
    if original.resolve() == dest.resolve():
        raise ValueError('выход совпадает с действующим корпусом')
    pdf = pdf_dir / f'{rid}.pdf'
    if not original.is_file():
        raise ValueError('исходный Markdown отсутствует')
    original_digest = sha(original)
    if original_digest != row['packaged_md_sha256']:
        raise ValueError('хэш действующего Markdown отличается от реестра')
    header, previous = page_parts(original.read_text(encoding='utf-8'), count)
    found = pdf.is_file()
    pdf_digest = sha(pdf) if found else None
    result = []
    review = []
    matching_fixes = [fix for fix in fixes if fix['pdf_sha256'] == pdf_digest]
    skipped_fixes = [fix['finding'] for fix in fixes if fix['pdf_sha256'] != pdf_digest]
    figures = {fix['page']: fix for fix in fixes if 'figure' in fix}
    assets = {}
    table_pages = {}
    joined = corrected = formatted = tables_repaired = 0
    doc = pymupdf.open(pdf) if found else None
    try:
        if doc is not None and (not doc.is_pdf or doc.needs_pass or doc.is_repaired or len(doc) != count):
            raise ValueError('исходный PDF не открывается либо число страниц отличается от реестра')
        for number, content in enumerate(previous, 1):
            page, edits = apply_fixes(content, matching_fixes, pdf_digest, number)
            page = fix_markup(page)
            corrected += edits
            if doc is not None:
                source = doc[number - 1]
                blocks = native_blocks(source)
                page, merges = reflow(page, blocks)
                joined += merges
                table_issues = []
                if '<table>' in page and not FENCE.search(page):
                    page, table_count, table_issues = review_tables(page, source, continuation_pairs(blocks))
                    tables_repaired += table_count
                    if table_count:
                        table_pages[number] = table_count
                markup = check_display(number, page)
                text = '\n'.join(line[0] for block in blocks for line in block)
                flags, absent = assess(text, markup)
                flags.extend(f'сверить таблицу: {issue}' for issue in table_issues)
                if flags:
                    review.append({'page': number, 'flags': flags, 'different_number_spellings': absent})
            else:
                markup = check_display(number, page)
            if number in figures:
                fix = figures[number]
                verified_source = doc is not None and fix['pdf_sha256'] == pdf_digest
                asset = save_figure(fix, doc[number - 1] if verified_source else None, original, dest, rid, markup)
                if verified_source and asset is None:
                    raise ValueError(f'страница {number}: ссылка на графику отсутствует после рендеринга')
                if asset is not None:
                    repository_path = (Path(row['repository_path']).parent / asset).as_posix()
                    assets[repository_path] = sha(dest.parent / asset)
            formatted += content != page
            result.append(display_page(number, page))
    finally:
        if doc is not None:
            doc.close()
    note = ('Исходный PDF открыт, текстовый слой каждой страницы сопоставлен с Markdown. '
            'Повторно проверены структура и вёрстка. Полная визуальная и смысловая сверка не завершена.'
            if found else 'Проверены структура и отображение Markdown. Исходный PDF для повторной сверки недоступен.')
    header = re.sub(r'(?m)^- Проверка: .*$', '- Проверка: ' + note, header, count=1)
    if '- Проверка: ' + note not in header:
        raise ValueError('не найдена служебная строка проверки')
    version = row['version']
    if not version.endswith(VERSION):
        version = f'{version}; {VERSION}'
    header, substitutions = re.subn(
        r'(?m)^- Версия Markdown: .*$', lambda _: f'- Версия Markdown: {version}.', header, count=1,
    )
    if substitutions != 1:
        raise ValueError('не найдена служебная строка версии')
    text = header + '\n\n' + '\n'.join(result)
    invalid_links = verify_document(text, count)
    data = text.encode('utf-8')
    atomic_write(dest, data)
    return {
        'report_id': rid, 'physical_pages': count, 'pdf_checked': found, 'pdf_sha256': pdf_digest,
        'previous_md_sha256': original_digest, 'packaged_md_sha256': hashlib.sha256(data).hexdigest(),
        'formatted_pages': formatted, 'merged_lines': joined, 'verified_fixes': corrected,
        'repaired_tables': tables_repaired,
        'table_repair_pages': table_pages,
        'assets': assets,
        'version': version, 'verification_status': note, 'review_queue': review,
        'skipped_fixes': skipped_fixes, 'unresolved_internal_links': invalid_links,
    }


def new_report(pdf, dest):
    if dest.exists():
        raise FileExistsError(f'выход уже существует: {dest}')
    sections = []
    pending = []
    with pymupdf.open(pdf) as doc:
        if not doc.is_pdf or doc.needs_pass or doc.is_repaired or not len(doc):
            raise ValueError('требуется читаемый PDF')
        for number, page in enumerate(doc, 1):
            blocks = native_blocks(page)
            paragraphs = []
            for block in blocks:
                lines = [html.escape(line[0], quote=False) for line in block]
                paragraphs.append('<p>' + '<br/>'.join(lines) + '</p>')
            source = '\n'.join(line[0] for block in blocks for line in block)
            content = '\n\n'.join(paragraphs)
            if len(source.strip()) < 100 or CONTROL.search(source) or '\ufffd' in source:
                pending.append(number)
                warning = '> Служебная пометка: проверьте текст и изображения по оригиналу, может потребоваться OCR.'
                content = f'{content}\n\n{warning}' if content else warning
            check_display(number, content)
            sections.append(display_page(number, content))
    title = html.escape(pdf.stem, quote=False)
    status = '> Черновик из текстового слоя PDF. Таблицы, графики и порядок чтения требуют сверки по оригиналу.'
    text = f'# {title}\n\n{status}\n\n' + '\n'.join(sections)
    verify_document(text, len(sections))
    atomic_write(dest, text.encode('utf-8'))
    return {'file': str(dest), 'physical_pages': len(sections), 'weak_text_layer_pages': pending}


def write_json(path, value):
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def write_registry(out, rows, fields, results):
    target = StringIO(newline='')
    writer = csv.DictWriter(target, fieldnames=fields, delimiter=';')
    writer.writeheader()
    for row, result in zip(rows, results, strict=True):
        writer.writerow({
            **row,
            'version': result['version'],
            'packaged_md_sha256': result['packaged_md_sha256'],
            'verification_status': result['verification_status'],
        })
    atomic_write(out / '00_Отчёты/Реестр_отчётов.csv', target.getvalue().encode('utf-8-sig'))


def write_metadata(source, out, results):
    index = source / '00_Отчёты'
    dest = out / '00_Отчёты'
    manifest_file = index / 'manifest.json'
    validation_file = index / 'validation.json'
    by_id = {row['report_id']: row for row in results}
    if manifest_file.is_file():
        manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
        if set(by_id) != {row['report_id'] for row in manifest}:
            raise ValueError('реестр и manifest.json описывают разные наборы отчётов')
        for item in manifest:
            update = by_id[item['report_id']]
            item.update({key: update[key] for key in ('version', 'packaged_md_sha256', 'verification_status')})
            item['repeat_run_pdf_opened'] = update['pdf_checked']
            item['repeat_run_pdf_sha256'] = update['pdf_sha256']
            item['repeat_run_unresolved_internal_links'] = update['unresolved_internal_links']
        write_json(dest / 'manifest.json', manifest)
    if validation_file.is_file():
        validation = json.loads(validation_file.read_text(encoding='utf-8'))
        validation['repeat_run'] = {
            'report_count': len(results),
            'physical_pages': sum(row['physical_pages'] for row in results),
            'pdfs_opened': sum(row['pdf_checked'] for row in results),
            'all_page_markers_and_anchors_visible': True,
            'unresolved_internal_links': {row['report_id']: row['unresolved_internal_links']
                                          for row in results if row['unresolved_internal_links']},
        }
        validation['full_content_verified'] = False
        write_json(dest / 'validation.json', validation)


def corpus(args):
    registry = args.corpus / '00_Отчёты/Реестр_отчётов.csv'
    with registry.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, delimiter=';')
        rows = list(reader)
        fields = reader.fieldnames
    if args.out.resolve() == args.corpus.resolve():
        raise ValueError('укажите отдельную выходную папку для повторного прогона')
    if args.only:
        if unknown := set(args.only) - {row['report_id'] for row in rows}:
            raise ValueError(f'в реестре нет отчётов: {sorted(unknown)}')
        rows = [row for row in rows if row['report_id'] in args.only]
    if args.require_pdfs:
        missing = [row['report_id'] for row in rows if not (args.pdf_dir / f"{row['report_id']}.pdf").is_file()]
        if missing:
            raise ValueError('отсутствуют исходные PDF: ' + ', '.join(missing))
    fixes_path = Path(__file__).with_name('source_fixes.json')
    fixes = json.loads(fixes_path.read_text(encoding='utf-8'))
    tasks = [(row, args.corpus, args.pdf_dir, args.out, fixes.get(row['report_id'], [])) for row in rows]
    results = []
    errors = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(report, task) for task in tasks]
        for row, future in zip(rows, futures):
            rid = row['report_id']
            try:
                result = future.result()
            except (OSError, ValueError, RuntimeError) as exc:
                errors.append({'report_id': rid, 'error': str(exc)})
                print(f'{rid}: ошибка: {exc}', flush=True)
                continue
            results.append(result)
            checked = 'с PDF' if result['pdf_checked'] else 'только MD'
            print(f'{rid}: {result["physical_pages"]} стр., {checked}, '
                  f'{result["merged_lines"]} склеенных строк, {result["verified_fixes"]} адресных правок, '
                  f'{result["repaired_tables"]} исправленных таблиц', flush=True)
    summary = {
        'report_count': len(results),
        'physical_pages': sum(row['physical_pages'] for row in results),
        'source_pdf_count': sum(row['pdf_checked'] for row in results),
        'whole_corpus': not args.only and not errors,
        'reports': results,
        'errors': errors,
    }
    write_json(args.out / 'conversion_run.json', summary)
    if not errors:
        if not args.only:
            write_metadata(args.corpus, args.out, results)
        write_registry(args.out, rows, fields, results)
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    one = sub.add_parser('pdf', help='черновик из нового PDF')
    one.add_argument('input', type=Path)
    one.add_argument('output', type=Path)
    all_reports = sub.add_parser('corpus', help='повторный прогон реестра в отдельную папку')
    all_reports.add_argument('--corpus', type=Path, required=True, help='папка «Основной_проект»')
    all_reports.add_argument('--pdf-dir', type=Path, required=True, help='папка PDF с именами <report_id>.pdf')
    all_reports.add_argument('--out', type=Path, required=True)
    all_reports.add_argument('--only', nargs='+')
    all_reports.add_argument('--require-pdfs', action='store_true', help='отказаться от прогона при отсутствии исходных PDF')
    all_reports.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if args.mode == 'pdf':
        print(json.dumps(new_report(args.input, args.output), ensure_ascii=False))
        return 0
    return corpus(args)


if __name__ == '__main__':
    raise SystemExit(main())
