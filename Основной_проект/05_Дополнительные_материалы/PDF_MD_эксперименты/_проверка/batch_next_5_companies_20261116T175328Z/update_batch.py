from pathlib import Path
import sys,json,datetime,collections,hashlib,re
AUDIT=Path(__file__).resolve().parent
BASE=AUDIT.parents[1]
launch=json.loads((AUDIT/'launch.json').read_text());control=json.loads((BASE/'_проверка/codex_controller.json').read_text())
manifest=json.loads((BASE/'_проверка/sources_manifest.json').read_text())
source_rows=manifest.get('reports',[]) if isinstance(manifest,dict) else manifest
expected={r['report_id']:r.get('pages') for r in source_rows}
rows=[]
for rid in launch['reports']:
 folder=BASE/'Codex'/rid.split('-')[0]/rid
 receipt_path=BASE/'_проверка/Codex'/rid/'v2/receipt.json'
 receipt=json.loads(receipt_path.read_text()) if receipt_path.is_file() else {}
 path=folder/'report.md';exists=path.is_file();markers=[]
 if exists:markers=[int(n) for n in re.findall(r'<!--\s*pdf_page:\s*(\d+)\s*-->',path.read_text())]
 pages=expected.get(rid)
 rows.append({'report_id':rid,'state':control.get('reports',{}).get(rid,{}).get('state','unknown'),'md_exists':exists,'pages':pages,'markers':len(markers),'markers_complete':bool(pages and markers==list(range(1,pages+1))),'assembled':receipt.get('assembled',False),'transcription_complete':receipt.get('transcription_complete',False),'pending_pages':len(receipt.get('pending_pages',[])),'checked':False})
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5))).isoformat()
summary={'updated_at':now,'reports':rows,'md_files':sum(r['md_exists'] for r in rows),'assembled':sum(r['assembled'] for r in rows),'transcription_complete':sum(r['transcription_complete'] for r in rows),'checked':0,'controller_status':control['overall_status']}
(AUDIT/'batch_status.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
lines=['# Перевод PDF → Markdown: пять компаний','',f'Обновлено: {now}. АЛРОСА, ММК, Металлоинвест, Мечел, НЛМК; 13 недостающих отчётов.','',f"Markdown-файлы: {summary['md_files']}/13. Структурная сборка: {summary['assembled']}/13. Полная транскрипция без открытых страниц: {summary['transcription_complete']}/13. Полная независимая сверка: не подтверждена.",'','| Отчёт | Этап | Страниц в MD / PDF | Сборка | Открытых страниц |','|---|---|---:|---|---:|']
for r in rows:
 rid=r['report_id'];link='../../Codex/'+rid.split('-')[0]+'/'+rid+'/report.md'
 title=f'[{rid}]({link})' if r['md_exists'] else rid
 lines.append(f"| {title} | {r['state']} | {r['markers']} / {r['pages']} | {'да' if r['assembled'] else 'нет'} | {r['pending_pages'] if r['md_exists'] else '—'} |")
lines+=['','Файл и успешная сборка не доказывают точность всех чисел, таблиц и порядка чтения. Непроверенные места остаются pending. DeepSeek не запущен из-за блокировки баланса.','','[Параметры запуска](launch.json) · [Лог](controller.log) · [Проверка исходных кандидатов](candidate_identity_check.json) · [Проверка отображения](render_summary.json) · [Повторная проверка сборки](verification.json)']
(AUDIT/'СТАТУС.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='reports'},ensure_ascii=False))
