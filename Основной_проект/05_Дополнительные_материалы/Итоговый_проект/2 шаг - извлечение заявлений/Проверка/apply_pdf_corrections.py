"""Apply reviewed, page-scoped PDF corrections to a separate working source."""
import hashlib
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent
ORIGINAL = ROOT / '1 шаг - перевод PDF в MD/Результаты работы/Газпром 2023 - экологический отчёт/report.md'
SAMPLE = BASE / 'Пример_Газпром_2023'
CHECK = BASE / 'Проверка'
norm = lambda s: re.sub(r'\s+', ' ', s).strip()


def replace(text, before, after):
    pattern = r'\s+'.join(re.escape(x) for x in before.split())
    return re.subn(pattern, lambda _: after, text)


def main():
    original_sha = hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()
    before_file = CHECK / 'claims.before_pdf_corrections.json'
    if not before_file.exists():
        before_file.write_bytes((SAMPLE / 'claims.json').read_bytes())
    data = json.loads(before_file.read_text())
    if data['source_sha256'] != original_sha:
        raise ValueError('Original report changed; do not apply stale corrections')
    reviews = [entry for i in [1,2,3] for entry in json.loads((CHECK / f'pdf_review_{i}.json').read_text())]
    expected = json.loads((CHECK / 'pdf_quote_check.json').read_text())['unmatched']
    if sorted(x['id'] for x in reviews) != sorted(x['id'] for x in expected):
        raise ValueError('PDF review does not cover every unmatched quotation exactly once')
    patches = []
    keys = set()
    for entry in reviews:
        if entry['status'] == 'typography_or_order':
            continue
        if entry['status'] != 'md_error':
            raise ValueError(f'Unresolved PDF review: {entry}')
        fix = entry['correction_if_any']
        replacements = fix.get('replacements', [{'before': fix.get('before'), 'after': fix.get('after')}])
        for r in replacements:
            if not r['before'] or not r['after']:
                raise ValueError(f'Empty replacement: {entry}')
            key = (entry['page'], r['before'], r['after'])
            if key not in keys:
                patches.append({'page':entry['page'],**r,'audit_id':entry['id']})
                keys.add(key)
    source = ORIGINAL.read_text()
    for patch in patches:
        page = patch['page']
        page_pattern = rf'(<!-- pdf_page: {page} -->.*?<!-- source_text_begin -->)(.*?)(<!-- source_text_end -->)'
        matched = re.search(page_pattern, source, re.S)
        changed, count = replace(matched[2],patch['before'],patch['after'])
        if count == 0:
            raise ValueError(f'Patch not found in source page: {patch}')
        source = source[:matched.start(2)] + changed + source[matched.end(2):]
        patch['source_occurrences'] = count
        for c in data['claims']:
            if c['page'] == page and not c.get('segments'):
                c['quote'], _ = replace(c['quote'],patch['before'],patch['after'])
            for segment in c.get('segments',[]):
                if segment['page'] == page:
                    segment['quote'], _ = replace(segment['quote'],patch['before'],patch['after'])
            if c.get('segments'):
                c['quote'] = norm(' '.join(s['quote'] for s in c['segments']))
            if c.get('context_page',c['page']) == page:
                for field in ['context','display_context']:
                    if c.get(field):c[field], _ = replace(c[field],patch['before'],patch['after'])
    working = CHECK / 'Рабочий_исходник'
    working.mkdir(exist_ok=True)
    report = working / 'report.md'
    report.write_text('> Рабочая версия для извлечения заявлений, 17.11.2026. Точечные исправления выбранных цитат подтверждены PDF; полный посимвольный аудит отчёта не заявляется. Журнал замен: ../source_corrections.json.\n\n'+source)
    assets = working / 'assets'
    if not assets.exists():assets.symlink_to(ORIGINAL.parent / 'assets', target_is_directory=True)
    data['original_source_sha256'] = original_sha
    data['original_source_report'] = str(ORIGINAL)
    data['source_sha256'] = hashlib.sha256(report.read_bytes()).hexdigest()
    data['source_report'] = str(report)
    data['pdf_review'] = {'automatic_text_layer_matches':len(data['claims'])-len(expected),'manually_reviewed_mismatches':len(reviews),'quotes_with_md_errors':sum(e['status']=='md_error' for e in reviews),'working_source_patches':len(patches)}
    for i,c in enumerate(data['claims'],1):c['audit_id']=i
    (SAMPLE / 'claims.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    (CHECK / 'source_corrections.json').write_text(json.dumps({'original_sha256':original_sha,'working_sha256':data['source_sha256'],'patches':patches,'scope':'Selected extracted quotations, not every word of the report'},ensure_ascii=False,indent=2)+'\n')
    if hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() != original_sha:
        raise ValueError('Original must remain unchanged')
    print(json.dumps(data['pdf_review'],ensure_ascii=False))


if __name__ == '__main__':main()
