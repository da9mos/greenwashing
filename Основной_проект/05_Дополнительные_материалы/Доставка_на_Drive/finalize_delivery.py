from pathlib import Path
import json,csv

base=Path(__file__).parent
rows=json.loads((base/'packages.json').read_text())
root=json.loads((base/'upload_root_complete.json').read_text())
states=[root]+[json.loads((base/f'upload_{letter}.json').read_text()) for letter in 'abc']
uploads=[u for state in states for u in state['uploads']]
folders={}
for state in states:
    value = state.get('folders', {})
    if isinstance(value, list):
        value = {item['company']: item for item in value}
    folders.update(value)
expected={}
for row in rows:
    expected[row['report']+'.md']=(row,row['source'])
    for p in row['parts']:
        expected[Path(p).name]=(row,p)
actual={}
for u in uploads:
    name=u.get('name') or u.get('title') or u.get('file_name')
    assert name not in actual,f'duplicate {name}'
    actual[name]=u
missing=sorted(set(expected)-set(actual))
assert not missing,missing
assert set(actual)==set(expected)
assert len(uploads)==299
lines=['# Корпус: 92 отчёта по 30 компаниям на Google Drive','',
       '17.11.2026. Рабочие транскрипции. Полная смысловая сверка содержания с PDF не завершена.','',
       'MD — отдельный читаемый текст. ZIP/ZIP-части содержат report.md и изображения assets без изменений. '
       'Скачайте все ZIP одного отчёта и распакуйте их в одну папку: каждый ZIP самостоятелен; это не многотомный архив. '
       'Получится папка с кодом отчёта, report.md и assets. Отдельный MD можно использовать для поиска и анализа.','',
       '| Компания | Отчёт | PDF-страниц | Markdown | Полный пакет с изображениями |','|---|---|---:|---|---|']
for row in rows:
    md=actual[row['report']+'.md']
    parts=' · '.join(f'[{Path(p).name}]({actual[Path(p).name]["url"]})' for p in row['parts'])
    lines.append(f'| {row["company"]} | {row["report"]} | {row["pages"]} | [Открыть MD]({md["url"]}) | {parts} |')
(base/'Корпус_92_отчёта_Drive.md').write_text('\n'.join(lines)+'\n')
with (base/'Реестр_доставки.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.writer(f,delimiter=';');writer.writerow(['Компания','Отчёт','Имя файла','ID Drive','URL','Байт','Локальный источник'])
    for name,(row,p) in expected.items():
        u=actual[name];writer.writerow([row['company'],row['report'],name,u['id'],u['url'],Path(p).stat().st_size,p])
manifest={name:{'id':u['id'],'url':u['url'],'parent_id':u['parent_id'],'bytes':Path(expected[name][1]).stat().st_size} for name,u in actual.items()}
(base/'delivery_manifest.json').write_text(json.dumps({'reports':92,'companies':30,'drive_files':299,'files':manifest},ensure_ascii=False,indent=2))
print(json.dumps({'reports':92,'companies':30,'drive_files':len(uploads),'folders':len(folders)},ensure_ascii=False))
