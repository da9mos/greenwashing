"""Broad ESG extraction contract. Semantic annotation happens outside this stdlib CLI."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'esg-extraction-3.0'
TYPES = ('обязательство', 'результат', 'декларация')
TOPICS = ('E', 'S', 'G')

# Keep numeric evidence verbatim, but do not accept part of a different number.
# Grouping spaces include the two non-breaking variants used by report tables.
_INTEGER = r'(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?!\d)|\d+)'
_NUMBER = rf'(?:[+−↑↓][ \u00a0\u202f]*|-)?{_INTEGER}(?:[.,]\d+)?(?:[eE][+\-−]?\d+)?'
_NUMERIC_EXPRESSION = re.compile(rf'{_NUMBER}(?:[ \u00a0\u202f]*(?:[–—\-/])[ \u00a0\u202f]*{_NUMBER})*')


def evidence_supports(field, value, quote):
    """Check literal support; numeric fields must cover whole numeric expressions.

    A value may appear within prose, but 5 is not supported by 517, -5, 5.17,
    1 005 or 5–7. Full ranges/periods and surrounding words remain allowed.
    This only checks tokens, not metric/year/column semantic alignment.
    """
    if field not in ('value', 'period'):
        return value in quote
    if not value:
        return False
    numbers = list(_NUMERIC_EXPRESSION.finditer(quote))
    for match in re.finditer(re.escape(value), quote):
        start, end = match.span()
        if all(not (number.start() < end and number.end() > start)
               or (start <= number.start() and number.end() <= end)
               for number in numbers):
            return True
    return False


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def text(value):
    return isinstance(value, str) and bool(value.strip())


def whole_word_quote(quote, source):
    """Match a continuous source span without clipping a word or its line wrap."""
    for match in re.finditer(re.escape(quote), source):
        start, end = match.span()
        start += len(quote) - len(quote.lstrip())
        end -= len(quote) - len(quote.rstrip())
        if start == end:
            continue
        word = lambda char: char.isalnum() or char == '_'
        if word(source[start]):
            if start and word(source[start - 1]):
                continue
            # Do not accept "зультате" from "ре-\nзультате" or a compound word.
            if re.search(r'\w[-\u00ad\u2010\u2011](?:[ \t\r]*\n[ \t]*)?$', source[:start]):
                continue
        if word(source[end - 1]):
            if end < len(source) and word(source[end]):
                continue
            if re.match(r'[-\u00ad\u2010\u2011](?:[ \t\r]*\n[ \t]*)?\w', source[end:]):
                continue
        return True
    return False


def presentation_status(claim, blocks):
    """Validate display-only provenance; never substitute an analytical statement.

    Legacy absence preserves classification compatibility and remains unprepared
    for display. Ready means mechanically verified text, not semantic/PDF QA.
    """
    present = ('presentation_quote' in claim, 'presentation_block_id' in claim)
    if not any(present):
        return 'unprepared_legacy'
    require(all(present), 'Неполная пара presentation_quote/presentation_block_id')
    quote, block_id = claim['presentation_quote'], claim['presentation_block_id']
    require(text(quote) and isinstance(block_id, str) and block_id in blocks,
            'Пустая цитата для вывода или неизвестный presentation_block_id')
    require(any(e['block_id'] == block_id for e in claim['evidence']),
            'Presentation-блок не связан с evidence заявления')
    require(quote in blocks[block_id]['text'], 'Presentation quote не является непрерывной точной цитатой')
    require(whole_word_quote(quote, blocks[block_id]['text']),
            'Presentation quote обрезает слово или перенос слова')
    return 'ready'


def preamble(path):
    path=Path(path)
    if path.suffix.lower() != '.md':return ''
    raw=path.read_bytes().decode('utf-8-sig')
    mark=re.search(r'<!--\s*pdf_page:\s*(\d+)\s*-->',raw)
    return raw[:mark.start()] if mark else ''


def verify_preamble(value):
    if not value.strip():return
    lines=[line for line in value.splitlines() if line.strip()]
    if len(lines) > 9 and lines[0].startswith('# ') and lines[1].startswith('- Идентификатор:') and lines[8].startswith('- Визуальный статус:') and lines[9] == '---':
        # Repository corpus wrapper. The full preamble remains in preamble.txt for separate review.
        return
    require(len(lines)>=2 and lines[0].startswith('# ') and lines[1].startswith('> Служебная информация о переносе') and all(line.startswith('>') for line in lines[1:]), 'Нераспознанный preamble: нужен отдельный смысловой разбор; физическая страница не присваивается')


def load_pages(path):
    path = Path(path)
    require(path.suffix.lower() in ('.md', '.jsonl', '.txt'), 'Нужна проверенная транскрипция MD/JSONL/TXT; PDF напрямую не принимается')
    raw = path.read_bytes().decode('utf-8-sig')
    if path.suffix.lower() == '.jsonl':
        pages = [json.loads(line) for line in raw.splitlines() if line.strip()]
        kind = 'provided_page_numbers_not_independently_verified'
    elif path.suffix.lower() == '.md':
        marks = list(re.finditer(r'<!--\s*pdf_page:\s*(\d+)\s*-->', raw))
        require(marks, 'MD должен содержать pdf_page')
        verify_preamble(raw[:marks[0].start()])
        pages = [{'page': int(m[1]), 'text': raw[m.end():marks[i+1].start() if i+1 < len(marks) else len(raw)]} for i,m in enumerate(marks)]
        kind = 'declared_pdf_page_numbers_not_independently_verified'
        if raw[:marks[0].start()].strip():kind += '_service_preamble_saved_separately'
    else:
        pages = [{'page': i+1, 'text': part} for i,part in enumerate(raw.split('\f'))]
        kind = 'text_segment_numbers_not_physical_pages'
    require(pages and all(isinstance(p,dict) and type(p.get('page')) is int and p['page'] > 0 and isinstance(p.get('text'),str) for p in pages), 'Неверные страницы')
    ids = [p['page'] for p in pages]
    require(ids == list(range(1, len(ids)+1)), 'Повтор, пропуск или нарушение порядка номеров страниц; требуется полный ряд от 1')
    return pages, kind


def blocks_for(pages, report_id):
    blocks = []
    for p in pages:
        # Paragraph slices are exact: no whitespace/OCR/HTML rewriting, no size filtering.
        matches = list(re.finditer(r'\S.*?(?=\n[ \t\r]*\n|\Z)', p['text'], re.S))
        for i,m in enumerate(matches,1):
            blocks.append({'id': f"{report_id}:p{p['page']}:b{i}", 'page': p['page'], 'start': m.start(), 'end': m.end(), 'text': m.group()})
        if not matches:
            blocks.append({'id': f"{report_id}:p{p['page']}:b0", 'page': p['page'], 'start': 0, 'end': 0, 'text': ''})
    return blocks


def prepare(source, output, report_id, prompt=ROOT/'agent/esg_agent_v3.md', taxonomy=ROOT/'agent/taxonomy.csv', pages_per_batch=4):
    require(text(report_id) and re.fullmatch(r'[\w-]+', report_id), 'Неверный report_id')
    require(type(pages_per_batch) is int and pages_per_batch > 0, 'Размер партии должен быть положительным')
    source, prompt, taxonomy = map(lambda p: Path(p).resolve(), (source,prompt,taxonomy))
    pages, page_kind = load_pages(source)
    blocks = blocks_for(pages, report_id)
    out = Path(output); require(not out.exists(), 'Каталог результата уже существует')
    hashes = {'source_sha256':sha(source), 'prompt_sha256':sha(prompt), 'taxonomy_sha256':sha(taxonomy)}
    out.mkdir(parents=True); (out/'batches').mkdir()
    write(out/'pages.json', pages); write(out/'blocks.json', blocks)
    (out/'preamble.txt').write_bytes(preamble(source).encode('utf-8'))
    batches = []
    for n,start in enumerate(range(0,len(pages),pages_per_batch),1):
        target = {p['page'] for p in pages[start:start+pages_per_batch]}
        context = {p['page'] for p in pages[max(0,start-1):start+pages_per_batch+1]} - target
        bid = f'{report_id}_b{n:04d}'
        batch = {'schema_version': VERSION, **hashes, 'batch_id':bid, 'target_block_ids':[b['id'] for b in blocks if b['page'] in target], 'blocks':[b for b in blocks if b['page'] in target|context]}
        path = out/'batches'/f'{bid}.json'; write(path,batch)
        batches.append({'id':bid,'file':str(path.relative_to(out)),'sha256':sha(path)})
    manifest = {'schema_version':VERSION, 'report_id':report_id, **hashes, 'source_path':str(source), 'prompt_path':str(prompt), 'taxonomy_path':str(taxonomy), 'page_kind':page_kind, 'pages_per_batch':pages_per_batch, 'preamble_sha256':sha(out/'preamble.txt'), 'preamble_status':'excluded_from_physical_page_coverage_not_semantically_reviewed' if preamble(source).strip() else 'empty', 'pages_sha256':sha(out/'pages.json'), 'blocks_sha256':sha(out/'blocks.json'), 'batches':batches}
    write(out/'manifest.json',manifest)
    (out/'manifest.sha256').write_text(sha(out/'manifest.json'),encoding='ascii')
    return manifest


def workspace(work):
    work=Path(work)
    require(sha(work/'manifest.json') == (work/'manifest.sha256').read_text().strip(), 'Manifest изменён')
    m=read(work/'manifest.json'); require(m.get('schema_version')==VERSION,'Неверная версия')
    for key in ('source','prompt','taxonomy'):
        require(sha(m[key+'_path'])==m[key+'_sha256'], f'{key} изменён')
    for name in ('pages','blocks'):
        require(sha(work/(name+'.json'))==m[name+'_sha256'], f'{name} изменён')
    require(sha(work/'preamble.txt')==m['preamble_sha256'] and (work/'preamble.txt').read_bytes().decode('utf-8')==preamble(m['source_path']), 'Preamble изменён')
    pages,kind=load_pages(m['source_path'])
    require(pages==read(work/'pages.json') and kind==m['page_kind'],'Исходник/страницы отличаются')
    require(blocks_for(pages,m['report_id'])==read(work/'blocks.json'),'Реестр блоков отличается')
    for b in m['batches']:
        require(sha(work/b['file'])==b['sha256'], 'Партия изменена')
    with Path(m['taxonomy_path']).open(encoding='utf-8-sig',newline='') as f:
        taxonomy={(r['block'],r['topic']) for r in csv.DictReader(f,delimiter=';')}
    return m,taxonomy


def check(work, response):
    return check_batch(work, response, *workspace(work))


def check_batch(work, response, m, taxonomy):
    d=read(response) if isinstance(response,(str,Path)) else response
    require(isinstance(d,dict),'Ожидается объект ответа')
    require(d.get('schema_version')==VERSION and d.get('source_sha256')==m['source_sha256'],'Версия/хеш ответа неверны')
    batch_entry=next((b for b in m['batches'] if b['id']==d.get('batch_id')),None)
    require(batch_entry is not None,'Лишняя/неизвестная партия')
    batch=read(Path(work)/batch_entry['file']); targets=set(batch['target_block_ids']); blocks={b['id']:b for b in batch['blocks']}
    require(text(d.get('reviewer')),'Нет проверяющего')
    require(isinstance(d.get('claims'),list) and isinstance(d.get('coverage'),list),'Нет claims/coverage')
    claims={}; used={}; pending_claims=0; presentation_ready=0; presentation_statuses={}
    for c in d['claims']:
        require(isinstance(c,dict) and text(c.get('id')) and c['id'] not in claims,'Дубль/неверный ID заявления')
        cid=c['id']; claims[cid]=c
        require(c.get('type') in TYPES and (c.get('block'),c.get('topic')) in taxonomy,'Тип/тема вне справочника')
        require(c.get('block2') in (*TOPICS,'') and c['block2']!=c['block'],'Неверная дополнительная тема')
        require(text(c.get('statement')) and text(c.get('reason')),'Пустое заявление/основание')
        require(c.get('source_kind') in ('text','table','chart') and c.get('source_status') in ('md_only','needs_pdf_review'),'Неверный источник/статус')
        require(type(c.get('quantitative')) is bool,'Нет quantitative boolean')
        ev=c.get('evidence'); require(isinstance(ev,list) and ev,'Нет evidence')
        used[cid]=set()
        for e in ev:
            require(isinstance(e,dict) and e.get('block_id') in blocks,'Неизвестный evidence-блок')
            require(text(e.get('quote')) and e['quote'] in blocks[e['block_id']]['text'],'Цитата не совпадает точно')
            require(e.get('role') in ('statement','subject','metric','value','unit','period','context'),'Неверная роль')
            require(e['role'] not in ('value','period') or evidence_supports(e['role'], e['quote'], blocks[e['block_id']]['text']),
                    'Числовая цитата вырезана из другого числа/периода')
            used[cid].add(e['block_id'])
        require(any(e['block_id'] in targets and e['role'] in ('statement','value','metric') for e in ev),'Заявление без собственного statement/value/metric в target')
        if not c['quantitative']:
            quotes=[e['quote'] for e in ev if e['role']=='statement']
            require(quotes and c['statement']==' '.join(quotes),'Statement отличается от точных цитат')
        else:
            fields=('metric','value','unit','period','entity_scope')
            require(all(isinstance(c.get(k),str) for k in fields),'Количественные поля должны быть строками, неизвестные — пустыми строками')
            for k in fields:
                role='subject' if k=='entity_scope' else k
                require(not c[k] or any(e['role']==role and evidence_supports(k, c[k], e['quote']) for e in ev), f'{k} не подтверждено дословным фрагментом соответствующей роли')
            complete=all(text(c.get(k)) for k in fields) and {'subject','metric','value','unit','period'} <= {e['role'] for e in ev}
            require(complete or c['source_status']=='needs_pdf_review','Неполный количественный контекст требует needs_pdf_review')
        require(c['source_kind']!='chart' or c['source_status']=='needs_pdf_review','График требует PDF review')
        pending_claims+=c['source_status']=='needs_pdf_review'
        presentation_statuses[cid] = presentation_status(c, blocks)
        presentation_ready += presentation_statuses[cid] == 'ready'
    cov={}
    for e in d['coverage']:
        require(isinstance(e,dict) and e.get('block_id') in targets and e['block_id'] not in cov,'Пропуск/дубль/чужой coverage-блок')
        bid=e['block_id']; cov[bid]=e
        require(e.get('status') in ('extracted','excluded','pending') and text(e.get('reason')),'Неверный coverage status/reason')
        refs=e.get('claim_ids'); require(isinstance(refs,list) and all(isinstance(cid,str) and cid in claims for cid in refs) and len(set(refs))==len(refs),'Неверные claim_ids')
        require(all(bid in used[cid] for cid in refs),'Coverage не соответствует evidence')
        require((e['status']!='extracted' or refs) and (e['status']!='excluded' or not refs),'Coverage противоречит ссылкам')
        image=bool(re.search(r'!\[|<img\b|Визуальный материал:|визуальный элемент оригинала',blocks[bid]['text'],re.I))
        require(not image or e['status']=='pending','Блок с изображением должен оставаться pending')
    require(set(cov)==targets,'Не все target блоки покрыты')
    for cid,bids in used.items():
        require(all(cid in cov[bid]['claim_ids'] for bid in bids&targets),'Нет обратной coverage ссылки')
    return d, {'pending_blocks':sum(e['status']=='pending' for e in cov.values()),'pending_claims':pending_claims,
               'presentation_ready_claims':presentation_ready,
               'presentation_unready_claims':len(claims)-presentation_ready,
               'presentation_status_by_claim':presentation_statuses}


def csv_write(path, rows, fields):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter=';'); w.writeheader(); w.writerows(rows)
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        require(list(csv.DictReader(f,delimiter=';'))==[{k:str(r[k]) for k in fields} for r in rows],'CSV readback mismatch')


def export(work, responses, output, allow_partial=False):
    m, taxonomy = workspace(work)
    checked = (check_batch(work, response, m, taxonomy) for response in responses)
    return export_checked(work, checked, output, m, allow_partial)


def export_checked(work, checked, output, m, allow_partial):
    expected={b['id'] for b in m['batches']}; seen=set(); ids=set(); claims=[]; coverage=[]; pb=pc=pr=pu=0
    for d,s in checked:
        require(d['batch_id'] not in seen,'Дублирован ответ партии');seen.add(d['batch_id'])
        for c in d['claims']:
            require(c['id'] not in ids,'Дублирован ID заявления между партиями');ids.add(c['id']);claims.append(c)
        coverage.extend(d['coverage']);pb+=s['pending_blocks'];pc+=s['pending_claims']
        pr+=s['presentation_ready_claims'];pu+=s['presentation_unready_claims']
    require(seen==expected,'Недостающие/лишние ответы партий')
    partial=bool(pb or pc); require(not partial or allow_partial,'Есть unresolved coverage/source; нужен --allow-partial')
    out=Path(output); out=out.with_name(out.name+'_draft') if allow_partial else out
    require(not out.exists(),'Каталог экспорта уже существует')
    blocks=read(Path(work)/'blocks.json'); order={b['id']:i for i,b in enumerate(blocks)};page={b['id']:b['page'] for b in blocks}
    claims.sort(key=lambda c:min(order[e['block_id']] for e in c['evidence']))
    rows=[{'id':c['id'],'statement':c['statement'],'type':c['type'],'block':c['block'],'topic':c['topic'],'block2':c['block2'],'source_status':c['source_status'],'pages':','.join(map(str,sorted({page[e['block_id']] for e in c['evidence']}))),
           'presentation_quote':c.get('presentation_quote',''),'presentation_block_id':c.get('presentation_block_id',''),
           'presentation_status':'ready' if 'presentation_quote' in c else 'unprepared_legacy'} for c in claims]
    fields=['id','statement','type','block','topic','block2','source_status','pages','presentation_quote','presentation_block_id','presentation_status']
    out.mkdir(parents=True)
    csv_write(out/'claims.csv',rows,fields)
    for topic in TOPICS:csv_write(out/(topic+'.csv'),[r for r in rows if r['block']==topic],fields)
    csv_write(out/'coverage.csv',[{'block_id':e['block_id'],'status':e['status'],'reason':e['reason'],'claim_ids':','.join(e['claim_ids'])} for e in coverage],['block_id','status','reason','claim_ids'])
    summary={'schema_version':VERSION,'status':'partial' if allow_partial else 'declared_md_coverage_complete','claims':len(claims),'pending_blocks':pb,'pending_claims':pc,'primary_counts':{t:sum(c['block']==t for c in claims) for t in TOPICS},'secondary_counts':{t:sum(c['block2']==t for c in claims) for t in TOPICS},'page_kind':m['page_kind'],'preamble_status':m['preamble_status'],'limitations':'MD coverage only; not proven semantic recall, PDF completeness or external truth. Numeric reconstruction requires semantic review.'}
    summary.update(presentation_ready_claims=pr,presentation_unready_claims=pu,
                   presentation_readiness='mechanical_quote_checks_only_not_semantic_or_pdf_certification')
    write(out/'claims.json',{'manifest':m,'claims':claims,'coverage':coverage});write(out/'summary.json',summary)
    return out,summary


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('source');a.add_argument('--out',required=True);a.add_argument('--report-id',required=True);a.add_argument('--prompt',default=ROOT/'agent/esg_agent_v3.md');a.add_argument('--taxonomy',default=ROOT/'agent/taxonomy.csv');a.add_argument('--pages-per-batch',type=int,default=4)
    a=sub.add_parser('check');a.add_argument('--work',required=True);a.add_argument('response')
    a=sub.add_parser('export');a.add_argument('--work',required=True);a.add_argument('--responses',nargs='+',required=True);a.add_argument('--out',required=True);a.add_argument('--allow-partial',action='store_true')
    a=p.parse_args()
    try:
        if a.command=='prepare':r=prepare(a.source,a.out,a.report_id,a.prompt,a.taxonomy,a.pages_per_batch)
        elif a.command=='check':_,r=check(a.work,a.response)
        else:out,r=export(a.work,a.responses,a.out,a.allow_partial);r['output']=str(out)
        print(json.dumps(r,ensure_ascii=False));return 0
    except (ValueError,TypeError,KeyError,OSError) as e:print(f'ОШИБКА: {e}');return 2

if __name__=='__main__':raise SystemExit(main())
