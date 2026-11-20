"""Read-only audit of every saved DeepSeek v3 response; no Client/API calls."""
from pathlib import Path
import sys,json,hashlib,csv,collections,datetime
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_models as rm
from deepseek_validation import decode_answer,validate_answer
from compare_results import compare_decimals_to_spans
BASE=rm.BASE
OUT=BASE/'_проверка/Аудит_DeepSeek_2026-11-16'
HASHES={}
def sha(p):
 p=Path(p);key=(str(p),p.stat().st_size,p.stat().st_mtime_ns)
 if key not in HASHES:HASHES[key]=hashlib.sha256(p.read_bytes()).hexdigest()
 return HASHES[key]
def main():
 OUT.mkdir(exist_ok=True);rows=[]
 paths=sorted((BASE/'_проверка/DeepSeek').glob('*/v3/page_*.json'))
 for path in paths:
  rid=path.parents[1].name;n=int(path.stem.split('_')[1]);data=json.loads(path.read_text());flags=[]
  try:validate_answer(data.get('response'),n)
  except ValueError as e:flags.append({'kind':'response_contract','detail':str(e)})
  import re
  if re.search(r'<!--\s*pdf_page\s*:',data.get('response',{}).get('markdown','')):
   flags.append({'kind':'redundant_wrapper_marker','detail':'Matching wrapper can be removed by existing source-guarded assembler; raw response preserved'})
  signature=data.get('request_signature',{})
  if data.get('request_sha256')!=hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest():flags.append({'kind':'request_fingerprint'})
  index=json.loads((BASE/'_проверка/входы'/rid/'pages.json').read_text());item=index['pages'][n-1]
  if item['pdf_page']!=n:raise ValueError('Input index page mismatch')
  if sha(BASE/item['image'])!=data.get('source_image_sha256'):flags.append({'kind':'source_image_identity'})
  if signature.get('packet_sha256')!=sha(BASE/item['packet']):flags.append({'kind':'packet_identity'})
  if data.get('instruction_sha256')!=rm.INSTRUCTION_SHA:flags.append({'kind':'instruction_identity'})
  prepared=json.loads((BASE/'_проверка/геометрия'/rid/(path.stem+'_metadata.json')).read_text())
  images=[BASE/p for p in prepared['images']]
  if [sha(p) for p in images]!=signature.get('provided_image_sha256'):flags.append({'kind':'provided_images_identity'})
  packet=json.loads((BASE/item['packet']).read_text())
  text=json.dumps({'page':packet,'source_geometry':prepared['geometry']},ensure_ascii=False)+'\n'
  if hashlib.sha256(text.encode()).hexdigest()!=signature.get('rich_text_sha256'):flags.append({'kind':'rich_text_identity','detail':'Assumes standard pass without explicit correction'})
  raw=path.parent/'raw'/path.name
  if not raw.is_file():flags.append({'kind':'missing_raw'})
  else:
   rawdata=json.loads(raw.read_text());choice=rawdata['choices'][0]
   if choice.get('finish_reason')!='stop':flags.append({'kind':'truncated_response'})
   try:
    raw_answer=decode_answer(choice['message']['content'])
    if raw_answer!=data['response']:flags.append({'kind':'raw_answer_mismatch'})
   except ValueError as e:flags.append({'kind':'raw_json','detail':str(e)})
  numeric=compare_decimals_to_spans(data['response']['markdown'],prepared['decimal_reference'])
  if numeric['pdf_only'] or numeric['markdown_only']:flags.append({'kind':'decimal_span_suspect','pdf_only':numeric['pdf_only'],'markdown_only':numeric['markdown_only']})
  issues=data['response'].get('issues',[])
  rows.append({'report_id':rid,'pdf_page':n,'flags':flags,'model_issues':issues,'saved_status':data.get('review_status'),'numeric_comparison':numeric,'checked':False})
 counts=collections.Counter(f['kind'] for r in rows for f in r['flags'])
 summary={'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'responses':len(rows),'reports':len({r['report_id'] for r in rows}),'pages_with_flags':sum(bool(r['flags']) for r in rows),'pages_with_model_issues':sum(bool(r['model_issues']) for r in rows),'flag_types':dict(counts),'scope':'All saved v3 responses checked for source/raw/request identity and response contract; decimal differences are suspects, not measured accuracy; no full visual semantic review','pages':rows}
 (OUT/'audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 with (OUT/'pages.csv').open('w',newline='') as f:
  writer=csv.writer(f);writer.writerow(['report_id','pdf_page','flags','model_issues','checked'])
  for r in rows:writer.writerow([r['report_id'],r['pdf_page'],','.join(x['kind'] for x in r['flags']),json.dumps(r['model_issues'],ensure_ascii=False),False])
 lines=['# Проверка сохранённых ответов DeepSeek v3','',f"Проверены все {len(rows)} сохранённых ответов по {summary['reports']} отчётам. API не вызывался.",'',f"Страниц с диагностическими флагами: {summary['pages_with_flags']}. Страниц с замечаниями самой модели: {summary['pages_with_model_issues']}.",'','| Тип | Число страниц |','|---|---:|']+[f'| {k} | {v} |' for k,v in counts.items()]+['','Десятичные расхождения относительно PDF-span требуют сверки изображения. Символьный слой PDF может ошибаться; это не число ошибок модели и не процент точности. Полная визуальная и смысловая проверка этих страниц пока не заявляется.','','[Все страницы](pages.csv) · [Доказательства и значения](audit.json)']
 (OUT/'README.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps({k:v for k,v in summary.items() if k!='pages'},ensure_ascii=False))
if __name__=='__main__':main()
