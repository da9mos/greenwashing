"""Independent DeepSeek pass with source geometry and overlapping zoom views."""
import base64
import hashlib
import json
import time
import run_models as runner
from compare_results import compare_decimals_to_spans
from deepseek_validation import guard_provider, decode_answer, validate_answer

VERSION = 'v3'
ADAPTER = '''
Сейчас транскрибируй только заданную физическую страницу в JSON {"pdf_page":integer,"markdown":string,"issues":[string]}.
К исходному изображению приложены его увеличенные области и числовые строки исходного PDF с размером шрифта, flags и координатами. Это не ответы другой модели.
При отделении сносок используй изображение и исходные spans совместно: не делай обычную последнюю цифру числа надстрочной; не присоединяй реальный надстрочный знак к числу. Не заменяй точное значение догадкой. Все ряды и столбцы сохраняй на своих местах.
Файлы изображений добавит сборщик, не создавай ссылки на несуществующие файлы. Не добавляй служебные маркеры страницы.
В issues только конкретные нерешённые места чтения, а не описания успешно сохранённой вёрстки или картинок.
Внутренние переходы допустимы только по исходным назначениям; внешние URL не выдумывай.
'''


def transcribe(row, item, version=VERSION, correction=''):
    guard_provider(runner.BASE)
    rid = row['report_id']
    n = item['pdf_page']
    dest = runner.BASE / '_проверка/DeepSeek' / rid / version / f'page_{n:04d}.json'
    packet = json.loads((runner.BASE / item['packet']).read_text())
    prepared_file = runner.BASE / '_проверка/геометрия' / rid / f'page_{n:04d}_metadata.json'
    if not prepared_file.is_file():
        raise ValueError('Geometry must be prepared in an isolated process before API calls')
    prepared = json.loads(prepared_file.read_text())
    geometry = prepared['geometry']
    images = [runner.BASE / p for p in prepared['images']]
    text = json.dumps({'page': packet, 'source_geometry': geometry}, ensure_ascii=False) + '\n' + correction
    system = runner.INSTRUCTION_TEXT + ADAPTER
    client = runner.Client()
    signature = {'instruction_sha256': runner.INSTRUCTION_SHA,
                 'system_sha256': hashlib.sha256(system.encode()).hexdigest(),
                 'packet_sha256': runner.sha(runner.BASE / item['packet']),
                 'rich_text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                 'image_sha256': runner.sha(runner.BASE / item['image']),
                 'provided_image_sha256': [runner.sha(p) for p in images],
                 'model': client.config['default_model'], 'base_url': client.config['base_url'],
                 'max_tokens': 18000, 'json_mode': True, 'thinking': 'disabled'}
    request_sha = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    if dest.exists():
        cached = json.loads(dest.read_text())
        if cached.get('request_sha256') == request_sha:
            validate_answer(cached.get('response'), n)
            return cached
        raise ValueError('Different source or prompt at cached response path')
    content = [{'type': 'text', 'text': text}]
    content += [{'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(p.read_bytes()).decode(), 'detail': 'original'}} for p in images]
    runner.put_json(dest.parent / 'requests' / dest.name, signature)
    client.config['timeout_seconds'] = 300
    started = time.time()
    response = client.complete([{'role': 'system', 'content': system}, {'role': 'user', 'content': content}], max_tokens=18000, json_mode=True)
    runner.put_json(dest.parent / 'raw' / dest.name, response)
    choice = response['choices'][0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('Truncated or non-stop model response')
    answer = validate_answer(decode_answer(choice['message']['content']), n)
    if not answer['markdown'].strip() and item['text_chars'] > 20:
        raise ValueError('Empty transcription for a text-bearing page')
    flags = [f for f in runner.local_flags(answer['markdown'], packet)
             if not isinstance(f, dict) or 'decimal_tokens_missing_vs_text_layer' not in f]
    numeric = compare_decimals_to_spans(answer['markdown'], prepared['decimal_reference'])
    if numeric['pdf_only'] or numeric['markdown_only']:
        flags.append({'decimal_span_difference': {'pdf_only': numeric['pdf_only'], 'markdown_only': numeric['markdown_only']}})
    result = {'instruction_sha256': runner.INSTRUCTION_SHA, 'source_image_sha256': item['image_sha256'],
              'request_sha256': request_sha, 'request_signature': signature, 'response': answer,
              'model': response.get('model'), 'usage': response.get('usage'), 'seconds': round(time.time() - started, 2),
              'automatic_flags': flags, 'decimal_span_check': numeric,
              'review_status': 'pending' if flags or answer['issues'] else 'converted'}
    runner.put_json(dest, result)
    runner.log('DeepSeek', VERSION, rid, n, result['review_status'])
    return result


if __name__ == '__main__':
    runner.RUN_VERSION = VERSION
    runner.deepseek_page = transcribe
    runner.main()
