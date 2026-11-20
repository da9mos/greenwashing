"""New, resumable PDF-to-MD runs. Old results are never used as model answers."""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as futures
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parents[2]
for local_lib in ('/private/tmp/sber-pdf-libs', '/private/tmp/sber-diff-libs'):
    if Path(local_lib).is_dir():
        sys.path.insert(0, local_lib)
import pymupdf as fitz

sys.path.insert(0, str(ROOT / '05_Инструменты/15_DeepSeek_API'))
from deepseek_client import Client

REGISTRY = ROOT / '11_Проект_Сбер/3_итерация/greenwashing/01_итерация_1_сбор_данных/выборка_30/reports.csv'
INSTRUCTION = BASE / '_проверка/Инструкция_на_старте.md'
INSTRUCTION_SHA = hashlib.sha256(INSTRUCTION.read_bytes()).hexdigest()
ROWS = list(csv.DictReader(REGISTRY.open(encoding='utf-8-sig'), delimiter=';'))
LOCK = threading.RLock()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f'.{threading.get_ident()}.part')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def log(*parts):
    with LOCK:
        print(time.strftime('%Y-%m-%d %H:%M:%S'), *parts, flush=True)


def report_dir(engine, row):
    return BASE / engine / row['company_id'] / row['report_id']


def page_inputs(row):
    """Local source packets, independent of either model's answers."""
    rid = row['report_id']
    source = BASE / '_источники' / (rid + '.pdf')
    packet_dir = BASE / '_проверка/входы' / rid
    packet_dir.mkdir(parents=True, exist_ok=True)
    index = packet_dir / 'pages.json'
    source_sha = sha(source)
    if index.exists():
        cached = json.loads(index.read_text())
        if cached['source_sha256'] == source_sha:
            return cached
        raise ValueError('Source changed; create a separate new run')
    pages = []
    with fitz.open(source) as doc:
        for page_no, page in enumerate(doc, 1):
            image = packet_dir / f'page_{page_no:04d}.png'
            # Keep the complete page: an automatic centre split can cut a table.
            scale = min(2.0, 2600 / max(page.rect.width, page.rect.height))
            page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(image)
            blocks = page.get_text('blocks', sort=False)
            text_blocks = [{'bbox': list(b[:4]), 'text': b[4]} for b in blocks if isinstance(b[4], str)]
            text = page.get_text(sort=False)
            links = []
            for link in page.get_links():
                item = {'bbox': list(link['from'])}
                if link.get('uri'):
                    item['uri'] = link['uri']
                elif link.get('page', -1) >= 0:
                    item['target'] = f"#pdf-page-{link['page'] + 1}"
                elif link.get('nameddest'):
                    item['named_destination'] = link['nameddest']
                else:
                    item['unresolved'] = True
                links.append(item)
            packet = {'pdf_page': page_no, 'width': page.rect.width, 'height': page.rect.height,
                      'text_blocks': text_blocks, 'links': links,
                      'image': str(image.relative_to(BASE)), 'image_sha256': sha(image)}
            put_json(packet_dir / f'page_{page_no:04d}.json', packet)
            pages.append({'pdf_page': page_no, 'text_chars': len(text),
                          'packet': str((packet_dir / f'page_{page_no:04d}.json').relative_to(BASE)),
                          'image': packet['image'], 'image_sha256': packet['image_sha256']})
    result = {'report_id': rid, 'source': str(source.relative_to(BASE)), 'source_sha256': source_sha,
              'pages': pages, 'instruction_sha256': INSTRUCTION_SHA}
    put_json(index, result)
    return result


def clone(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha(source) != sha(target):
            raise ValueError('Asset conflict')
        return
    result = subprocess.run(['cp', '-c', str(source), str(target)], capture_output=True)
    if result.returncode:
        shutil.copy2(source, target)


def local_flags(md, packet):
    issues = []
    if re.search(r'\]\(\s*#?\s*\)', md):
        issues.append('link_placeholder')
    if '[НЕРАЗБОРЧИВО]' in md or '[неразборчиво]' in md.lower():
        issues.append('unreadable_content')
    text = '\n'.join(b['text'] for b in packet['text_blocks'])
    if len(text.strip()) > 300 and len(md.strip()) < len(text.strip()) * .35:
        issues.append('possible_content_loss')
    numeric = lambda s: set(re.findall(r'(?<!\w)\d+[,.]\d+(?!\w)', s))
    missing = sorted(numeric(text) - numeric(md))
    if missing:
        issues.append({'decimal_tokens_missing_vs_text_layer': missing})
    return issues


def deepseek_page(row, item, version='v1', correction=''):
    rid = row['report_id']
    dest = BASE / '_проверка/DeepSeek' / rid / version / f"page_{item['pdf_page']:04d}.json"
    if dest.exists():
        result = json.loads(dest.read_text())
        if result['instruction_sha256'] != INSTRUCTION_SHA:
            raise ValueError('Cannot reuse answers from a different instruction')
        return result
    packet = json.loads((BASE / item['packet']).read_text())
    image = BASE / item['image']
    system = INSTRUCTION.read_text() + '''

В этом вызове выполняется только транскрипция одной физической страницы.
Изображение является источником; текстовый слой с координатами и аннотации помогают чтению,
но могут содержать ошибки. Ответы другой модели не предоставляются.
Верни JSON: {"pdf_page": integer, "markdown": string, "issues": [string]}.
Передай всё содержание страницы. Не добавляй общий отчёт, маркеры страницы и сведения об API.
Изображение страницы уже будет сохранено сборщиком. Если элемент нельзя надёжно прочитать,
отметь проблему рядом с ним и в issues. Не сокращай длинную таблицу и не угадывай символы.
Внутренние ссылки используй только из предоставленных назначений; внешние URL не выдумывай.
Никаких внешних ограждений ```json. Собственная проверка не означает независимую сверку по PDF.
'''
    content = [{'type': 'text', 'text': json.dumps({k: v for k, v in packet.items() if k not in ('image', 'image_sha256')}, ensure_ascii=False) + '\n' + correction},
               {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(image.read_bytes()).decode(), 'detail': 'original'}}]
    started = time.time()
    client = Client()
    client.config['timeout_seconds'] = 300
    response = client.complete([{'role': 'system', 'content': system}, {'role': 'user', 'content': content}], max_tokens=16000, json_mode=True)
    raw_dir = dest.parent / 'raw'
    put_json(raw_dir / dest.name, response)
    choice = response['choices'][0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('Incomplete model response: ' + str(choice.get('finish_reason')))
    answer = json.loads(choice['message']['content'])
    if answer.get('pdf_page') != item['pdf_page'] or not isinstance(answer.get('markdown'), str) or not isinstance(answer.get('issues'), list):
        raise ValueError('Response schema/page mismatch')
    if not answer['markdown'].strip() and item['text_chars'] > 20:
        raise ValueError('Empty response for a nonempty page')
    flags = local_flags(answer['markdown'], packet)
    result = {'instruction_sha256': INSTRUCTION_SHA, 'source_image_sha256': item['image_sha256'],
              'response': answer, 'model': response.get('model'), 'usage': response.get('usage'),
              'seconds': round(time.time() - started, 2), 'automatic_flags': flags,
              'review_status': 'pending' if flags or answer['issues'] else 'converted'}
    put_json(dest, result)
    log('DeepSeek', rid, item['pdf_page'], result['review_status'])
    return result


def assemble_deepseek(row, index):
    folder = report_dir('DeepSeek', row)
    folder.mkdir(parents=True, exist_ok=True)
    pages = []
    missing = []
    for item in index['pages']:
        answer_file = BASE / '_проверка/DeepSeek' / row['report_id'] / 'v1' / f"page_{item['pdf_page']:04d}.json"
        if not answer_file.exists():
            missing.append(item['pdf_page'])
            continue
        answer = json.loads(answer_file.read_text())
        if answer['instruction_sha256'] != INSTRUCTION_SHA:
            raise ValueError('Wrong instruction hash')
        n = item['pdf_page']
        name = f'page_{n:04d}.png'
        clone(BASE / item['image'], folder / 'assets' / name)
        issues = answer['response']['issues'] + answer['automatic_flags']
        note = '' if not issues else '\n\n> Служебная пометка: требуется проверка: ' + '; '.join(str(x) for x in issues) + '\n'
        pages.append(f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n' + answer['response']['markdown'] + note +
                     f'\n\n<details>\n<summary>Источник: PDF-страница {n}</summary>\n\n![Исходная PDF-страница {n}](assets/{name})\n\n</details>\n')
    if missing:
        put_json(folder / '_incomplete.json', {'missing_pages': missing, 'total': len(index['pages'])})
        return False
    heading = f"# {row['company']} · {row['year']} · {row['report_type']}\n\n"
    heading += '> Служебная информация: новая транскрипция DeepSeek по исходным PDF-страницам. Полная независимая сверка всего текста не завершена; модельный результат не имеет статуса checked.\n\n'
    (folder / 'report.md').write_text(heading + '\n'.join(pages))
    (folder / '_incomplete.json').unlink(missing_ok=True)
    put_json(BASE / '_проверка/DeepSeek' / row['report_id'] / 'assembled.json', {
        'source_sha256': index['source_sha256'], 'instruction_sha256': INSTRUCTION_SHA,
        'pages': len(pages), 'report_sha256': sha(folder / 'report.md'), 'review_status': 'converted'})
    return True


def run_deepseek(row, index, executor):
    jobs = {executor.submit(deepseek_page, row, item): item for item in index['pages']}
    errors = []
    for job in futures.as_completed(jobs):
        item = jobs[job]
        try:
            job.result()
        except Exception as exc:
            error = {'report_id': row['report_id'], 'page': item['pdf_page'], 'type': type(exc).__name__, 'error': str(exc)[:1000]}
            put_json(BASE / '_проверка/DeepSeek' / row['report_id'] / 'errors' / f"page_{item['pdf_page']:04d}.json", error)
            errors.append(error)
            log('DeepSeek ERROR', row['report_id'], item['pdf_page'], type(exc).__name__)
    complete = assemble_deepseek(row, index)
    return {'complete': complete, 'errors': len(errors), 'pages': len(index['pages'])}


def run_codex(row, index):
    """A real Codex agent receives the PDF and uses local tools. No DeepSeek answer is supplied."""
    rid = row['report_id']
    receipt_file = BASE / '_проверка/Codex' / rid / 'receipt.json'
    folder = report_dir('Codex', row)
    if receipt_file.exists():
        old = json.loads(receipt_file.read_text())
        if old.get('complete') and old.get('instruction_sha256') == INSTRUCTION_SHA and (folder / 'report.md').exists():
            return old
    work = Path('/private/tmp/sber-codex-transcription') / rid
    work.mkdir(parents=True, exist_ok=True)
    source = (BASE / index['source']).resolve()
    (work / 'AGENT.md').write_bytes(INSTRUCTION.read_bytes())
    put_json(work / 'source.json', {'source_pdf': str(source), 'index': str((BASE / '_проверка/входы' / rid / 'pages.json').resolve()),
                                  'instruction_sha256': INSTRUCTION_SHA, 'pages': len(index['pages'])})
    prompt = f'''Прочитай AGENT.md и выполни новую полную конвертацию PDF в Markdown.
Ты отвечаешь только за каталог {work}, другие агенты работают параллельно; чужие файлы не меняй.
Исходный PDF: {source}
Всего физических страниц: {len(index['pages'])}. Реестр исходных изображений и текстовых блоков: {BASE / '_проверка/входы' / rid / 'pages.json'}.
Это входы, подготовленные механически из PDF. Ответов DeepSeek и старых транскрипций тебе не передавали: не ищи и не используй их.
Сохрани result/report.md и необходимые result/assets/. Нужен весь документ, а не выдержки или план.
Можно использовать Python и локальные библиотеки из /private/tmp/sber-pdf-libs и /private/tmp/sber-diff-libs.
Допустимо извлечение с помощью pymupdf4llm, но проверь охват, таблицы, колонки и неоднозначные участки по PDF/изображениям.
Полные исходные изображения из реестра можно скопировать в assets как визуальную опору; они не заменяют текстовую транскрипцию.
Работай по страницам, сохраняя прогресс. Не запускай новые модели, API или дочерние Codex. Не скачивай ничего.
Не утверждай полную сверку по оригиналу, если реально её не выполнил. Все непросмотренные страницы оставь converted/pending.
В result/_проверка/pages.json перечисли ВСЕ страницы и раздельно их conversion_status, review_status, issues.
В конце кратко укажи обработанные страницы и ограничения. Не останавливайся на плане: создай файлы.
'''
    receipt_file.parent.mkdir(parents=True, exist_ok=True)
    (receipt_file.parent / 'prompt.txt').write_text(prompt)
    command = ['codex', 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check', '--sandbox', 'workspace-write',
               '--cd', str(work), '--json', '--output-last-message', str(work / 'last_message.txt'), '-']
    with (receipt_file.parent / 'events.jsonl').open('w') as out, (receipt_file.parent / 'stderr.log').open('w') as err:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err, text=True)
        process.stdin.write(prompt)
        process.stdin.close()
        put_json(receipt_file.parent / 'running.json', {'pid': process.pid, 'started_at': time.time(), 'work': str(work)})
        returncode = process.wait()
    result_dir = work / 'result'
    complete = returncode == 0 and (result_dir / 'report.md').exists()
    if complete:
        # Copy only this worker's outputs. Keep its checks outside the analytical input.
        folder.mkdir(parents=True, exist_ok=True)
        for child in result_dir.iterdir():
            if child.name == '_проверка':
                shutil.copytree(child, receipt_file.parent / 'worker_checks', dirs_exist_ok=True)
            elif child.is_dir():
                shutil.copytree(child, folder / child.name, dirs_exist_ok=True)
            else:
                shutil.copy2(child, folder / child.name)
        text = (folder / 'report.md').read_text()
        markers = [int(x) for x in re.findall(r'<!--\s*pdf_page:\s*(\d+)\s*-->', text)]
        complete = markers == list(range(1, len(index['pages']) + 1))
    else:
        markers = []
    result = {'engine': 'Codex CLI (configured default; exact model must be read from runtime evidence if available)',
              'cli_version': subprocess.run(['codex', '--version'], capture_output=True, text=True).stdout.strip(),
              'instruction_sha256': INSTRUCTION_SHA, 'source_sha256': index['source_sha256'],
              'returncode': returncode, 'complete': complete, 'pages_expected': len(index['pages']),
              'page_markers_found': len(markers), 'review_status': 'converted' if complete else 'pending',
              'report_sha256': sha(folder / 'report.md') if (folder / 'report.md').exists() else None}
    put_json(receipt_file, result)
    log('Codex', rid, 'complete' if complete else 'INCOMPLETE')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', choices=['DeepSeek', 'Codex', 'both'], default='both')
    parser.add_argument('--reports', nargs='*')
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    rows = [r for r in ROWS if not args.reports or r['report_id'] in args.reports]
    pending = list(rows)
    state = {}
    started = time.time()
    with futures.ThreadPoolExecutor(max_workers=args.workers) as api_pool, futures.ThreadPoolExecutor(max_workers=2) as codex_pool:
        codex_jobs = {}
        while pending:
            ready = [r for r in pending if (BASE / '_источники' / (r['report_id'] + '.pdf')).exists()]
            if not ready:
                # Source acquisition has its own complete manifest and process.
                manifest = BASE / '_проверка/sources_manifest.json'
                if manifest.exists():
                    data = json.loads(manifest.read_text())
                    if data.get('finished_at') or data.get('complete'):
                        break
                if time.time() - started > 7200:
                    break
                time.sleep(3)
                continue
            for row in ready:
                rid = row['report_id']
                try:
                    index = page_inputs(row)
                    state[rid] = {'pages': len(index['pages'])}
                    put_json(BASE / '_проверка/progress.json', state)
                    if args.engine in ('Codex', 'both'):
                        codex_jobs[codex_pool.submit(run_codex, row, index)] = rid
                    if args.engine in ('DeepSeek', 'both'):
                        state[rid]['DeepSeek'] = run_deepseek(row, index, api_pool)
                    pending.remove(row)
                    put_json(BASE / '_проверка/progress.json', state)
                except Exception as exc:
                    state[rid] = {'error': str(exc)[:1000], 'traceback': traceback.format_exc()}
                    pending.remove(row)
                    put_json(BASE / '_проверка/progress.json', state)
                    log('REPORT ERROR', rid, type(exc).__name__)
        for job in futures.as_completed(codex_jobs):
            rid = codex_jobs[job]
            try:
                state[rid]['Codex'] = job.result()
            except Exception as exc:
                state[rid]['Codex'] = {'error': str(exc)[:1000]}
            put_json(BASE / '_проверка/progress.json', state)
    put_json(BASE / '_проверка/run_summary.json', {'instruction_sha256': INSTRUCTION_SHA,
             'reports_requested': len(rows), 'reports': state, 'missing_sources': [r['report_id'] for r in pending]})
    log('RUN FINISHED', len(state), 'reports, missing sources:', len(pending))


if __name__ == '__main__':
    main()
