# Переносимый третий этап: проверка фактов

Python 3.10+; только стандартная библиотека. Перенеси всю папку `Агент` на другой компьютер. Скрипт не требует API-ключа и не делает внешних запросов. Реальный поиск выполняет исследовательская модель через доступный в её сессии поисковый инструмент; инструкции — `FACT_CHECK_AGENT.md`.

## Запуск

```bash
python3 factcheck.py prepare classified.json run
python3 factcheck.py next run
# Исследователь читает run/prompt.md, run/plan.json, выполняет поиск и создаёт response.json
python3 factcheck.py ingest run response.json
python3 factcheck.py check run
python3 factcheck.py export run export --allow-partial
```

`prepare` принимает JSON `{"claims":[...]}`, `{"rows":[...]}` либо список. В строке нужны `quote` или `statement`; все исходные поля сохраняются в `original`. Исходные ID не обязаны быть уникальными: канонический ID очереди C000001 и input_index сохраняют различимость строк. Пустые E/S/G и спорные строки не удаляются. Источник, prompt и план копируются в run с хешами; внешние исходники после этого не используются. Чтобы сменить вход/методику, создай новый run.

`next` возвращает непроверенные и незавершённые строки, их исходный контекст и следующую revision. В `results` хранится неизменяемая история JSON+SHA256 каждой строки; повторная попытка требует следующего номера ревизии. Запись отдельного результата атомарна. `.lock` предотвращает одновременные записи. После аварии сначала убедись, что процесс не работает, и лишь затем убирай оставшийся `.lock`. Незаконченная пара SHA/JSON без JSON не считается выполненной работой.

`export` без флага запрещён при непроверенных/незавершённых строках. С флагом добавляет `_draft` к имени папки, выводит `status=partial` и сохраняет каждую исходную строку, в том числе без оценки. Все завершённые поиски могут всё равно закончиться insufficient_evidence: `research_complete` не означает «все факты подтверждены». Существующие экспорты не перезаписываются.

Выход: `claims.json` (исходные строки + полная доказательная база), `claims.csv` (UTF-8 BOM, `;`), `summary.json`. `assessment=null` означает отсутствие принятого исследовательского ответа.

## Контракт response

Полный исполняемый пример — `examples/synthetic_response.json` (искусственные данные, не реальный поиск). Поля:

- schema_version=`esg-factcheck-1.0`; source_sha256 из plan; claim_id; точная исходная quote; reviewer; checked_at (ISO8601 с часовым поясом); revision; reason.
- research_status=`complete|partial|blocked`; verdict=`true|false|partial|insufficient_evidence|not_verifiable|not_due`. Непроверенные строки получают not_researched автоматически, без придуманного response.
- target: proposition, entity, period, boundary, assessment_object=`reported_fact|promise_made|promise_fulfillment|principle`; для исполнения — due_date YYYY-MM-DD и deadline_basis. Неустановленный срок требует открытого исхода.
- searches: id, direction=`support|contradiction`, query, tool, tool_ref, searched_at, status=`completed|blocked`, source_ids, outcome_note. Сохраняй только реально выполненные запросы, а не план как результат.
- sources: id, url, publisher, origin_group, origin_basis, publication_date (YYYY-MM-DD либо null+publication_date_note), event_period, locator, content, content_sha256, tool_ref, retrieved_at, access=`full_text|excerpt|snippet`, independence=`independent|issuer|issuer_republication|unknown`.
- evidence: id, source_id, quote (точная подстрока content), relation=`supports|contradicts|context`, reason; alignment содержит entity/period/boundary/metric/unit, каждая с status=`matched|not_applicable|mismatch|unknown` и reason.
- aspects: id, proposition, status=`supported|contradicted|unresolved`, evidence_ids, reason; conflict_resolution при конфликте. Каждое evidence должно участвовать хотя бы в одном аспекте.
- Для true/false/partial: source_review={status:verified,method,locator}; aspect_coverage_confirmed=true и aspect_coverage_reason. Нужны независимые прочитанные сопоставимые доказательства по каждому существенному аспекту. Простая корпоративная републикация/сниппет не подходят.

Хеш текста источника: `hashlib.sha256(content.encode('utf-8')).hexdigest()`. Пакет фиксирует полученный отрывок и проверяет цитату в нём; он не доказывает, что отрывок действительно скачан с указанного URL. Реальность tool_ref, независимость, смысловое соответствие и достаточность разбиения проверяются исследователем/ревьюером. Для полноценного аудита сохраняй нативный журнал поискового инструмента отдельно от ответа модели. Не заполняй tool_ref вымышленными значениями.

## Проверка установки без внешнего поиска

```bash
python3 -m unittest discover -s tests -v
python3 factcheck.py prepare examples/synthetic_input.json demo_run
python3 factcheck.py ingest demo_run examples/synthetic_response.json
python3 factcheck.py next demo_run
python3 factcheck.py export demo_run demo_export --allow-partial
```

Это тест контракта на искусственных фактах. Example.org и fixture-ссылки не являются доказательствами реальных ESG-результатов.

`examples/gazprom_pilot_input.json` содержит четыре реальные цитаты из ранее выполненного пилота Газпрома. Команда `prepare examples/gazprom_pilot_input.json gazprom_run` создаёт очередь с нулём завершённых проверок. Результаты старого поиска намеренно не объявляются новым provenance-rich исследованием: для них нужно повторно открыть источники, сохранить отрывки и журнал, установить даты/периметры. Известный пограничный случай: закупка САКВ позднее заявленного года не доказывает отсутствие ранее разработанного плана. Корпоративный отчёт 2024 с расходами 2023 может подтверждать арифметическую согласованность, но не независимую истинность расходов.

Протокол основан на локальных CLAIM_ASSESSMENT_AGENT.md (17.11.2026) и README сквозной проверки Газпром 2023; старые коды и результаты не изменяются. Модель не назначена жёстко; версия и имя фактического рецензента должны записываться в reviewer. Качество на полном корпусе и юридическое заключение о гринвошинге не заявляются.
