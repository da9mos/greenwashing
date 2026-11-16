---
проект: study
тип: doc
дата: 2026-11-15
---
# 03 — конвейер детектора (итерация 3)

*Создано 12.11.2026. Как работает конвейер без API-ключа, подробно: [../00_общий_план/Конвейер_без_API.md](../00_общий_план/Конвейер_без_API.md).*

Скрипты здесь не обращаются к модели. Механику (разбор PDF, куски, партии, проверку цитат, таблицы, метрики, индекс) делают скрипты Python. Работу с текстом (заявления, цели, разметка, классы) делает Claude в потоках проекта: читает промпт из `prompts/` и партию из `batches/`, пишет ответ в `llm/`, отмечает партию в `runs/manifest.csv`.

**Статус на 16.11.2026:** действуют тексты v4 (`data/pages_v4`), заявления и эталон на них — `data/out/claims_text_v4.csv` и `gold_extract_text_v4.csv`. Ниже статус на 15.11.

**Статус на 15.11.2026:** тексты всех 92 отчётов и эталон уже есть. Реализован этап извлечения заявлений Георгия: [результат и ограничения](study_report_извлечение_ESG_2026-11-15.md), [таблица](data/out/claims.csv), [промпт](prompts/extract_v1.md), [качество](data/extract_evaluation/v1/metrics.json). Остальная схема ниже описывает общий проект, не готовность всех его этапов. Новое извлечение выполнялось потоками Codex; старый эталон размечен Claude.

Пересобрать извлечение из сохранённых ответов без модели и API, из этой папки:

```bash
python src/run_extract.py --output-root data/rebuilt_extract/run_01
python -m unittest discover -s tests -v
```

Заявления Георгия (extract v1) собраны на текстах v2 и заморожены: исходная таблица `data/out/claims.csv`, комплект сборки в `data/extract/v1/`, оценка в `data/extract_evaluation/v1/`. Пересборка `run_extract.py` всегда берёт тексты v2 и исходный эталон, поэтому совпадает с ними по хэшам. **Для работы дальше берите версию на действующих текстах v4:** `data/out/claims_text_v4.csv` (те же заявления и метки, цитата и страница по тексту v4). Новая папка назначения обязательна. При повторной сборке цитаты сверяются с исходными страницами; промпт и входные партии проверяются по хэшам. Числовые поля `metric/value/unit/base_year/target_year` пока пусты, их извлечение отдельным проходом не выполнялось.

### Версии текстов (с 16.11.2026)

Какую версию брать, решает один файл: `src/text_versions.py` (`CURRENT = "v4"`). Скрипты `chunk.py`, `audit_gold.py`, `evaluate_extract.py` по умолчанию берут действующую версию, у `audit_gold.py` и `build_extract.py` есть `--text-version v2|v3|v4`. Замороженное извлечение v1 (`prepare_extract.py`, `build_extract.py --version v1`, `extract_integrity.py`, `run_extract.py`) всегда работает на v2.

| версия | тексты | заявления / эталон | статус |
|---|---|---|---|
| v2 | `data/pages`, `data/chunks` | `claims.csv`, `gold_extract.csv` | исходная, заморожена для extract v1 |
| v3 | `data/pages_v3`, `data/chunks_v3` | `claims_text_v3.csv`, `gold_extract_text_v3.csv` | **УСТАРЕЛО** 16.11: «№» → 9 в ММК 2025, дефисы по словарю |
| v4 | `data/pages_v4`, `data/chunks_v4` | `claims_text_v4.csv`, `gold_extract_text_v4.csv` | **действует**: шрифт и дефисы по самим PDF, см. [data/text_v4/README.md](data/text_v4/README.md) |

Для разбора PDF нужна `pymupdf==1.28.2` (`pip install -r requirements.txt`): на ней разбор совпадает с v2 символ в символ. Чистка текстов (v3, v4) PDF не читает и библиотеку не требует.

```
config.yaml            версии промптов по этапам, размер куска и партии, квоты, порог проверки цитаты
data/reports/          PDF (после «скачивай»)
data/pages_v4/         текст по страницам: код_отчёта.jsonl (действующая версия; v2 — data/pages)
data/chunks_v4/        куски с номером страницы (v2 — data/chunks)
data/text_v4/          как получен v4: переносы.csv, шрифт ММК 2025, сверка с PDF
batches/<этап>/        входные партии для потоков (extract, targets, dynamics, annotate_A, annotate_B, classify)
prompts/               промпты с версией: extract_v1.md и т. д.
llm/<этап>/<версия>/   ответы модели, по файлу на партию; не перезаписываются и руками не правятся
runs/manifest.csv      журнал партий: строка на каждую партию
data/out/              claims_text_v4.csv (заявления, действует), gold_extract_text_v4.csv (эталон), targets.csv, metrics_dynamics.csv, external_facts.csv, gold.csv, classes.csv, index.csv
src/                   parse.py, chunk.py, make_batches.py, check.py, merge.py, dynamics.py, agreement.py, metrics.py, index.py
run.py                 python run.py --company NORN  (собирает таблицы из готовых ответов, без модели и без ключа)
requirements.txt
```

**Главная копия — репозиторий GitHub `da9mos/greenwashing`** (решение Григория 16.11.2026): все правки и результаты сдаются туда через ветку и PR. Библиотека проекта на claude.ai, Google Drive и папка на компьютере Григория — копии, их обновляют из GitHub после каждого этапа. Таблицы — CSV, разделитель `;`, UTF-8 с BOM.
