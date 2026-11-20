from pathlib import Path
import sys
sys.path.insert(0,str(Path('11_Проект_Сбер/2_итерация/Тесты_PDF_в_MD_DeepSeek_Codex/tools').resolve()))
import run_deepseek_pilot as pilot
root=Path('11_Проект_Сбер/Итоговый проект/1 шаг - перевод PDF в MD/_проверка/Сравнение_инструкций_2026-11-17')
variant=sys.argv[1]
pilot.MASTER=Path('11_Проект_Сбер/Итоговый проект/1 шаг - перевод PDF в MD/_проверка/Оптимизация_агента_2026-11-17/before/project/PDF_TO_MD_AGENT.md') if variant=='baseline' else Path('11_Проект_Сбер/Итоговый проект/1 шаг - перевод PDF в MD/Агент/PDF_TO_MD_AGENT.md')
specs=['GAZP-2023-ОУР:57','GAZP-2025-ОУР:75','GAZP-2025-ОУР:109','GAZP-2023-ЭО:76','TRMK-2023-ИО:4','GAZP-2023-ОУР:92','GAZP-2024-ОУР:113','LKOH-2023-ОУР:15','LKOH-2023-ОУР:98','GAZP-2023-ЭО:52','GAZP-2024-ОУР:95','IRKN-2023-ИО:13','IRKN-2023-ИО:98']
sys.argv=['run_deepseek_pilot.py','--output',str(root/variant),'--run-version','instruction-ab-'+variant+'-20261117','--execute']
for p in specs:sys.argv.extend(['--page',p])
pilot.main()
