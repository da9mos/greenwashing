"""Render complete saved Markdown bundles; this is a layout check, not source QA."""
from pathlib import Path
import hashlib
import json
import sys
import urllib.parse
sys.path.insert(0, '/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
CSS = '''body{font:16px/1.6 Arial,sans-serif;max-width:1180px;margin:auto;padding:20px;overflow-wrap:anywhere}img{max-width:100%;height:auto}pre{white-space:pre-wrap}.scroll{max-width:100%;overflow:auto}table{border-collapse:collapse}td,th{border:1px solid #bbc8d2;padding:8px;min-width:80px}th{background:#edf2f7}details{border:1px solid #ddd;padding:8px;margin:12px 0}a{color:#145a94}'''


def main():
    records = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless=True)
        for engine in ('DeepSeek', 'Codex'):
            for source in sorted((BASE / engine).glob('*/*/report.md')):
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                out = BASE / '_проверка/Просмотр' / engine / source.parent.name
                out.mkdir(parents=True, exist_ok=True)
                receipt = out / 'render_check.json'
                if receipt.exists():
                    old = json.loads(receipt.read_text())
                    if old.get('report_sha256') == digest:
                        records.append(old)
                        continue
                soup = BeautifulSoup(MarkdownIt('commonmark', {'html': True}).enable('table').render(source.read_text()), 'html.parser')
                for el in soup.find_all(['script', 'iframe', 'object', 'embed']):
                    el.decompose()
                for image in soup.find_all('img'):
                    target = (source.parent / urllib.parse.unquote(image.get('src', ''))).resolve()
                    if target.is_file() and target.is_relative_to(source.parent.resolve()):
                        image['src'] = target.as_uri()
                        image['loading'] = 'lazy'
                for table in list(soup.find_all('table')):
                    wrapper = soup.new_tag('div')
                    wrapper['class'] = 'scroll'
                    table.wrap(wrapper)
                html = '<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>' + CSS + '</style>' + str(soup)
                (out / 'report.html').write_text(html)
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                page.route('https://**/*', lambda route: route.abort())
                page.route('http://**/*', lambda route: route.abort())
                page.goto((out / 'report.html').as_uri())
                widths = []
                for width in (1440, 390):
                    page.set_viewport_size({'width': width, 'height': 1000})
                    overflow = page.evaluate('document.documentElement.scrollWidth>innerWidth')
                    page.screenshot(path=str(out / f'width_{width}.png'))
                    widths.append({'width': width, 'document_overflow': overflow})
                record = {'engine': engine, 'report_id': source.parent.name, 'report_sha256': digest,
                          'page_anchors': page.locator('[id^="pdf-page-"]').count(),
                          'tables_rendered': page.locator('table').count(), 'image_references': page.locator('img').count(),
                          'widths': widths, 'scope': 'Complete MD rendered; viewport layout inspected, not every source word'}
                receipt.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
                records.append(record)
                page.close()
        browser.close()
    (BASE / '_проверка/render_summary.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
    print('Rendered', len(records), 'complete saved Markdown bundles')


if __name__ == '__main__':
    main()
