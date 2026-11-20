# Сравнение PDF → Markdown: текущий снимок

Реестр: **92 отчётов**, **30 компаний**. PDF прочитано: 92; физических страниц: 14731.

## Покрытие и ошибки

Состояния документов: {'compared_unreviewed': 3, 'structural_issues': 2, 'pending': 87}
DeepSeek: {'structurally_valid_unreviewed': 3, 'structural_issues': 2, 'pending': 87}
Codex: {'structurally_valid_unreviewed': 25, 'pending': 67}
Структурных замечаний: **2**. Парных страниц для сравнения: **665**.

Отсутствующий report.md или пакет — pending. Существующий файл с нарушениями маркеров, ссылок либо изображений отражён как structural_issues. Это автоматическая диагностика, которая не присваивает checked. Прогон моделей может ещё выполняться.

## Десятичные числа по PDF-span

Страниц с диагностическими расхождениями: {'DeepSeek': 68, 'Codex': 217}. См. comparison_decimal_differences.csv; координаты, шрифт, размер и flags каждого исходного span сохранены в comparison_pages.jsonl.
Десятичные токены извлекаются из отдельных PDF-span, без склейки с соседним надстрочным номером сноски. Сравнение сплошного текста сохранено отдельно. Это не автоматический вердикт об ошибке модели: контекст таблиц и OCR требуют проверки.

## Детали

| Отчёт | PDF стр. | Пакеты | DeepSeek | Codex | Замечаний |
|---|---:|---|---|---|---:|
| GAZP-2023-ОУР | 136 | packets_valid_unreviewed | structurally_valid_unreviewed | structurally_valid_unreviewed | 0 |
| GAZP-2023-ЭО | 84 | packets_valid_unreviewed | structurally_valid_unreviewed | structurally_valid_unreviewed | 0 |
| GAZP-2024-ОУР | 150 | packets_valid_unreviewed | structural_issues | structurally_valid_unreviewed | 1 |
| GAZP-2025-ОУР | 152 | packets_valid_unreviewed | structural_issues | structurally_valid_unreviewed | 1 |
| IRKN-2023-ИО | 143 | packets_valid_unreviewed | structurally_valid_unreviewed | structurally_valid_unreviewed | 0 |
| IRKN-2024-ИО | 149 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| IRKN-2025-ИО | 206 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| LKOH-2023-ОУР | 115 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| LKOH-2024-ОУР | 116 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| LKOH-2025-ОУР | 114 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| NVTK-2023-ОУР | 138 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| NVTK-2024-ОУР | 129 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| NVTK-2025-ОУР | 121 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| ROSN-2023-ОУР | 134 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| ROSN-2024-ОУР | 135 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| ROSN-2025-ИО | 68 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| TATN-2023-ИО | 172 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| TATN-2024-ИО | 200 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| TATN-2025-ИО | 258 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| TRNF-2023-ИО | 343 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| TRNF-2024-ИО | 303 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| TRNF-2025-ИО | 190 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| ALRS-2023-ОУР | 170 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| ALRS-2024-ОУР | 189 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| ALRS-2025-ОУР | 247 | packets_valid_unreviewed | pending | pending | 0 |
| MAGN-2023-ИО | 242 | packets_valid_unreviewed | pending | structurally_valid_unreviewed | 0 |
| MAGN-2024-ИО | 329 | packets_valid_unreviewed | pending | pending | 0 |
| MAGN-2025-ИО | 378 | packets_valid_unreviewed | pending | pending | 0 |
| MINV-2023-ОУР | 158 | packets_valid_unreviewed | pending | pending | 0 |
| MINV-2024-ОУР | 162 | packets_valid_unreviewed | pending | pending | 0 |
| MINV-2025-ОУР | 188 | packets_valid_unreviewed | pending | pending | 0 |
| MTLR-2023-ОУР | 98 | packets_valid_unreviewed | pending | pending | 0 |
| MTLR-2024-ОУР | 133 | packets_valid_unreviewed | pending | pending | 0 |
| MTLR-2025-ГО | 69 | packets_valid_unreviewed | pending | pending | 0 |
| MTLR-2025-ОУР | 164 | packets_valid_unreviewed | pending | pending | 0 |
| NLMK-2023-ОУР | 96 | packets_valid_unreviewed | pending | pending | 0 |
| NLMK-2024-ИО | 172 | packets_valid_unreviewed | pending | pending | 0 |
| NLMK-2025-ИО | 139 | packets_valid_unreviewed | pending | pending | 0 |
| NORN-2023-ОУР | 246 | packets_valid_unreviewed | pending | pending | 0 |
| NORN-2024-ОУР | 198 | packets_valid_unreviewed | pending | pending | 0 |
| NORN-2025-ОУР | 119 | packets_valid_unreviewed | pending | pending | 0 |
| PLZL-2023-ОУР | 152 | packets_valid_unreviewed | pending | pending | 0 |
| PLZL-2024-ОУР | 257 | pending | pending | pending | 0 |
| PLZL-2025-ИО | 136 | pending | pending | pending | 0 |
| PLZL-2025-ОУР | 346 | pending | pending | pending | 0 |
| RUAL-2023-ОУР | 206 | pending | pending | pending | 0 |
| RUAL-2024-ОУР | 149 | pending | pending | pending | 0 |
| RUAL-2025-ИО | 294 | pending | pending | pending | 0 |
| RASP-2023-ОУР | 70 | pending | pending | pending | 0 |
| RASP-2024-ОУР | 103 | pending | pending | pending | 0 |
| RASP-2025-ОУР | 204 | pending | pending | pending | 0 |
| CHMF-2023-ОУР | 295 | pending | pending | pending | 0 |
| CHMF-2024-ИО | 167 | pending | pending | pending | 0 |
| CHMF-2025-ИО | 186 | pending | pending | pending | 0 |
| TRMK-2023-ИО | 43 | pending | pending | pending | 0 |
| TRMK-2024-ОУР | 128 | pending | pending | pending | 0 |
| TRMK-2025-ОУР | 115 | pending | pending | pending | 0 |
| AKRN-2023-ОУР | 54 | pending | pending | pending | 0 |
| AKRN-2024-ОУР | 65 | pending | pending | pending | 0 |
| AKRN-2025-ИО | 117 | pending | pending | pending | 0 |
| PIGM-2023-ОУР | 120 | pending | pending | pending | 0 |
| PIGM-2024-ОУР | 175 | pending | pending | pending | 0 |
| PIGM-2025-ОУР | 187 | pending | pending | pending | 0 |
| SIBR-2023-ИО | 183 | pending | pending | pending | 0 |
| SIBR-2024-ИО | 223 | pending | pending | pending | 0 |
| SIBR-2025-ИО | 265 | pending | pending | pending | 0 |
| URKA-2023-ОУР | 131 | pending | pending | pending | 0 |
| URKA-2024-ОУР | 132 | pending | pending | pending | 0 |
| URKA-2025-ГО | 82 | pending | pending | pending | 0 |
| URKA-2025-ОУР | 121 | pending | pending | pending | 0 |
| URCH-2023-ОУР | 133 | pending | pending | pending | 0 |
| URCH-2024-ОУР | 110 | pending | pending | pending | 0 |
| URCH-2025-ОУР | 117 | pending | pending | pending | 0 |
| PHOR-2023-ИО | 202 | pending | pending | pending | 0 |
| PHOR-2024-ИО | 206 | pending | pending | pending | 0 |
| PHOR-2025-ИО | 217 | pending | pending | pending | 0 |
| KMAZ-2023-ОУР | 162 | pending | pending | pending | 0 |
| KMAZ-2024-ОУР | 127 | pending | pending | pending | 0 |
| KMAZ-2025-ГО | 124 | pending | pending | pending | 0 |
| SHLZ-2023-ОУР | 36 | pending | pending | pending | 0 |
| SHLZ-2024-ОУР | 56 | pending | pending | pending | 0 |
| SVEZ-2023-ОУР | 131 | pending | pending | pending | 0 |
| SVEZ-2024-ОУР | 58 | pending | pending | pending | 0 |
| SGZH-2023-ИО | 164 | pending | pending | pending | 0 |
| SGZH-2024-ИО | 167 | pending | pending | pending | 0 |
| SGZH-2025-ИО | 177 | pending | pending | pending | 0 |
| MVDK-2023-ГО | 190 | pending | pending | pending | 0 |
| MVDK-2024-ГО | 92 | pending | pending | pending | 0 |
| MVDK-2025-ГО | 211 | pending | pending | pending | 0 |
| RVDK-2023-ОУР | 92 | pending | pending | pending | 0 |
| RVDK-2024-ОУР | 95 | pending | pending | pending | 0 |
| RVDK-2025-ОУР | 105 | pending | pending | pending | 0 |

## Как читать сравнение

`comparison.csv` — одна строка на каждый RID. `comparison_details.json` — конкретные нарушения; `comparison_pages.jsonl` — отдельные результаты каждого сравнения по физической странице. Все файлы обновляются только этим инструментом, модельные результаты не исправляются.
Текст очищается от HTML-разметки, Markdown-оформления и явно служебных обёрток. Для каждой доступной страницы сопоставляется очищенная последовательность токенов и мультимножество числовых токенов: обе ветки друг с другом и каждая с исходным PDF-текстовым слоем. Ничего не подменяется старым результатом.
**Доля различий не является точностью модели.** PDF-слой может иметь неверный порядок колонок, дефектное извлечение, числа колонтитулов или отсутствовать на скане. OCR, содержание изображений, верность таблиц и отображение требуют самостоятельной визуальной сверки. Декодирование PNG/JPEG не проверяет содержание картинки. Внешние URL не открываются. Автоматические заголовочные якоря проверяются по правилам, близким GitHub; особенности другого рендера нужно проверять отдельно.
Повторить: `python3 tools/compare_results.py`. Снимок отражает только файлы, доступные во время чтения; результаты запущенных моделей появятся после очередного прогона проверки.
