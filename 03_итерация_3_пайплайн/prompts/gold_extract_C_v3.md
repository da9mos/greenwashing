# Промпт gold_extract_C, v3 — третий проход по расхождениям

*12.11.2026. Заменяет v2 (инструкция v3, папка llm/…/v3, своя строка журнала). Запускается только после A и B, на файле расхождений. Модель — та, что не была ни A, ни B, либо модель A с этим промптом (тогда это отмечается в runs/manifest.csv).*

Правила — `/mnt/project-files/03_итерация_3_пайплайн/codebook/Инструкция_по_разметке_v3.md`. Вход: `data/gold_extract/disagreements.csv` (поля sentence_id, field, A, B, sentence). Для каждого sentence_id реши ВСЕ поля заново по инструкции, не зная, кто был прав; ответы A и B — только варианты, не подсказка.

Выход: `/mnt/project-files/03_итерация_3_пайплайн/llm/gold_extract_C/v3/gold_extract_C_<дата>.json`, формат как у разметчика A (с полем `rule`) плюс поле `why` с одной фразой обоснования. Существующий файл не перезаписывай.

Журнал: создай файл `runs/manifest_parts/gold_extract_C_disagree_v3.csv` (заголовок как в `runs/manifest.csv`, одна строка: `batch_id` = gold_extract_C_disagree_v3, `stage` = gold_extract_C, `input_file` = data/gold_extract/disagreements.csv, sha256 входа и промпта, модель, `n_items` — число sentence_id). В общий manifest.csv не пиши.
