from pathlib import Path
import json
w=Path(__file__).resolve().parent;out=w.parent
p=w/'pages/0115.md';t=p.read_text();pos=t.index('\n\n',t.index('> **Техническая пометка.**'));t=t[:pos]+'\n\n'+(w/'115-checked-transcript.md').read_text()+t[pos:];p.write_text(t)
r=json.loads((w/'pages.json').read_text());r['method']='Native PyMuPDF characters, vector geometry for HTML tables, local Tesseract for scanned assurance on page 115; source page images retained.'
r['pages'][114]['content_type']='mixed_native_text_and_scanned_assurance';r['pages'][114]['ocr']={'engine':'local Tesseract rus+eng','region_pdf':[90,70,555,717],'body_transcribed':True,'region_review_status':'checked','corrections':['Восстановлено ФИО под печатью по изображению.','Исправлен адрес GRI по изображению.','Убраны ошибочно распознанные символы логотипа.']}
for n in [6,31,91,114,115]:r['pages'][n-1]['review_scope']='Выборочный просмотр изображения и отдельных блоков; вся страница не сверена.'
r['pages'][3]['issues'].append('Широкий складной разворот: линейный порядок блоков требует ручной проверки.')
for a in r['pages']:
 a['structural_preview']='Просмотр миниатюры: общая вёрстка, наличие основного текста и графики; не сверка содержания.'
 a['issues'].append('Автоматическое снятие переносов и связи сносок требуют ручной проверки.')
 a['issues'].append('Визуальное отображение итогового Markdown не проверено: локальный headless-браузер не запустился.')
(w/'pages.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
parts=[(w/'pages'/f'{n:04}.md').read_text() for n in range(1,117)]
(out/'report.md').write_text('# ИСКУССТВО СОЗДАВАТЬ ЭНЕРГИЮ\n\nОтчет об устойчивом развитии Группы «ЛУКОЙЛ»\n\n2024\n\n'+'\n\n'.join(parts))
