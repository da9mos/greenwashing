"""Publish verified native-layer candidates as a separate local analytical corpus.

No API/LLM/import of model runners. Only this primary corpus and its validation
registry are written. Native candidates are read-only and assets are hardlinked.
"""
from __future__ import annotations
import argparse
import concurrent.futures as futures
import multiprocessing
from collections import Counter
import csv
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time

for lib in ('/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs'):
    if Path(lib).is_dir():sys.path.insert(0,lib)
import pymupdf as fitz
from PIL import Image
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup

BASE=Path(__file__).resolve().parents[1]
REGISTRY=BASE.parents[2]/'11_Проект_Сбер/3_итерация/greenwashing/01_итерация_1_сбор_данных/выборка_30/reports.csv'
PRIMARY='Все_отчёты_MD'
MARKER=re.compile(r'<!--\s*pdf_page:\s*(\d+)\s*-->')
NOTE=re.compile(r'\n<!-- corpus_note_start: \d+ -->.*?<!-- corpus_note_end: \d+ -->\n',re.S)
HEADER='> Служебная информация: перенос из текстового слоя + геометрии, символьный состав сверен, ограничения помечены.\n\n> Происхождение: Codex-root и локальные инструменты переноса; это не ответ DeepSeek и не одобрение Codex CLI. Полная визуальная и смысловая сверка не завершена.\n\n'
RENDER=MarkdownIt('commonmark',{'html':True})
HASH_CACHE={}
PUBLISHER_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

class InvalidCandidate(ValueError):
    def __init__(self,code,message):self.code=code;super().__init__(message)

def fail(code,message):raise InvalidCandidate(code,message)

def stat(path):
    s=path.stat();return (s.st_ino,s.st_size,s.st_mtime_ns)

def sha(path):
    key=(str(path.resolve()),stat(path))
    if key not in HASH_CACHE:
        h=hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
        HASH_CACHE[key]=h.hexdigest()
    return HASH_CACHE[key]

def load(path):return json.loads(path.read_bytes())

def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+f'.{os.getpid()}.part')
    temp.write_bytes(data if isinstance(data,bytes) else data.encode());temp.replace(path)

def page_parts(md,n):
    markers=list(MARKER.finditer(md))
    if [int(m[1]) for m in markers]!=list(range(1,n+1)):fail('PAGE_MARKERS','Physical page markers must be exactly 1..N')
    if 'pdf_page' in MARKER.sub('',md):fail('MALFORMED_PAGE_MARKER','Unrecognized physical-page marker')
    return [(i+1,md[m.start():markers[i+1].start() if i+1<len(markers) else len(md)]) for i,m in enumerate(markers)]

def native_prefix(page_md):
    body=MARKER.sub('',page_md, count=1)
    body=re.sub(r'^\s*<a id="pdf-page-\d+"></a>','',body,count=1)
    stops=[body.find(x) for x in ('> Служебная пометка: распознанный текст изображения',
            '> Служебная информация: ссылки исходного PDF','<details>') if x in body]
    return body[:min(stops)] if stops else body

def empty_columns(table):
    rows=table.find_all('tr',recursive=False)
    if not rows:rows=table.find_all('tr')
    grid={};width=0
    for r,row in enumerate(rows):
        c=0
        for cell in row.find_all(['td','th'],recursive=False):
            while (r,c) in grid:c+=1
            try:cs=int(cell.get('colspan',1));rs=int(cell.get('rowspan',1))
            except (TypeError,ValueError):return []
            if not (1<=cs<=500 and 1<=rs<=500):return []
            text=cell.get_text().strip()
            for rr in range(r,min(len(rows),r+rs)):
                for cc in range(c,c+cs):grid[rr,cc]=text
            c+=cs;width=max(width,c)
    return [c+1 for c in range(width) if len(rows)>1 and all(not grid.get((r,c),'') for r in range(len(rows)))]

def page_notes(record,body,anchors):
    messages=[];tags=[]
    if record.get('ocr_engine') or record.get('ocr_error') or record.get('ocr_chars') is not None:
        if record.get('ocr_verified') is not True:
            tags.append('ocr');messages.append('OCR и текст внутри изображений не проверены: сверяйте распознанный фрагмент с изображением страницы.')
    if record.get('unresolved_unicode'):
        tags.append('unicode');messages.append('В текстовом слое есть нерасшифрованные или нестандартные символы; чтение этих мест требует сверки с изображением.')
    if record.get('ambiguous_cell_assignments'):
        tags.append('ambiguity');messages.append('Часть символов неоднозначно отнесена к ячейкам таблицы; структура и принадлежность значений требуют сверки с оригиналом.')
    if record.get('table_detection_error'):
        tags.append('table');messages.append('Детектор геометрии таблицы сообщил ошибку; табличную структуру на этой странице нужно проверить.')
    if record.get('overlapping_native_conflicts'):
        tags.append('ocr_overlap');messages.append('Выявлены спорные пересечения OCR и текстового слоя; не считать дополнительное распознавание подтверждённым.')
    soup=BeautifulSoup(RENDER.render(body),'html.parser')
    broken=[a.get('href') for a in soup.find_all('a') if str(a.get('href','')).startswith('#') and a['href'][1:] not in anchors]
    if record.get('unresolved_source_links') or broken:
        tags.append('links');messages.append('Есть неразрешённые назначения ссылок исходного PDF; недостающие адреса не восстановлены догадкой.')
    for i,table in enumerate(soup.find_all('table'),1):
        cols=empty_columns(table)
        if cols:
            tags.append('empty_column');messages.append(f'В таблице {i} обнаружены полностью пустые неназванные столбцы {", ".join(map(str,cols))}. Структура не подтверждена; это не доказанная ошибка. Арбитр — изображение исходной страницы; данные не изменены.')
    if record.get('issues') and not messages:
        tags.append('other');messages.append('Для этой страницы сохранены нерешённые замечания обработки; используйте изображение оригинала и реестр ограничений.')
    return messages,sorted(set(tags))

def transform(md,n,records,provenance=None):
    first=MARKER.search(md)
    if not first:fail('PAGE_MARKERS','No physical page marker')
    prefix=md[:first.start()]
    if not prefix.startswith('> Служебная информация: механический исходный кандидат'):
        fail('UNEXPECTED_PREFIX','Refuse to discard a possibly author-written prefix')
    original=md[first.start():];parts=[];limitations={}
    anchors={f'pdf-page-{i}' for i in range(1,n+1)}
    for number,body in page_parts(md,n):
        messages,tags=page_notes(records[number-1],body,anchors)
        if messages:
            a=re.match(r'<!--\s*pdf_page:\s*\d+\s*-->\s*<a id="pdf-page-\d+"></a>',body)
            if not a:fail('PAGE_ANCHOR','Required page anchor absent')
            note=f'\n<!-- corpus_note_start: {number} -->\n'+''.join('> Служебная пометка: '+m+'\n>\n' for m in messages)+f'<!-- corpus_note_end: {number} -->\n'
            body=body[:a.end()]+note+body[a.end():]
            limitations[number]={'tags':tags,'notes':messages}
        parts.append(body)
    extra=''
    if provenance:
        extra=f'> Служебные данные: RID {provenance["rid"]}; физических страниц: {n}.'
        url=provenance.get('source_url')
        if isinstance(url,str) and url.startswith(('https://','http://')) and not any(c in url for c in '<>\n\r'):
            label='Архив источника' if provenance.get('archive') else 'Исходная ссылка'
            extra+=f' [{label}](<{url}>)'
        extra+='\n\n'
    final=HEADER+extra+''.join(parts)
    if NOTE.sub('',final[MARKER.search(final).start():])!=original:fail('AUTHOR_BODY_CHANGED','Publication modified source author body')
    return final,limitations

def validate_candidate(base,row):
    rid=row['report_id'];candidate=base/'_проверка/native_candidates'/rid;checks=candidate/'_проверка'
    required=[candidate/'report.md']+[checks/name for name in ('native_coverage.json','pages.json','source_input.json','native_assets.json')]
    batch_file=base/'_проверка/native_candidate_batch.json'
    batch_record=None
    if batch_file.exists():
        batch=load(batch_file);batch_record=batch.get('reports',{}).get(rid)
        if not batch_record:return {'state':'pending','code':'AWAITING_CURRENT_BATCH'},None
        if batch_record.get('state')=='needs_review':fail('BATCH_CANDIDATE_ERROR',batch_record.get('error','Native producer requires review'))
        if batch_record.get('state')!='candidate_ready':return {'state':'pending','code':'AWAITING_CURRENT_BATCH'},None
    if not (checks/'native_coverage.json').exists():return {'state':'pending','code':'CANDIDATE_NOT_FINISHED'},None
    for path in required:
        if not path.is_file():fail('MISSING_ARTIFACT',str(path.relative_to(base)))
    before={str(p):stat(p) for p in required}
    source=base/'_источники'/f'{rid}.pdf'
    if not source.is_file():fail('MISSING_SOURCE',rid)
    source_stat=stat(source);impl_stat=stat(base/'tools/native_candidate.py')
    source_hash=sha(source);impl_hash=sha(base/'tools/native_candidate.py')
    coverage=load(checks/'native_coverage.json');receipt=load(checks/'source_input.json')
    if batch_record:
        if batch_record.get('source_sha256')!=source_hash or batch_record.get('implementation_sha256')!=impl_hash:
            return {'state':'pending','code':'AWAITING_CURRENT_SOURCE_IMPLEMENTATION'},None
        if batch_record.get('report_sha256')!=coverage.get('report_sha256'):fail('BATCH_RECEIPT_MISMATCH',rid)
    for data in (coverage,receipt):
        if data.get('source_sha256')!=source_hash:fail('SOURCE_SHA_MISMATCH',rid)
        if data.get('implementation_sha256')!=impl_hash:fail('IMPLEMENTATION_SHA_MISMATCH',rid)
    md=(candidate/'report.md').read_bytes().decode('utf-8');report_hash=sha(candidate/'report.md')
    if coverage.get('report_sha256')!=report_hash:fail('REPORT_SHA_MISMATCH',rid)
    records=load(checks/'pages.json').get('pages',[]);assets=load(checks/'native_assets.json')
    asset_stats={};glyphs=0
    with fitz.open(source) as doc:
        n=len(doc)
        if coverage.get('pages')!=n or [r.get('pdf_page') for r in records]!=list(range(1,n+1)):fail('PAGE_REGISTRY','Incomplete page accounting')
        parts=page_parts(md,n)
        if coverage.get('all_native_glyphs_assigned_once') is not True:fail('NATIVE_COVERAGE','Coverage receipt did not pass')
        for number,body in parts:
            record=records[number-1]
            if record.get('all_native_glyphs_assigned_once') is not True or record.get('rendered_native_character_inventory_matches') is not True:
                fail('NATIVE_PAGE_ACCOUNTING',f'{rid}:{number}')
            raw=doc[number-1].get_text('rawdict')
            units=[c['c'] for block in raw['blocks'] for line in block.get('lines',[]) for span in line.get('spans',[]) for c in span.get('chars',[])]
            if record.get('native_glyphs')!=len(units) or record.get('native_nonspace_glyphs')!=sum(bool(c.strip()) for c in units):
                fail('SOURCE_GLYPH_COUNT',f'{rid}:{number}')
            if sum(o.get('glyph_count',0) for o in record.get('objects',[]))!=len(units):fail('OBJECT_GLYPH_COUNT',f'{rid}:{number}')
            source_chars=Counter(c for u in units for c in u if not c.isspace())
            rendered=BeautifulSoup(RENDER.render(native_prefix(body)),'html.parser').get_text()
            actual_chars=Counter(c for c in rendered if not c.isspace())
            if source_chars!=actual_chars:fail('RENDERED_INVENTORY',f'{rid}:{number}')
            glyphs+=len(units)
            name=f'page_{number:04d}.png';path=candidate/'assets'/name
            if not path.is_file():fail('MISSING_ASSET',f'{rid}:{name}')
            if assets.get(name)!=sha(path):fail('ASSET_SHA_MISMATCH',f'{rid}:{name}')
            with Image.open(path) as image:image.verify()
            with Image.open(path) as image:image.load()
            if f'assets/{name}' not in body:fail('PAGE_IMAGE_REFERENCE',f'{rid}:{number}')
            asset_stats[name]=stat(path)
    for name,digest in assets.items():
        path=(candidate/'assets'/name).resolve()
        if not path.is_relative_to((candidate/'assets').resolve()):fail('UNSAFE_ASSET',name)
        if not path.is_file() or sha(path)!=digest:fail('ASSET_MANIFEST',name)
        asset_stats[name]=stat(path)
    manifest=base/'_проверка/sources_manifest.json'
    source_meta=next((x for x in load(manifest).get('reports',[]) if x.get('report_id')==rid),{}) if manifest.exists() else {}
    provenance={'rid':rid,'source_url':source_meta.get('source_url'),'archive':bool(source_meta.get('archive_member') or source_meta.get('archive_members'))}
    final,limitations=transform(md,n,records,provenance)
    if any(stat(p)!=before[str(p)] for p in required) or stat(source)!=source_stat or stat(base/'tools/native_candidate.py')!=impl_stat:
        fail('CANDIDATE_CHANGED','Retry after producer finishes')
    if any(stat(candidate/'assets'/name)!=expected for name,expected in asset_stats.items()):
        fail('CANDIDATE_CHANGED','Asset changed during validation')
    result={'state':'validated','code':'PASS','source_sha256':source_hash,'implementation_sha256':impl_hash,
            'publisher_sha256':PUBLISHER_SHA,'candidate_md_sha256':report_hash,'final_md_sha256':hashlib.sha256(final.encode()).hexdigest(),
            'pages':n,'native_glyphs':glyphs,'native_pass':True,'rendered_inventory_pass':True,
            'author_body_unchanged':True,'checked':False,'semantic_source_review_completed':False,
            'source_url':source_meta.get('source_url'),'source_url_is_archive':provenance['archive'],'limitations':limitations,'ocr_pages':[p for p,x in limitations.items() if 'ocr' in x['tags']],
            'unicode_pages':[p for p,x in limitations.items() if 'unicode' in x['tags']],
            'ambiguity_pages':[p for p,x in limitations.items() if 'ambiguity' in x['tags']],
            'unresolved_link_pages':[p for p,x in limitations.items() if 'links' in x['tags']],
            'empty_column_pages':[p for p,x in limitations.items() if 'empty_column' in x['tags']],
            'candidate_sidecar_stats':before,'asset_stats':asset_stats,'source_stat':source_stat,'native_implementation_stat':impl_stat}
    return result,(candidate,final,assets)

def publish(base,row,result,payload):
    candidate,final,assets=payload;primary=base/PRIMARY;target=primary/row['company_id']/row['report_id']
    receipt=primary/'_проверка/published'/f"{row['report_id']}.json"
    if target.is_dir() and receipt.exists():
        old=load(receipt)
        if old.get('final_md_sha256')==result['final_md_sha256'] and (target/'report.md').is_file() and sha(target/'report.md')==result['final_md_sha256']:
            result.update(state='published',output=str(target.relative_to(base)),asset_method=old.get('asset_method'))
            atomic(receipt,json.dumps(result,ensure_ascii=False,indent=2)+'\n');return
    stage=primary/'_проверка/staging'/f"{row['report_id']}-{os.getpid()}-{time.time_ns()}";stage.mkdir(parents=True)
    method=Counter()
    try:
        for name in assets:
            dest=stage/'assets'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            try:os.link(candidate/'assets'/name,dest);method['hardlink']+=1
            except OSError:shutil.copy2(candidate/'assets'/name,dest);method['copy']+=1
        for name,digest in assets.items():
            if sha(stage/'assets'/name)!=digest:fail('CANDIDATE_CHANGED','Asset changed before atomic publication: '+name)
        (stage/'report.md').write_bytes(final.encode())
        if sha(stage/'report.md')!=result['final_md_sha256']:fail('FINAL_REPORT_SHA','Publication write mismatch')
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            history=primary/'_проверка/previous'/row['company_id']/row['report_id']/str(time.time_ns())
            history.parent.mkdir(parents=True,exist_ok=True);target.rename(history)
        stage.rename(target)
        result.update(state='published',output=str(target.relative_to(base)),asset_method=dict(method))
        atomic(receipt,json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    finally:
        if stage.exists():shutil.rmtree(stage)

def input_signature(base,row):
    rid=row['report_id'];c=base/'_проверка/native_candidates'/rid
    paths=[base/'_источники'/f'{rid}.pdf',base/'tools/native_candidate.py',c/'report.md']+list((c/'_проверка').glob('*.json'))+list((c/'assets').glob('*'))
    final=base/PRIMARY/row['company_id']/rid/'report.md'
    if final.exists():paths.append(final)
    signature=tuple((str(p),stat(p)) for p in sorted(paths) if p.is_file())
    batch=base/'_проверка/native_candidate_batch.json'
    if batch.exists():
        data=load(batch);record=data.get('reports',{}).get(rid)
        signature+=(('__current_batch_record__',data.get('started_at'),data.get('implementation_sha256'),json.dumps(record,sort_keys=True)),)
    return signature

def write_status(base,rows,results,active=None):
    primary=base/PRIMARY;primary.mkdir(exist_ok=True);counts=Counter(r['state'] for r in results.values())
    summary={'updated_at':time.time(),'publisher_pid':os.getpid(),'currently_validating':active,
             'reports_expected':len(rows),'companies':len({r['company_id'] for r in rows}),'states':dict(counts),
             'published_pages':sum(r.get('pages',0) for r in results.values() if r['state']=='published'),
             'checked':False,'publisher_sha256':PUBLISHER_SHA,'reports':results}
    root=base/'_проверка';atomic(root/'native_corpus_validation.json',json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    fields=['report_id','company_id','state','code','pages','source_sha256','implementation_sha256','candidate_md_sha256','final_md_sha256','native_pass','rendered_inventory_pass','author_body_unchanged','ocr_pages','unicode_pages','ambiguity_pages','unresolved_link_pages','empty_column_pages','checked','message']
    buf=io.StringIO();w=csv.DictWriter(buf,fields,delimiter=';',extrasaction='ignore');w.writeheader()
    for row in rows:
        value=dict(results[row['report_id']],report_id=row['report_id'],company_id=row['company_id'],checked=False)
        for key in ['ocr_pages','unicode_pages','ambiguity_pages','unresolved_link_pages','empty_column_pages']:value[key]=json.dumps(value.get(key,[]))
        w.writerow(value)
    atomic(root/'native_corpus_validation.csv','\ufeff'+buf.getvalue())
    lines=['# Основной локальный набор PDF → Markdown','',f"Опубликовано **{counts['published']}/{len(rows)} отчётов**, физических страниц **{summary['published_pages']}**. Состояния: {dict(counts)}.",
           f'Проверяется сейчас: {active or "—"}. Обновлено UTC: {time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime())}.','',
           'Происхождение: Codex-root и локальный перенос текстового слоя с геометрией PDF. Это не ответы DeepSeek и не одобрение Codex CLI. Символьный состав native-слоя проверен отдельно от семантики; полного визуального или смыслового checked нет.',
           'OCR, нерешённые Unicode, неоднозначные ячейки, пустые неназванные колонки и ссылки отмечены русскими служебными пометками у соответствующих физических страниц. Пустая колонка не объявляется ошибкой без оригинала. Служебные папки _проверка не являются материалом для анализа.',
           'Кандидаты не меняются. PNG связаны hardlink, если файловая система это допускает; файлы report.md самостоятельны. Источник, реализация, кандидат и опубликованный MD имеют отдельные SHA в реестре.','',
           '| Отчёт | Состояние | Страниц | Текст | Ограничения |','|---|---|---:|---|---|']
    for row in rows:
        r=results[row['report_id']];link='—'
        if r['state']=='published':link=f"[report.md](<{row['company_id']}/{row['report_id']}/report.md>)"
        issues=', '.join(f'{key}:{len(r.get(key,[]))}' for key in ['ocr_pages','unicode_pages','ambiguity_pages','unresolved_link_pages','empty_column_pages'] if r.get(key))
        lines.append(f"| {row['report_id']} | {r['state']} ({r.get('code','')}) | {r.get('pages','—')} | {link} | {issues or r.get('message','—')} |")
    lines+=['','При pending нет заглушки report.md. Ошибочный или устаревший кандидат не публикуется; код причины сохранён в реестре. Полное сохранение символов не доказывает верность порядка чтения, формы таблиц, OCR или исходной Unicode-карты.','']
    text='\n'.join(lines);atomic(primary/'README.md',text);atomic(root/'native_corpus_validation.md',text.replace('](<','](<../'+PRIMARY+'/'))

def worker_publish(base,row):
    """One PDF per isolated process; no MuPDF threads and no central writes."""
    before=input_signature(base,row)
    try:
        result,payload=validate_candidate(base,row)
        if payload:publish(base,row,result,payload)
        after=input_signature(base,row)
        prefix=str(base/PRIMARY)
        stable_before=tuple(v for v in before if not str(v[0]).startswith(prefix))
        stable_after=tuple(v for v in after if not str(v[0]).startswith(prefix))
        if stable_before!=stable_after:
            return {'state':'pending','code':'CANDIDATE_CHANGED','message':'Input changed; published previous version is not counted as current','checked':False},before
        return result,after
    except InvalidCandidate as e:
        return {'state':'pending' if e.code=='CANDIDATE_CHANGED' else 'error','code':e.code,'message':str(e),'checked':False},before
    except Exception as e:
        return {'state':'error','code':type(e).__name__,'message':str(e)[:400],'checked':False},before


def run(base,registry,watch=False,interval=20,workers=4):
    with registry.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f,delimiter=';'))
    if len({r['report_id'] for r in rows})!=len(rows):raise ValueError('Duplicate RID')
    primary=base/PRIMARY;(primary/'_проверка').mkdir(parents=True,exist_ok=True)
    lock=(primary/'_проверка/publisher.lock').open('a+')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close();raise SystemExit('Publisher already active')
    cache={};results={r['report_id']:{'state':'pending','code':'AWAITING_CANDIDATE','checked':False} for r in rows}
    atomic(primary/'_проверка/publisher.pid',str(os.getpid())+'\n');write_status(base,rows,results)
    try:
        with futures.ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn')) as pool:
            while True:
                planned=[row for row in rows if cache.get(row['report_id'])!=input_signature(base,row)]
                iterator=iter(planned);active={}
                def fill():
                    while len(active)<workers:
                        row=next(iterator,None)
                        if row is None:break
                        active[pool.submit(worker_publish,base,row)]=row
                fill()
                while active:
                    write_status(base,rows,results,', '.join(r['report_id'] for r in active.values()))
                    done,_=futures.wait(active,timeout=15,return_when=futures.FIRST_COMPLETED)
                    for future in done:
                        row=active.pop(future);rid=row['report_id']
                        try:result,signature=future.result()
                        except Exception as e:
                            result={'state':'error','code':'PUBLISHER_WORKER_FAILED','message':type(e).__name__+': '+str(e)[:300],'checked':False}
                            signature=input_signature(base,row)
                        results[rid]=result;cache[rid]=signature
                        print(time.strftime('%Y-%m-%d %H:%M:%S'),rid,result['state'],result['code'],flush=True)
                    fill()
                    write_status(base,rows,results,', '.join(r['report_id'] for r in active.values()) or None)
                if not watch or all(r['state']=='published' for r in results.values()):return results
                time.sleep(interval)
    finally:lock.close()


def self_test(base):
    """Temporary native fixtures, no model/native helper conversion invocation."""
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);(root/'tools').mkdir();shutil.copy2(base/'tools/native_candidate.py',root/'tools/native_candidate.py')
        (root/'_источники').mkdir();rid='TEST-2025';row={'report_id':rid,'company_id':'TEST'}
        c=root/'_проверка/native_candidates'/rid;(c/'_проверка').mkdir(parents=True);(c/'assets').mkdir()
        doc=fitz.open()
        for _ in range(2):doc.new_page().insert_text((40,60),'Hello 42')
        source=root/'_источники'/f'{rid}.pdf';doc.save(source);doc.close()
        records=[];parts=[];assets={}
        with fitz.open(source) as doc:
            for i,p in enumerate(doc,1):
                glyphs=[ch['c'] for b in p.get_text('rawdict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] for ch in s['chars']]
                records.append({'pdf_page':i,'all_native_glyphs_assigned_once':True,'rendered_native_character_inventory_matches':True,'native_glyphs':len(glyphs),'native_nonspace_glyphs':sum(bool(x.strip()) for x in glyphs),'objects':[{'glyph_count':len(glyphs)}],'issues':[]})
                image=c/'assets'/f'page_{i:04d}.png';p.get_pixmap().save(image);assets[image.name]=sha(image)
                parts.append(f'<!-- pdf_page: {i} -->\n<a id="pdf-page-{i}"></a>\n<p>Hello 42</p>\n<details>\n<summary>Источник: PDF-страница {i}</summary>\n\n![page](assets/{image.name})\n</details>\n')
        records[1].update(ocr_engine='fixture',ocr_verified=False,unresolved_unicode=1,ambiguous_cell_assignments=[{'glyph_id':0}],unresolved_source_links=[{}])
        original='> Служебная информация: механический исходный кандидат fixture.\n\n'+''.join(parts)
        atomic(c/'report.md',original)
        identity={'source_sha256':sha(source),'implementation_sha256':sha(root/'tools/native_candidate.py')}
        coverage={**identity,'report_sha256':sha(c/'report.md'),'pages':2,'all_native_glyphs_assigned_once':True}
        for name,data in [('source_input.json',identity),('native_coverage.json',coverage),('pages.json',{'pages':records}),('native_assets.json',assets)]:atomic(c/'_проверка'/name,json.dumps(data))
        result,payload=validate_candidate(root,row);publish(root,row,result,payload)
        final=(root/PRIMARY/'TEST'/rid/'report.md').read_text()
        assert NOTE.sub('',final[MARKER.search(final).start():])==original[MARKER.search(original).start():]
        assert 'corpus_note_start: 2' in final and 'corpus_note_start: 1' not in final
        assert all(x in final for x in ['OCR','нерасшифрованные','ячейкам','назначения ссылок'])
        assert not result['checked'] and result['native_pass']
        registry=root/'registry.csv'
        with registry.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,['report_id','company_id'],delimiter=';');w.writeheader();w.writerow(row)
        parallel=run(root,registry,workers=2)
        assert parallel[rid]['state']=='published' and parallel[rid]['author_body_unchanged']
        for mutation,expected in [('stale','SOURCE_SHA_MISMATCH'),('page','PAGE_MARKERS'),('asset','MISSING_ASSET')]:
            bad=dict(coverage)
            if mutation=='stale':bad['source_sha256']='stale'
            if mutation=='page':
                atomic(c/'report.md',original.replace('pdf_page: 2','pdf_page: 3'));bad['report_sha256']=sha(c/'report.md')
            if mutation=='asset':(c/'assets/page_0002.png').unlink()
            atomic(c/'_проверка/native_coverage.json',json.dumps(bad))
            try:validate_candidate(root,row);raise AssertionError('Accepted '+mutation)
            except InvalidCandidate as e:assert e.code==expected,(mutation,e.code)
            if mutation=='page':atomic(c/'report.md',original)
        table=BeautifulSoup('<table><tr><td rowspan="2">A</td><td></td><td>B</td></tr><tr><td></td><td>C</td></tr></table>','html.parser').table
        assert empty_columns(table)==[2]
    print('SELF TEST PASS: ready fixture, staleSHA, page gap, missingasset, inline notes, unchangedbody, rowspan emptycolumn',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,default=BASE);p.add_argument('--registry',type=Path,default=REGISTRY)
    p.add_argument('--watch',action='store_true');p.add_argument('--interval',type=float,default=20);p.add_argument('--workers',type=int,default=4);p.add_argument('--self-test',action='store_true')
    a=p.parse_args()
    if a.self_test:self_test(a.base)
    else:
        if not 1<=a.workers<=6:p.error('--workers must be 1..6')
        run(a.base,a.registry,a.watch,a.interval,a.workers)
