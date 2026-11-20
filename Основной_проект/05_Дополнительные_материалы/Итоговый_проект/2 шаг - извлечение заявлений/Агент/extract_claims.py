"""Page-grounded ESG extraction contract; semantic extraction is done by the LLM."""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

TYPES = ('обязательство', 'результат', 'декларация')
HEADERS = ['№', 'Обязательства', 'Результаты', 'Декларации']


def norm(text):
    return re.sub(r'\s+', ' ', text).strip()


def display_quote(quote, page_text):
    """Remove presentation markup; retain raw quote in the evidence JSON."""
    text = quote
    if text.strip().startswith('|') and text.strip().endswith('|'):
        cells = [x.strip() for x in text.strip().strip('|').split('|')]
        before = page_text[:page_text.find(text)]
        lines = before.splitlines()
        headers = None
        for i in range(len(lines)-1):
            if re.match(r'^\s*\|[\s:|\-]+\|\s*$', lines[i+1]) and lines[i].strip().startswith('|'):
                headers = [x.strip() for x in lines[i].strip().strip('|').split('|')]
        if headers and len(headers) == len(cells):
            text = '; '.join(f'{h}: {v}' for h,v in zip(headers,cells) if h != '№')
        else:
            text = '; '.join(cells)
    supers = str.maketrans('0123456789','⁰¹²³⁴⁵⁶⁷⁸⁹')
    subs = str.maketrans('0123456789','₀₁₂₃₄₅₆₇₈₉')
    text = re.sub(r'<sup>(.*?)</sup>', lambda m:m[1].translate(supers), text)
    text = re.sub(r'<sub>(.*?)</sub>', lambda m:m[1].translate(subs), text)
    text = text.replace('**','').replace('\u00ad','')
    return norm(text)


def source(path):
    raw = Path(path).read_bytes()
    text = raw.decode('utf-8-sig')
    found = re.findall(r'<!-- pdf_page: (\d+) -->.*?<!-- source_text_begin -->(.*?)<!-- source_text_end -->', text, re.S)
    if not found:
        raise ValueError('Нет размеченных страниц: нужны pdf_page и source_text_begin/end')
    ids = [int(n) for n, _ in found]
    if ids != list(range(1, len(ids) + 1)):
        raise ValueError('Страницы повторяются, пропущены или нарушен порядок')
    return hashlib.sha256(raw).hexdigest(), {int(n): t.strip() for n, t in found}


def validate(report, data):
    sha, pages = source(report)
    if not isinstance(data, dict):
        raise ValueError('Ожидается JSON-объект')
    if data.get('source_sha256') != sha:
        raise ValueError('Хеш MD не совпадает; проверь версию исходника')
    reviewed = data.get('pages_reviewed', [])
    if not isinstance(reviewed, list) or any(type(n) is not int for n in reviewed) or sorted(reviewed) != list(pages):
        raise ValueError('Не подтверждён просмотр всех страниц или есть повторы')
    claims = data.get('claims')
    if not isinstance(claims, list) or not claims:
        raise ValueError('Нет извлечённых заявлений')
    seen = set()
    for i, c in enumerate(claims, 1):
        if not isinstance(c, dict):
            raise ValueError(f'Запись {i}: ожидается объект')
        page, kind, quote = c.get('page'), c.get('type'), c.get('quote')
        if isinstance(page, bool) or page not in pages or kind not in TYPES:
            raise ValueError(f'Запись {i}: неверная страница/тип')
        segments = c.get('segments')
        if segments:
            if not isinstance(segments, list) or any(not isinstance(seg,dict) or seg.get('page') not in pages or not isinstance(seg.get('quote'),str) or not norm(seg['quote']) or norm(seg['quote']) not in norm(pages[seg['page']]) for seg in segments):
                raise ValueError(f'Запись {i}: неверные фрагменты на границе страниц')
            if segments[0]['page'] != page or [s['page'] for s in segments] != list(range(page,page+len(segments))):
                raise ValueError(f'Запись {i}: нарушен порядок страниц фрагментов')
            quote_matches = isinstance(quote,str) and norm(quote) == norm(' '.join(seg['quote'] for seg in segments))
        else:
            quote_matches = isinstance(quote,str) and bool(norm(quote)) and norm(quote) in norm(pages[page])
        if not quote_matches:
            raise ValueError(f'Запись {i}: цитата отсутствует на странице {page}')
        if len(norm(quote)) > 32767:
            raise ValueError(f'Запись {i}: превышен предел ячейки Excel; раздели заявление')
        if not isinstance(c.get('reason'), str) or not c['reason'].strip():
            raise ValueError(f'Запись {i}: нет основания типа')
        if c.get('needs_source_review'):
            raise ValueError(f'Запись {i}: не разрешено сомнение по источнику')
        if c.get('display_context'):
            cp = c.get('context_page',page)
            if cp not in pages or norm(c['display_context']) not in norm(pages[cp]):
                raise ValueError(f'Запись {i}: отображаемый контекст отсутствует в источнике')
        key = (norm(quote), norm(c.get('context', '')))
        if key in seen:
            raise ValueError(f'Запись {i}: точный повтор заявления')
        seen.add(key)
    ordered = sorted(claims, key=lambda c: (c['page'], norm(pages[c['page']]).index(norm(c.get('segments',[{'quote':c['quote']}])[0]['quote']))))
    return sha, pages, ordered


def merge_parts(report, paths):
    """Combine completed page batches; fail closed on gaps or overlapping reviews."""
    sha, pages = source(report)
    merged = {'source_sha256': sha, 'pages_reviewed': [], 'claims': [], 'excluded_notes': []}
    owners = set()
    for path in paths:
        part = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        if not isinstance(part, dict) or part.get('source_sha256') != sha:
            raise ValueError(f'{path}: неверный объект или хеш исходника')
        reviewed = part.get('pages_reviewed')
        if not isinstance(reviewed, list) or not reviewed or any(type(n) is not int or n not in pages for n in reviewed):
            raise ValueError(f'{path}: неверные страницы пакета')
        if len(set(reviewed)) != len(reviewed) or owners.intersection(reviewed):
            raise ValueError(f'{path}: страницы обработаны повторно')
        claims = part.get('claims')
        if not isinstance(claims, list):
            raise ValueError(f'{path}: claims должен быть списком')
        for claim in claims:
            if not isinstance(claim, dict) or type(claim.get('page')) is not int or claim['page'] not in reviewed:
                raise ValueError(f'{path}: заявление вне просмотренных страниц пакета')
        notes = part.get('excluded_notes', [])
        if not isinstance(notes, list):
            raise ValueError(f'{path}: excluded_notes должен быть списком')
        owners.update(reviewed)
        merged['pages_reviewed'].extend(reviewed)
        merged['claims'].extend(claims)
        merged['excluded_notes'].extend(notes)
    missing = sorted(set(pages) - owners)
    if missing:
        raise ValueError(f'Не обработаны страницы: {missing}')
    merged['pages_reviewed'].sort()
    # Final validation checks quotes, boundary segments, types and duplicates globally.
    _, _, merged['claims'] = validate(report, merged)
    return merged


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'merge', 'validate', 'export'])
    parser.add_argument('--report', required=True)
    parser.add_argument('--claims')
    parser.add_argument('--parts', nargs='+', help='JSON результатов пакетов для merge')
    parser.add_argument('--output')
    parser.add_argument('--name', default='Заявления')
    args = parser.parse_args()
    try:
        sha, pages = source(args.report)
        if args.command == 'prepare':
            out = Path(args.output)
            out.mkdir(parents=True, exist_ok=True)
            packets = out / 'Пакеты'
            packets.mkdir(exist_ok=True)
            for start in range(1, len(pages) + 1, 8):
                stop = min(start + 7, len(pages))
                write_json(packets / f'{start:03d}-{stop:03d}.json', [{'page': n, 'text': pages[n]} for n in range(start, stop + 1)])
            template = out / 'claims.template.json'
            write_json(template, {'source_sha256': sha, 'pages_reviewed': [], 'claims': [], 'excluded_notes': []})
            print(json.dumps({'pages': len(pages), 'packets': (len(pages)+7)//8, 'template': str(template)}, ensure_ascii=False))
            return 0
        if args.command == 'merge':
            if not args.parts or not args.output:
                raise ValueError('Для merge нужны --parts и --output (новый JSON-файл)')
            merged = merge_parts(args.report, args.parts)
            target = Path(args.output)
            # Exclusive creation preserves an existing result on accidental reruns.
            with target.open('x', encoding='utf-8') as f:
                f.write(json.dumps(merged, ensure_ascii=False, indent=2) + '\n')
            print(json.dumps({'output': str(target), 'pages': len(pages), 'claims': len(merged['claims'])}, ensure_ascii=False))
            return 0
        data = json.loads(Path(args.claims).read_text())
        sha, pages, claims = validate(args.report, data)
        stats = {'source_sha256': sha, 'pages_reviewed': len(pages), 'claims': len(claims), 'types': dict(Counter(c['type'] for c in claims)), 'quote_check': 'all matched in MD', 'semantic_accuracy': 'not measured by this validator'}
        if args.command == 'export':
            out = Path(args.output)
            out.mkdir(parents=True, exist_ok=True)
            rows = []
            for i, c in enumerate(claims, 1):
                row = [i, '', '', '']
                text = display_quote(c['quote'], pages[c['page']])
                if c.get('display_context'):
                    text = display_quote(c['display_context'],pages[c.get('context_page',c['page'])]) + '\n' + text
                row[TYPES.index(c['type'])+1] = text
                rows.append(row)
            if Path(args.name).name != args.name or not args.name.strip():
                raise ValueError('Имя результата должно быть простым именем без пути')
            target = out / (args.name + '.csv')
            with target.open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(HEADERS)
                writer.writerows(rows)
            with target.open(encoding='utf-8-sig', newline='') as f:
                saved = list(csv.reader(f, delimiter=';'))
            if saved != [HEADERS] + [[str(x) for x in row] for row in rows]:
                raise ValueError('CSV readback mismatch')
            write_json(out / 'table.json', {'headers': HEADERS, 'rows': rows, 'output_name': args.name})
            write_json(out / 'validation.json', stats)
        print(json.dumps(stats, ensure_ascii=False))
        return 0
    except (ValueError, TypeError, OSError, KeyError) as e:
        print(f'ОШИБКА: {e}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
