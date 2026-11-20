"""Regenerate root СТАТУС.md from local receipts; never changes run outputs.

Public entry point for runner hooks: update_status(base=BASE, registry=REGISTRY).
A document's checked state cannot be authorized by this script.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import quote

BASE=Path(__file__).resolve().parents[1]
REGISTRY=BASE.parents[2]/'11_Проект_Сбер/3_итерация/greenwashing/01_итерация_1_сбор_данных/выборка_30/reports.csv'
def safe_version(value):
    return value if isinstance(value,str) and re.fullmatch(r'v[0-9]+',value) else 'unknown'


def hash_file(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def load_json(path,errors):
    if not path.is_file():return {}
    try:return json.loads(path.read_text())
    except (ValueError,OSError) as e:
        errors.append(path.name+': '+type(e).__name__);return {}


def existing_link(base,path,label):
    if not path.is_file():return '—'
    return '['+label+']('+quote(path.relative_to(base).as_posix(),safe='/')+')'


def update_status(base=BASE,registry=REGISTRY):
    base=Path(base);registry=Path(registry);errors=[]
    with registry.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f,delimiter=';'))
    if len({r['report_id'] for r in rows})!=len(rows):raise ValueError('Duplicate registry RID')
    manifest=load_json(base/'_проверка/sources_manifest.json',errors)
    sources={r['report_id']:r for r in manifest.get('reports',[])}
    ledger=base/'_проверка/sources.csv'
    if ledger.exists():
        with ledger.open(encoding='utf-8-sig') as f:
            for r in csv.DictReader(f,delimiter=';'):sources.setdefault(r['report_id'],r)
    instruction=base/'_проверка/Инструкция_на_старте.md'
    instruction_sha=hashlib.sha256(instruction.read_text().encode()).hexdigest() if instruction.exists() else None
    job=load_json(base/'_проверка/job.json',errors)
    codex_controller=load_json(base/'_проверка/codex_controller.json',errors)
    versions={'DeepSeek':safe_version(job.get('DeepSeek_version',job.get('version'))),
              'Codex':safe_version(job.get('Codex_version',codex_controller.get('version')))}
    comparison_details=load_json(base/'_проверка/comparison_details.json',errors)
    comparison_details={r['report_id']:r for r in comparison_details} if isinstance(comparison_details,list) else {}
    comparison_summary=load_json(base/'_проверка/comparison_summary.json',errors)
    comparison={};comparison_path=base/'_проверка/comparison.csv'
    if comparison_path.exists():
        with comparison_path.open(encoding='utf-8-sig') as f:comparison={r['report_id']:r for r in csv.DictReader(f,delimiter=';')}
    results=[]
    for row in rows:
        rid=row['report_id'];cid=row.get('company_id') or rid.split('-')[0]
        source=sources.get(rid,{});pdf=base/'_источники'/f'{rid}.pdf'
        state='готов (manifest)' if source.get('state')=='ready' and pdf.is_file() else ('ошибка' if source.get('state')=='failed' else 'pending')
        if not pdf.is_file() and source.get('state')=='ready':state='ошибка: файл отсутствует'
        packet=load_json(base/'_проверка/входы'/rid/'pages.json',errors)
        n=source.get('pages') or len(packet.get('pages',[])) or 0
        try:n=int(n)
        except (TypeError,ValueError):n=0
        image_hashes={p.get('pdf_page'):p.get('image_sha256') for p in packet.get('pages',[])}
        saved=0;usable=0;pending_pages=0
        for path in sorted((base/'_проверка/DeepSeek'/rid/versions['DeepSeek']).glob('page_*.json')):
            if not re.fullmatch(r'page_\d{4}\.json',path.name):continue
            saved+=1;d=load_json(path,errors);response=d.get('response',{})
            page=response.get('pdf_page');expected=int(path.stem.split('_')[1])
            valid=(type(page) is int and page==expected and n>0 and 1<=page<=n and
                   isinstance(response.get('markdown'),str) and isinstance(response.get('issues'),list) and
                   instruction_sha is not None and d.get('instruction_sha256')==instruction_sha and
                   page in image_hashes and d.get('source_image_sha256')==image_hashes[page])
            if valid and d.get('request_signature') is not None:
                signature=d['request_signature']
                packet_path=base/'_проверка/входы'/rid/f'page_{expected:04d}.json'
                valid=(isinstance(signature,dict) and
                       d.get('request_sha256')==hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest() and
                       signature.get('instruction_sha256')==instruction_sha and
                       signature.get('image_sha256')==image_hashes[page] and
                       packet_path.is_file() and signature.get('packet_sha256')==hash_file(packet_path))
            elif valid:
                valid=False  # Active runs require an adapter request fingerprint.
            if valid:
                usable+=1
                if d.get('review_status')!='converted' or response.get('issues') or d.get('automatic_flags'):pending_pages+=1
        model={}
        for engine in ('DeepSeek','Codex'):
            md=base/engine/cid/rid/'report.md';exists=md.is_file()
            if engine=='DeepSeek':
                receipt=load_json(base/'_проверка/DeepSeek'/rid/'assembled.json',errors)
                gate=load_json(base/'_проверка/DeepSeek'/rid/versions['DeepSeek']/'bundle_check.json',errors)
            else:
                receipt=load_json(base/'_проверка/Codex'/rid/versions['Codex']/'receipt.json',errors);gate=receipt
            matching=(exists and receipt.get('instruction_sha256')==instruction_sha and
                      receipt.get('source_sha256')==source.get('sha256') and
                      receipt.get('report_sha256')==hash_file(md))
            assembled=bool(matching and receipt.get('assembled') is True and gate.get('assembled') is True)
            if engine=='DeepSeek' and (usable!=n or not n):assembled=False
            if engine=='Codex' and (receipt.get('identity_valid') is False or receipt.get('prompt_identity_valid') is False):assembled=False
            complete=bool(assembled and ((usable==n and n>0 and pending_pages==0) if engine=='DeepSeek' else receipt.get('transcription_complete') is True))
            model[engine]={'md':existing_link(base,md,'report.md'),'exists':exists,'assembled':assembled,'transcription_complete':complete}
        c=comparison.get(rid,{})
        cd=comparison_details.get(rid,{})
        comparison_current=bool(comparison_summary and cd and any(cd.get(e,{}).get('report_sha256') for e in ('DeepSeek','Codex')))
        for engine in ('DeepSeek','Codex'):
            old_hash=cd.get(engine,{}).get('report_sha256')
            md=base/engine/cid/rid/'report.md'
            if old_hash and (not md.exists() or hash_file(md)!=old_hash):comparison_current=False
            if md.exists() and not old_hash:comparison_current=False
        try:paired=int(c.get('pair_pages_compared') or 0) if comparison_current else 0
        except (TypeError,ValueError):paired=0
        results.append({'rid':rid,'source':state,'source_link':existing_link(base,pdf,state) if pdf.exists() else state,
                        'pages':n,'saved_active':saved,'usable_active':usable,'pending_pages':pending_pages,'model':model,'paired':paired,'comparison_current':comparison_current,
                        'codex_controller_state':codex_controller.get('reports',{}).get(rid,{}).get('state','pending')})
    states=Counter('готов' if r['source'].startswith('готов') else ('ошибка' if r['source'].startswith('ошибка') else 'pending') for r in results)
    totals={'reports':len(rows),'companies':len({r.get('company_id') or r['report_id'].split('-')[0] for r in rows}),
            'sources':dict(states),'physical_pages_manifest':sum(r['pages'] for r in results),
            'versions':versions,'DeepSeek_responses_saved':sum(r['saved_active'] for r in results),'DeepSeek_responses_matching_inputs':sum(r['usable_active'] for r in results),
            'md_files':{e:sum(r['model'][e]['exists'] for r in results) for e in ('DeepSeek','Codex')},
            'assembled':{e:sum(r['model'][e]['assembled'] for r in results) for e in ('DeepSeek','Codex')},
            'transcription_complete':{e:sum(r['model'][e]['transcription_complete'] for r in results) for e in ('DeepSeek','Codex')},
            'paired_pages_snapshot':sum(r['paired'] for r in results),'comparison_current_reports':sum(r['comparison_current'] for r in results),'checked_confirmed':0,'read_errors':errors}
    timestamp=datetime.now(timezone.utc).isoformat(timespec='seconds')
    lines=['# Живой статус перевода PDF в Markdown','',f'Снимок файлов: **{timestamp}** (UTC). Реестр: **{totals["reports"]} отчёта / {totals["companies"]} компаний**.','',
           f'Исходники по manifest: готово {states["готов"]}, ошибки {states["ошибка"]}, pending {states["pending"]}. Учтено физических страниц: **{totals["physical_pages_manifest"]}**.',
           f'DeepSeek **{versions["DeepSeek"]}**: сохранено ответов **{totals["DeepSeek_responses_saved"]}**, из них совпадают по странице/инструкции/изображению и fingerprint запроса **{totals["DeepSeek_responses_matching_inputs"]}**. Это не число проверенных страниц.',
           f'Файлы report.md: DeepSeek **{totals["md_files"]["DeepSeek"]}**, Codex **{totals["md_files"]["Codex"]}**. Assembled: DeepSeek **{totals["assembled"]["DeepSeek"]}**, Codex **{totals["assembled"]["Codex"]}**. Transcription_complete: DeepSeek **{totals["transcription_complete"]["DeepSeek"]}**, Codex **{totals["transcription_complete"]["Codex"]}**.',
           f'Парных страниц в последнем сравнении: **{totals["paired_pages_snapshot"]}**. Полная независимая сверка **не подтверждена**; checked этим инструментом не присваивается.','',
           f'Активные версии: **DeepSeek {versions["DeepSeek"]} / Codex {versions["Codex"]}**. DeepSeek job: pid=`{job.get("pid","—")}`, status=`{job.get("status","не указано")}`. Codex controller: pid=`{codex_controller.get("pid","—")}`, status=`{codex_controller.get("overall_status","не указано")}`. Это метаданные; существование процессов отдельно не проверялось.',
           f'Замороженная инструкция: SHA-256 `{instruction_sha or "отсутствует"}`.',
           f'Сравнение обновлено: `{comparison_summary.get("generated_at","ещё не выполнялось")}`. Ранний снимок по двум черновикам DeepSeek v2 не считается сравнением активной пары; совпадение MD-хэшей проверяется отдельно. '+existing_link(base,base/'_проверка/comparison.md','Открыть сравнение')+'.','',
           '## Все отчёты','',
           'Число PDF-страниц берётся из manifest (при отсутствии — из полного входного pages.json). В графе ответов: подходящие входам / сохранённые / ожидаемые. MD-ссылка появляется только при существующем файле. D/C означает DeepSeek/Codex.','',
           f'| RID | Исходник | PDF стр. | Ответы DeepSeek {versions["DeepSeek"]} | DeepSeek MD | Codex MD | Codex этап | Assembled D/C | Transcription complete D/C | Парных активных стр. | Полная сверка |',
           '|---|---|---:|---:|---|---|---|---|---|---:|---|']
    yes=lambda value:'да' if value else '—'
    for r in results:
        m=r['model'];lines.append(f'| {r["rid"]} | {r["source_link"]} | {r["pages"] or "—"} | {r["usable_active"]}/{r["saved_active"]}/{r["pages"] or "?"} | {m["DeepSeek"]["md"]} | {m["Codex"]["md"]} | {r["codex_controller_state"]} | {yes(m["DeepSeek"]["assembled"])}/{yes(m["Codex"]["assembled"])} | {yes(m["DeepSeek"]["transcription_complete"])}/{yes(m["Codex"]["transcription_complete"])} | {r["paired"]} | не подтверждена |')
    lines+=['','## Значение статусов','',
            '- **MD существует**: файл есть; полнота и корректность этим не подтверждаются',
            '- **assembled**: есть соответствующий текущим входам протокол структурной сборки; это не визуальная сверка с PDF',
            '- **transcription_complete**: текущие протоколы не оставляют незавершённых страниц транскрипции; это всё ещё не независимый checked',
            '- **checked**: требует полной сверки заявленного объёма с оригиналом; скрипт не повышает статус автоматически',
            '- **pending**: нет исходника, ответа, комплекта или достаточного подтверждения этапа; файл не подменяется пустой заглушкой','',
            'Обновить статус: `python3 tools/update_status.py`. Обновить сравнение: `python3 tools/compare_results.py`.',
            'Продолжить DeepSeek: `python3 tools/run_deepseek_v3.py --engine DeepSeek --workers 16`. Продолжить Codex: `python3 tools/run_codex_independent.py --workers 2`. Не запускайте второй экземпляр поверх соответствующего работающего контроллера.','']
    archived=sorted((base/'DeepSeek_v2_черновик').glob('*/*/report.md'))
    lines+=['## Ранние черновики и пилот','',
            'V1 остановлен из-за ссылки на отсутствующий asset. В v2 на PDF-странице57 социального отчёта подтверждены три изменения чисел; два ранних MD перенесены в DeepSeek_v2_черновик, raw v1/v2 сохранены. Эти файлы не входят в активные счётчики. Исправленный пилот с геометрией и увеличенными областями подтвердил числа одной страницы, а не качество всего корпуса.','']
    lines.extend('- '+existing_link(base,path,path.parent.name+' — архивный черновик v2') for path in archived)
    lines+=['',existing_link(base,base/'_проверка/pilot_geometry/answer.json','Ответ пилота')+' · '+
            existing_link(base,base/'_проверка/pilot_geometry/input.json','Входы и хэши пилота')+' · '+
            existing_link(base,base/'_проверка/pilot_geometry/raw.json','Raw пилота'),'']
    if errors:lines+=['Ошибки чтения метаданных этого снимка: '+', '.join(errors),'']
    path=base/'СТАТУС.md';temp=path.with_name(path.name+f'.{os.getpid()}.part');temp.write_text('\n'.join(lines));temp.replace(path)
    return totals


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,default=BASE);p.add_argument('--registry',type=Path,default=REGISTRY)
    a=p.parse_args();print(json.dumps(update_status(a.base,a.registry),ensure_ascii=False,indent=2))
