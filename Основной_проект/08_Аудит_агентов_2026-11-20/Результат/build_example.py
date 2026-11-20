"""Use the project's fact export adapter and Excel builder for the audited eight-claim scope."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
AUDIT = HERE.parent
spec = importlib.util.spec_from_file_location('project_export', PROJECT / '04_Итоги_проверки/prepare_company_export.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
summary = json.loads((AUDIT / '03_Фактчекинг/atomic_export/summary.json').read_text())
assert summary['status'] == 'research_complete' and summary['total'] == 8 and summary['unfinished'] == 0
records = json.loads((AUDIT / '03_Фактчекинг/atomic_export/claims.json').read_text())['claims']
report = next(r for r in json.loads((PROJECT / '00_Отчёты/manifest.json').read_text()) if r['report_id'] == 'GAZP-2023-ЭО')
origin = {'issuer_republication': 'перепубликация данных компании', 'issuer': 'собственные данные компании',
          'independent': 'независимый источник', 'unknown': 'происхождение не установлено'}
rows = []
for number, record in enumerate(records, 1):
    assessment = record['assessment']
    row = adapter.display(record, report, number)
    row[4] = 'Исследовано: ' + row[4].lower()
    used = {e['source_id'] for e in assessment['evidence']}
    sources = [s for s in assessment['sources'] if s['id'] in used]
    links = '\n'.join(s['publisher'] + ': ' + s['url'] for s in sources)
    target = assessment['target']
    context = '; '.join(str(target[k]) for k in ('entity', 'period', 'boundary'))
    row[5] = (f"Внешнее исследование выполнено 20.11.2026; оба направления поиска сохранены в журнале.\n"
              f"Контекст: {context}.\n{assessment['reason']}\n"
              f"Исходник, физическая страница {record['original']['pdf_page']}: {report['pdf_source_url']}\n"
              f"Источники:\n{links}\nПроисхождение данных: "
              + '; '.join(dict.fromkeys(origin[s['independence']] for s in sources)))
    rows.append(row)
data = {'company': 'Газпром', 'draft': True,
        'scope_note': 'Проверка проектных агентов: 4 исходные цитаты → 8 тезисов; внешнее исследование завершено для 8/8. Охват всего отчёта не заявлен.',
        'headers': adapter.HEADERS,
        'sheets': [{'id': report['report_id'], 'title': '8 исследованных тезисов', 'rows': rows}]}
input_path = HERE / 'company.json'
input_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
dependencies = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
if not (HERE / 'node_modules').exists():
    (HERE / 'node_modules').symlink_to(dependencies, target_is_directory=True)
temp_output = Path(tempfile.mkdtemp(prefix='sber-project-export-')) / 'export'
builder = PROJECT / '04_Итоги_проверки/build_company_excel.mjs'
subprocess.run(['node', '--input-type=module', '-', str(input_path), str(temp_output)],
               input=builder.read_text(), text=True, cwd=HERE, check=True)
destination = HERE / 'Excel'
destination.mkdir(exist_ok=True)
(destination / 'CSV').mkdir(exist_ok=True)
(temp_output / 'Оценка_заявлений_Газпром_черновик.xlsx').replace(destination / 'Газпром_пример_полного_цикла_8_тезисов.xlsx')
(temp_output / 'CSV/GAZP-2023-ЭО.csv').replace(destination / 'CSV/GAZP-2023-ЭО.csv')
print('Built eight researched rows using the existing project export code')
