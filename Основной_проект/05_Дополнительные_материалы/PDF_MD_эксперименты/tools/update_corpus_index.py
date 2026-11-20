"""Index existing report versions without copying or replacing source artifacts."""
from pathlib import Path
import csv,json,hashlib,re,datetime,os,urllib.parse
BASE=Path(__file__).resolve().parents[1]
ROOT=BASE.parents[2]
REGISTRY=ROOT/'11_Проект_Сбер/3_итерация/greenwashing/01_итерация_1_сбор_данных/выборка_30/reports.csv'
OUT=ROOT/'11_Проект_Сбер/Итоговый проект/Корпус_92_отчёта.md'
def main():
 rows=list(csv.DictReader(REGISTRY.open(encoding='utf-8-sig'),delimiter=';'))
 native=json.loads((BASE/'_проверка/native_corpus_validation.json').read_text())['reports']
 sources={r['report_id']:r for r in json.loads((BASE/'_проверка/sources_manifest.json').read_text())['reports']}
 records=[]
 for row in rows:
  rid=row['report_id'];cid=row['company_id'];curated=BASE/'Codex'/cid/rid/'report.md';receipt=BASE/'_проверка/Codex'/rid/'v2/receipt.json'
  if curated.is_file() and receipt.is_file():
   meta=json.loads(receipt.read_text())
   if not meta.get('assembled'):raise ValueError('Unassembled Codex result '+rid)
   source=curated;expected=meta['report_sha256'];kind='Codex: рабочая версия'
   source_hash=meta['source_sha256']
  else:
   meta=native.get(rid,{})
   if meta.get('state')!='published':raise ValueError('No accepted automatic version '+rid)
   source=BASE/'Все_отчёты_MD'/cid/rid/'report.md';expected=meta['final_md_sha256'];kind='Автоматический перенос'
   source_hash=meta['source_sha256']
  body=source.read_text();digest=hashlib.sha256(source.read_bytes()).hexdigest()
  if digest!=expected:raise ValueError('Saved MD hash changed '+rid)
  if source_hash!=sources[rid]['sha256']:raise ValueError('Source identity mismatch '+rid)
  pages=sources[rid]['pages'];markers=[int(x) for x in re.findall(r'<!--\s*pdf_page:\s*(\d+)\s*-->',body)]
  if markers!=list(range(1,pages+1)):raise ValueError('Page coverage mismatch '+rid)
  for target in re.findall(r'!\[[^\]]*\]\(([^\n)]+)\)',body):
   if target.startswith(('http://','https://','data:')):continue
   if not (source.parent/urllib.parse.unquote(target.strip('<>'))).is_file():raise ValueError('Missing image '+rid+': '+target)
  records.append({'report_id':rid,'company':row['company'],'year':row['year'],'pages':pages,'kind':kind,'path':str(source),'sha256':digest,'checked':False})
 codex=sum(r['kind'].startswith('Codex') for r in records);total=sum(r['pages'] for r in records)
 now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5))).isoformat()
 lines=['# Корпус: 92 отчёта по 30 компаниям','',f'Обновлено: {now}. Все {len(records)} отчётов доступны в Markdown, {total:,} физических страниц.'.replace(',',' '),'',f'Отдельная обработка Codex: {codex}. Автоматические версии для остальных: {len(records)-codex}. Полная сверка содержания по PDF не завершена.','','Ссылка ведёт на рабочую версию Codex, если она собрана; иначе на существующий автоматический перенос. Файлы не копировались и не подменялись.','','Автоматический перенос сохраняет текстовый слой, геометрию и изображения. Контроль символов и наличие всех страниц не доказывают правильность порядка чтения, таблиц и OCR. Версии Codex содержат адресные исправления, но также не объявляются полностью проверенными.','','| Компания | Отчёт | Страниц | Версия |','|---|---|---:|---|']
 for r in records:
  link=urllib.parse.quote(os.path.relpath(r['path'],OUT.parent),safe='/')
  lines.append(f"| {r['company']} | [{r['report_id']}]({link}) | {r['pages']} | {r['kind']} |")
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text('\n'.join(lines)+'\n')
 summary={'updated_at':now,'reports':records,'available':len(records),'codex_versions':codex,'automatic_versions':len(records)-codex,'pages':total,'source_review':'not_complete'}
 (BASE/'_проверка/unified_corpus_index.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in summary.items() if k!='reports'},ensure_ascii=False))
if __name__=='__main__':main()
