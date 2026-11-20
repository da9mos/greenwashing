"""New, resumable PDF-to-MD runs. Old results are never used as model answers."""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as futures
import csv
import hashlib
import html
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
import urllib.parse

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parents[2]
for local_lib in ('/private/tmp/sber-pdf-libs', '/private/tmp/sber-diff-libs'):
    if Path(local_lib).is_dir():
        sys.path.insert(0, local_lib)
import pymupdf as fitz
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup

sys.path.insert(0, str(ROOT / '05_Инструменты/15_DeepSeek_API'))
from deepseek_client import Client

REGISTRY = ROOT / '11_Проект_Сбер/3_итерация/greenwashing/01_итерация_1_сбор_данных/выборка_30/reports.csv'
INSTRUCTION = BASE / '_проверка/Инструкция_на_старте.md'
INSTRUCTION_TEXT = INSTRUCTION.read_text()
INSTRUCTION_SHA = hashlib.sha256(INSTRUCTION_TEXT.encode()).hexdigest()
RUN_VERSION = 'v2'
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
            with fitz.open(source) as source_doc:
                expected_pages = list(range(1, len(source_doc) + 1))
            if [item.get('pdf_page') for item in cached['pages']] != expected_pages:
                raise ValueError('Cached page index does not cover actual PDF exactly once')
            for item in cached['pages']:
                if not (BASE / item['packet']).is_file() or not (BASE / item['image']).is_file() or sha(BASE / item['image']) != item['image_sha256']:
                    raise ValueError('Cached packet/image missing or changed')
                packet_sha = sha(BASE / item['packet'])
                if item.get('packet_sha256') and packet_sha != item['packet_sha256']:
                    raise ValueError('Cached packet changed')
                item['packet_sha256'] = packet_sha
            put_json(index, cached)
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
                elif isinstance(link.get('page'), int) and link['page'] >= 0:
                    item['target'] = f"#pdf-page-{link['page'] + 1}"
                elif link.get('nameddest'):
                    item['named_destination'] = link['nameddest']
                else:
                    item['unresolved'] = True
                    if 'page' in link:
                        item['unresolved_target_page'] = link['page']
                links.append(item)
            packet = {'pdf_page': page_no, 'width': page.rect.width, 'height': page.rect.height,
                      'text_blocks': text_blocks, 'links': links,
                      'image': str(image.relative_to(BASE)), 'image_sha256': sha(image)}
            put_json(packet_dir / f'page_{page_no:04d}.json', packet)
            pages.append({'pdf_page': page_no, 'text_chars': len(text),
                          'packet': str((packet_dir / f'page_{page_no:04d}.json').relative_to(BASE)),
                          'packet_sha256': sha(packet_dir / f'page_{page_no:04d}.json'),
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
    if re.search(r'!\[[^\]]*\]\((?!https?://)[^)]+\)|<img\b', md, re.I):
        issues.append('prohibited_model_asset_link')
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


def validate_bundle(folder, index):
    """Structural gate only. Never declares source fidelity or checked."""
    errors = []
    path = folder / 'report.md'
    if not path.is_file():
        return {'assembled': False, 'errors': ['missing_report'], 'markers': []}
    text = path.read_text()
    markers = [int(x) for x in re.findall(r'<!--\s*pdf_page:\s*(\d+)\s*-->', text)]
    if markers != list(range(1, len(index['pages']) + 1)):
        errors.append('page_markers_missing_duplicated_or_out_of_order')
    anchors = set(re.findall(r'\bid=[\"\']([^\"\']+)', text))
    targets = []
    def collect(tokens):
        for token in tokens:
            if token.type == 'image':
                targets.append(token.attrGet('src'))
            elif token.type == 'link_open':
                targets.append(token.attrGet('href'))
            elif token.type in ('html_block', 'html_inline'):
                soup = BeautifulSoup(token.content, 'html.parser')
                for tag in soup.find_all(True):
                    for attr in ('src', 'href'):
                        if tag.get(attr):
                            targets.append(tag[attr])
            if token.children:
                collect(token.children)
    collect(MarkdownIt('commonmark', {'html': True}).parse(text))
    for value in targets:
        target = urllib.parse.unquote(value.strip().strip('<>'))
        if target.startswith(('https://', 'http://', 'mailto:', 'tel:')):
            continue
        if target.startswith('#'):
            if len(target) == 1 or target[1:] not in anchors:
                errors.append('unresolved_internal_anchor:' + target)
            continue
        target = target.split('#', 1)[0].split(' "', 1)[0]
        asset = (folder / target).resolve()
        if not target or not asset.is_relative_to(folder.resolve()) or not asset.is_file():
            errors.append('missing_or_unsafe_asset:' + target)
    return {'assembled': not errors, 'errors': errors, 'markers': markers}


def worker_page_states(check_path, total):
    if not check_path.is_file():
        return {'transcription_complete': False, 'pending_pages': list(range(1, total + 1)), 'error': 'missing_worker_page_registry'}
    data = json.loads(check_path.read_text())
    records = data if isinstance(data, list) else data.get('pages', [])
    if isinstance(records, dict):
        records = [dict(value, pdf_page=int(key)) for key, value in records.items()]
    nums = [r.get('pdf_page', r.get('page')) for r in records]
    if nums != list(range(1, total + 1)):
        return {'transcription_complete': False, 'pending_pages': list(range(1, total + 1)), 'error': 'incomplete_worker_page_registry'}
    pending = [n for n, r in zip(nums, records) if r.get('conversion_status') not in ('converted', 'checked') or r.get('issues')]
    return {'transcription_complete': not pending, 'pending_pages': pending}


def deepseek_page(row, item, version=RUN_VERSION, correction=''):
    rid = row['report_id']
    dest = BASE / '_проверка/DeepSeek' / rid / version / f"page_{item['pdf_page']:04d}.json"
    packet = json.loads((BASE / item['packet']).read_text())
    image = BASE / item['image']
    system = INSTRUCTION_TEXT + '''

В этом вызове выполняется только транскрипция одной физической страницы.
Изображение является источником; текстовый слой с координатами и аннотации помогают чтению,
но могут содержать ошибки. Ответы другой модели не предоставляются.
Верни JSON: {"pdf_page": integer, "markdown": string, "issues": [string]}.
Передай всё содержание страницы. Не добавляй общий отчёт, маркеры страницы и сведения об API.
Изображение страницы будет сохранено сборщиком. На этом шаге ты не создаёшь файлы: не вставляй Markdown/HTML-ссылки на локальные изображения или вложения. Подписи и описания графики передавай текстом, а саму графику сохранит сборщик в исходном изображении страницы. Если элемент нельзя надёжно прочитать,
отметь проблему рядом с ним и в issues. Не сокращай длинную таблицу и не угадывай символы.
Внутренние ссылки используй только из предоставленных назначений; внешние URL не выдумывай.
Никаких внешних ограждений ```json. Собственная проверка не означает независимую сверку по PDF.
'''
    client = Client()
    signature = {'correction_sha256': hashlib.sha256(correction.encode()).hexdigest(), 'model': client.config['default_model'], 'base_url': client.config['base_url'], 'thinking': 'disabled', 'instruction_sha256': INSTRUCTION_SHA, 'system_sha256': hashlib.sha256(system.encode()).hexdigest(),
                 'packet_sha256': sha(BASE / item['packet']), 'image_sha256': sha(image), 'max_tokens': 16000, 'json_mode': True}
    request_sha = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    if dest.exists():
        cached = json.loads(dest.read_text())
        if cached.get('request_sha256') == request_sha:
            return cached
        raise ValueError('Cached response belongs to different input/prompt')
    put_json(dest.parent / 'requests' / dest.name, signature)
    content = [{'type': 'text', 'text': json.dumps({k: v for k, v in packet.items() if k not in ('image', 'image_sha256')}, ensure_ascii=False) + '\n' + correction},
               {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(image.read_bytes()).decode(), 'detail': 'original'}}]
    started = time.time()
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
              'request_sha256': request_sha, 'request_signature': signature,
              'seconds': round(time.time() - started, 2), 'automatic_flags': flags,
              'review_status': 'pending' if flags or answer['issues'] else 'converted'}
    put_json(dest, result)
    log('DeepSeek', rid, item['pdf_page'], result['review_status'])
    return result


def assemble_deepseek(row, index):
    folder = report_dir('DeepSeek', row)
    folder.mkdir(parents=True, exist_ok=True)
    prior_meta = BASE / '_проверка/DeepSeek' / row['report_id'] / 'assembled.json'
    if prior_meta.exists() and (folder / 'report.md').exists():
        prior = json.loads(prior_meta.read_text())
        if prior.get('source_corrections') and prior.get('source_sha256') == index['source_sha256'] and prior.get('report_sha256') == sha(folder / 'report.md'):
            # A later model candidate must not overwrite source-verified corrections.
            return validate_bundle(folder, index)['assembled']
    pages = []
    missing = []
    assembly_edits = []
    for item in index['pages']:
        answer_file = BASE / '_проверка/DeepSeek' / row['report_id'] / RUN_VERSION / f"page_{item['pdf_page']:04d}.json"
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
        body = answer['response']['markdown']
        source_packet = json.loads((BASE / item['packet']).read_text())
        source_text = '\n'.join(b['text'] for b in source_packet['text_blocks'])
        marker_pattern = rf'<!--\s*pdf_page:\s*{n}\s*-->'
        anchor_pattern = rf'<a\s+id=[\"\']pdf-page-{n}[\"\']\s*>\s*</a>'
        # Wrapper metadata belongs to the assembler. Never alter a literal source example.
        for kind, pattern in [('duplicate_page_marker', marker_pattern), ('duplicate_page_anchor', anchor_pattern)]:
            count = len(re.findall(pattern, body))
            if count and not re.search(pattern, source_text):
                body = re.sub(pattern, '', body)
                assembly_edits.append({'pdf_page': n, 'kind': kind, 'count': count, 'raw_answer_unchanged': True})
        # The page image is real; model-proposed crops may not exist. Do not pretend
        # that a complete page is a crop. Keep the request as explicit service text.
        def missing_image(match):
            label, target = match.group(1), match.group(2)
            local = urllib.parse.unquote(target.strip().strip('<>'))
            if local.startswith(('https://', 'http://', 'data:')) or (folder / local).is_file():
                return match.group(0)
            if match.group(0) in source_text or local in source_text:
                return match.group(0)
            assembly_edits.append({'pdf_page': n, 'kind': 'unmaterialized_model_image_reference',
                                   'target': local, 'raw_answer_unchanged': True,
                                   'fallback': 'full_original_page_below_not_a_crop'})
            return ('\n\n> Служебная пометка: отдельное изображение «' + html.escape(label) +
                    '» не создавалось. Графический элемент доступен на полном исходном изображении PDF-страницы ниже.\n\n')
        body = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', missing_image, body)
        pages.append(f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n' + body + note +
                     f'\n\n<details>\n<summary>Источник: PDF-страница {n}</summary>\n\n![Исходная PDF-страница {n}](assets/{name})\n\n</details>\n')
    if missing:
        put_json(folder / '_incomplete.json', {'missing_pages': missing, 'total': len(index['pages'])})
        return False
    heading = f"> Служебная информация: рабочая транскрипция {row['report_id']}. Метки компании, года и типа взяты из реестра; название самого документа сохраняется ниже по источнику.\n\n"
    heading += '> Служебная информация: новая транскрипция DeepSeek по исходным PDF-страницам. Полная независимая сверка всего текста не завершена; модельный результат не имеет статуса checked.\n\n'
    (folder / 'report.md').write_text(heading + '\n'.join(pages))
    (folder / '_incomplete.json').unlink(missing_ok=True)
    gate = validate_bundle(folder, index)
    put_json(BASE / '_проверка/DeepSeek' / row['report_id'] / RUN_VERSION / 'assembly_edits.json', assembly_edits)
    put_json(BASE / '_проверка/DeepSeek' / row['report_id'] / RUN_VERSION / 'bundle_check.json', gate)
    put_json(BASE / '_проверка/DeepSeek' / row['report_id'] / 'assembled.json', {
        'source_sha256': index['source_sha256'], 'instruction_sha256': INSTRUCTION_SHA,
        'pages': len(pages), 'report_sha256': sha(folder / 'report.md'), 'assembled': gate['assembled'], 'assembly_version': 3,
        'bundle_errors': gate['errors'], 'review_status': 'converted' if gate['assembled'] else 'pending'})
    return gate['assembled']


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
    # A stale file must not conceal a failed fingerprint validation or model call.
    complete = assemble_deepseek(row, index) if not errors else False
    pending_pages = []
    for item in index['pages']:
        f = BASE / '_проверка/DeepSeek' / row['report_id'] / RUN_VERSION / f"page_{item['pdf_page']:04d}.json"
        if not f.exists() or json.loads(f.read_text()).get('review_status') == 'pending':
            pending_pages.append(item['pdf_page'])
    return {'assembled': complete, 'transcription_complete': complete and not pending_pages, 'complete': complete and not pending_pages, 'pending_pages': pending_pages, 'errors': len(errors), 'pages': len(index['pages'])}


def run_codex(row, index):
    """A real Codex agent receives the PDF and uses local tools. No DeepSeek answer is supplied."""
    rid = row['report_id']
    receipt_file = BASE / '_проверка/Codex' / rid / RUN_VERSION / 'receipt.json'
    folder = report_dir('Codex', row)
    work = Path('/private/tmp/sber-codex-transcription') / RUN_VERSION / rid
    work.mkdir(parents=True, exist_ok=True)
    source = (BASE / index['source']).resolve()
    (work / 'AGENT.md').write_text(INSTRUCTION_TEXT)
    put_json(work / 'source.json', {'source_pdf': str(source), 'index': str((BASE / '_проверка/входы' / rid / 'pages.json').resolve()),
                                  'instruction_sha256': INSTRUCTION_SHA, 'pages': len(index['pages'])})
    seed = BASE / '_проверка/native_candidates' / rid
    seed_receipt = seed / '_проверка/native_coverage.json'
    if seed_receipt.is_file() and (seed / 'report.md').is_file() and not (work / 'result/report.md').exists():
        seed_meta = json.loads(seed_receipt.read_text())
        if seed_meta.get('source_sha256') == index['source_sha256'] and seed_meta.get('report_sha256') == sha(seed / 'report.md'):
            shutil.copytree(seed, work / 'result', dirs_exist_ok=True)
    prompt = f'''Прочитай AGENT.md и выполни новую полную конвертацию PDF в Markdown.
Ты отвечаешь только за каталог {work}, другие агенты работают параллельно; чужие файлы не меняй.
Исходный PDF: {source}
Всего физических страниц: {len(index['pages'])}. Реестр исходных изображений и текстовых блоков: {BASE / '_проверка/входы' / rid / 'pages.json'}.
Это входы, подготовленные механически из PDF. Ответов DeepSeek и старых транскрипций тебе не передавали: не ищи и не используй их.
Сохрани result/report.md и необходимые result/assets/. Нужен весь документ, а не выдержки или план.
Можно использовать Python и локальные библиотеки из /private/tmp/sber-pdf-libs и /private/tmp/sber-diff-libs.
Для локальной проверки отображения есть готовая команда: python3 "{BASE / 'tools/render_bundle.py'}" --input result/report.md --output result/_проверка/render. Она использует установленный Chrome без сетевых запросов, сохраняет HTML, снимки шириной 1440/390 и протокол; просмотри снимки и нужные таблицы, не выдавай это за полную сверку PDF.
Для механического переноса есть проверенная общая программа {BASE / 'tools/native_candidate.py'}.
Она копирует исходные глифы и геометрию таблиц без переписывания чисел моделью, сохраняет надстрочные знаки по PDF и ведёт учёт символов. Если result уже содержит механический кандидат с native_coverage.json, используй его как начало; это не ответ другой модели. Если готового кандидата нет, сначала запусти эту программу с --source из source.json, --output result и --image-source равным родительскому каталогу index. Не изобретай заново конвертер для этого отчёта.
Затем проверь все диагностические записи и исходные изображения сложных участков: обложку, ошибки Unicode, OCR, пустые/слившиеся колонки, неоднозначные ячейки и порядок чтения. Учёт всех символов не подтверждает их порядок и связи. Ошибки исправляй по оригиналу и документируй; непросмотренное не помечай checked. Механический кандидат находится также в {seed} (если каталог уже полностью собран).
Допустимо извлечение с помощью pymupdf4llm, но проверь охват, таблицы, колонки и неоднозначные участки по PDF/изображениям.
Полные исходные изображения из реестра можно скопировать в assets как визуальную опору; они не заменяют текстовую транскрипцию.
Работай по страницам, сохраняя прогресс. На сканах и смешанных страницах обязательно обработай текст тела доступным OCR/визуальным чтением; одна картинка вместо непрочитанного текста не означает завершённую транскрипцию. Не создавай ссылок на несуществующие файлы. Не запускай новые модели, API или дочерние Codex. Не скачивай ничего.
Не утверждай полную сверку по оригиналу, если реально её не выполнил. Все непросмотренные страницы оставь converted/pending.
В result/_проверка/pages.json перечисли ВСЕ страницы и раздельно их conversion_status, review_status, issues.
В конце кратко укажи обработанные страницы и ограничения. Не останавливайся на плане: создай файлы.
'''
    prompt_sha = hashlib.sha256(prompt.encode()).hexdigest()
    if receipt_file.exists():
        old = json.loads(receipt_file.read_text())
        if old.get('assembled') and old.get('instruction_sha256') == INSTRUCTION_SHA and old.get('source_sha256') == index['source_sha256'] and old.get('prompt_sha256') == prompt_sha and (folder / 'report.md').exists() and old.get('report_sha256') == sha(folder / 'report.md'):
            gate = validate_bundle(folder, index)
            if gate['assembled']:
                return old
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
    gate = validate_bundle(folder, index)
    states = worker_page_states(receipt_file.parent / 'worker_checks/pages.json', len(index['pages']))
    assembled = returncode == 0 and gate['assembled']
    complete = assembled and states['transcription_complete']
    result = {'engine': 'Codex CLI (configured default; exact model must be read from runtime evidence if available)',
              'cli_version': subprocess.run(['codex', '--version'], capture_output=True, text=True).stdout.strip(),
              'instruction_sha256': INSTRUCTION_SHA, 'source_sha256': index['source_sha256'],
              'prompt_sha256': prompt_sha, 'returncode': returncode, 'complete': complete,
              'assembled': assembled, 'transcription_complete': states['transcription_complete'],
              'pending_pages': states['pending_pages'], 'bundle_errors': gate['errors'], 'pages_expected': len(index['pages']),
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
    if args.reports:
        unknown = set(args.reports) - {r['report_id'] for r in ROWS}
        if unknown:
            parser.error('Unknown report IDs: ' + ', '.join(sorted(unknown)))
    rows = [r for r in ROWS if not args.reports or r['report_id'] in args.reports]
    if args.engine in ('DeepSeek', 'both'):
        from deepseek_validation import guard_provider
        guard_provider(BASE)
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
                    if data.get('finished_at') or data.get('complete') or data.get('counts', {}).get('pending') == 0:
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
    counts = {}
    for engine in ('DeepSeek', 'Codex'):
        entries = [v.get(engine, {}) for v in state.values()]
        counts[engine] = {'assembled': sum(bool(e.get('assembled')) for e in entries), 'transcription_complete': sum(bool(e.get('transcription_complete')) for e in entries), 'failed_or_pending': sum(not e.get('complete', False) for e in entries)}
    overall_complete = not pending and len(state) == len(rows) and all(v.get(e, {}).get('complete') for v in state.values() for e in ('DeepSeek', 'Codex') if args.engine in ('both', e))
    put_json(BASE / '_проверка/run_summary.json', {'overall_complete': overall_complete, 'counts': counts, 'instruction_sha256': INSTRUCTION_SHA,
             'reports_requested': len(rows), 'reports': state, 'missing_sources': [r['report_id'] for r in pending]})
    log('RUN ENDED', len(state), 'reports attempted, missing sources:', len(pending), 'overall_complete:', overall_complete)
    if not overall_complete:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
