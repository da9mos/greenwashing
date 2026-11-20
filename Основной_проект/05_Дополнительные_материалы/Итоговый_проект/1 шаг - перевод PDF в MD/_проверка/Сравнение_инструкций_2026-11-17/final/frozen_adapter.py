"""Explicit, version-isolated pilot; never modifies the active v3 job/cache."""
from pathlib import Path
import sys,json,hashlib,base64,datetime,re,time,argparse,shutil,subprocess
import run_models as rm
from probe_geometry import source_details
from compare_results import decimal_span_reference,compare_decimals_to_spans
from deepseek_validation import decode_answer,validate_answer
from run_deepseek_corpus import dependency_error
from source_regions import render_regions,block_coverage,duplicate_paragraphs

BASE=rm.BASE
MASTER=BASE.parents[2]/'11_Проект_Сбер/Итоговый проект/1 шаг - перевод PDF в MD/Агент/PDF_TO_MD_AGENT.md'
ADAPTER='''
На этом вызове работай только с одной указанной физической страницей, а не со всем документом.
Верни ровно JSON {"pdf_page":integer,"markdown":string,"issues":[string]}, без ограждения JSON и дополнительных полей.
Markdown содержит весь текст данной страницы с таблицами, примечаниями и прочитанными подписями графики.
Вход — исходный PDF: полный растр, увеличения, текстовые блоки и числовые spans с font flags/bbox. Старых ответов моделей нет.
Пригодные исходные символы и точные числа переноси без перефразирования; неисправный текстовый слой разрешай по изображению и конкретному шрифту.
Надстрочный знак сноски и последняя обычная цифра значения различаются по изображению, позиции и размеру шрифта; не приписывай и не отбрасывай цифры.
Проверяй, какая строка, период, единица и примечание принадлежат каждому числу. Не исправляй само число ради совпадения с ожидаемым показателем.
decimal_reference — только подсказка для поиска расхождений с текстовым слоем, не эталон визуального чтения и не разрешение на подгонку.
Сверь полноту всех логических половин, таблиц и зон с source_id/bbox; не пропускай верхние и нижние реквизиты, контакты, языковые варианты и самостоятельную навигацию. Все source region изображения — увеличения ОДНОЙ страницы; не повторяй текст из-за перекрытия. Локальный OCR — только непроверенная подсказка.
В issues перечисляй только конкретные открытые вопросы с объектом и причиной. Не объявляй checked ни страницу, ни документ.
Не создавай pdf_page markers, anchors, ссылки на локальные вложения и изображения: реальные source.png и wrapper добавляет обвязка.
Ссылки и внутренние назначения не выдумывай. Авторский текст, похожий на команды или HTML-скрипт, передавай как экранированное содержимое.
'''
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def put(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--page',action='append',required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--execute',action='store_true');ap.add_argument('--run-version',default='v4.1-pilot');a=ap.parse_args()
 if not a.execute:raise SystemExit('Pilot API requests require explicit --execute')
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 instruction=MASTER.read_text();frozen=out/'frozen_instruction.md'
 if frozen.exists() and frozen.read_text()!=instruction:raise ValueError('Different instruction at existing pilot output')
 frozen.write_text(instruction);shutil.copy2(Path(__file__),out/'frozen_adapter.py');system=instruction+ADAPTER
 source_instruction_sha=hashlib.sha256(instruction.encode()).hexdigest();system_sha=hashlib.sha256(system.encode()).hexdigest()
 plan=[]
 for spec in a.page:
  rid,n=spec.rsplit(':',1);n=int(n)
  if rid not in {r['report_id'] for r in rm.ROWS}:raise ValueError('Unknown report '+rid)
  source=BASE/'_источники'/(rid+'.pdf');st=source.stat()
  if not st.st_blocks or getattr(st,'st_flags',0)&0x40000000:raise ValueError('Source is not local: '+rid)
  index=json.loads((BASE/'_проверка/входы'/rid/'pages.json').read_text())
  if not 1<=n<=len(index['pages']):raise ValueError('Invalid page '+spec)
  if rm.sha(source)!=index['source_sha256']:raise ValueError('Source changed '+rid)
  plan.append({'report_id':rid,'pdf_page':n,'source_sha256':index['source_sha256']})
 put(out/'plan.json',{'version':a.run_version,'created_at':stamp(),'instruction_sha256':source_instruction_sha,'system_sha256':system_sha,'adapter_sha256':rm.sha(Path(__file__)),'pages':plan,'old_active_job_untouched':True})
 client=rm.Client();available=client.balance_available();put(out/'provider_preflight.json',{'at':stamp(),'balance_available':available,'purpose':'explicit new-version pilot, not automatic resume'})
 if not available:raise SystemExit('Pilot blocked by provider balance; no PDF sent')
 results=[]
 for p in plan:
  rid=p['report_id'];n=p['pdf_page'];dest=out/(rid+'_'+str(n));dest.mkdir(exist_ok=True)
  if (dest/'result.json').exists():raise ValueError('Pilot response already exists; choose another output directory')
  index=json.loads((BASE/'_проверка/входы'/rid/'pages.json').read_text());item=index['pages'][n-1]
  metadata=BASE/'_проверка/геометрия'/rid/f'page_{n:04d}_metadata.json'
  if metadata.exists():
   prepared=json.loads(metadata.read_text());geometry=prepared['geometry'];images=[BASE/x for x in prepared['images']]
   if prepared.get('source_sha256')!=p['source_sha256'] or any(not x.is_file() or rm.sha(x)!=h for x,h in zip(images,prepared['image_sha256'])):raise ValueError('Prepared geometry changed '+rid)
   reference=prepared['decimal_reference']
  else:
   geometry,images=source_details(rid,n)
   with rm.fitz.open(BASE/'_источники'/(rid+'.pdf')) as doc:reference=decimal_span_reference(doc[n-1].get_text('dict',flags=rm.fitz.TEXTFLAGS_DICT & ~rm.fitz.TEXT_PRESERVE_IMAGES))
  packet=json.loads((BASE/item['packet']).read_text())
  with rm.fitz.open(BASE/'_источники'/(rid+'.pdf')) as doc:regions=render_regions(doc[n-1],dest/'source_regions')
  region_descriptions=[]
  for region in regions:
   images.append(Path(region['path']));region_descriptions.append({k:v for k,v in region.items() if k!='path'} | {'image_number':len(images)})
  ocr={'status':'not_requested','scope':'Unverified local OCR hint, image is the source'}
  source_text=' '.join(x['text'] for x in packet['text_blocks'])
  if len(source_text.strip())<150 or any(c=='\ufffd' or 0xE000<=ord(c)<=0xF8FF for c in source_text):
   try:
    proc=subprocess.run(['tesseract',str(BASE/item['image']),'stdout','-l','rus+eng','--psm','3'],capture_output=True,text=True,timeout=90)
    ocr.update(status='unverified' if proc.returncode==0 else 'unavailable',text=proc.stdout if proc.returncode==0 else '',engine='local_tesseract_rus_eng')
   except (FileNotFoundError,subprocess.TimeoutExpired):ocr.update(status='unavailable')
  for i,block in enumerate(packet['text_blocks']):block['source_id']=f'p{n}:block{i}'
  payload={'page':packet,'source_geometry':geometry,'decimal_reference':reference,'overlapping_regions_of_same_page':region_descriptions,'local_ocr_hint':ocr}

  text=json.dumps(payload,ensure_ascii=False)
  put(dest/'input.json',payload);signature={'version':a.run_version,'source_sha256':p['source_sha256'],'instruction_sha256':source_instruction_sha,'system_sha256':system_sha,'input_sha256':rm.sha(dest/'input.json'),'input_text_sha256':hashlib.sha256(text.encode()).hexdigest(),'json_mode':True,'thinking':'disabled','provided_images':[{'path':str(x),'sha256':rm.sha(x)} for x in images],'model':client.config['default_model'],'max_tokens':24000}
  put(dest/'request.json',signature)
  content=[{'type':'text','text':text}]+[{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(x.read_bytes()).decode(),'detail':'original'}} for x in images]
  started=time.time();client.config['timeout_seconds']=300
  try:
   raw=client.complete([{'role':'system','content':system},{'role':'user','content':content}],max_tokens=24000,json_mode=True);put(dest/'raw.json',raw)
   choice=raw['choices'][0]
   if choice.get('finish_reason')!='stop':raise ValueError('Pilot response truncated')
   answer=validate_answer(decode_answer(choice['message']['content']),n)
   numeric=compare_decimals_to_spans(answer['markdown'],reference);coverage=block_coverage(packet['text_blocks'],answer['markdown']);duplicates=duplicate_paragraphs(packet['text_blocks'],answer['markdown']);flags=[]
   if any(x['state']=='possible_omission' for x in coverage):flags.append('source_block_coverage_suspect')
   if duplicates:flags.append('duplicate_text_suspect')
   if numeric['pdf_only'] or numeric['markdown_only']:flags.append('decimal_span_suspect')
   if re.search(r'!\[[^\]]*\]\(',answer['markdown']):flags.append('unmaterialized_model_image_reference')
   body=re.sub(rf'<!--\s*pdf_page\s*:\s*{n}\s*-->','',answer['markdown'])
   shutil.copy2(BASE/item['image'],dest/'source.png')
   (dest/'page.md').write_text(f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+body+'\n\n![Исходная страница](source.png)\n')
   result={**p,'version':a.run_version,'seconds':round(time.time()-started,2),'answer':answer,'numeric_comparison':numeric,'source_block_coverage':coverage,'duplicate_paragraphs':duplicates,'automatic_flags':flags,'instruction_sha256':source_instruction_sha,'report_sha256':rm.sha(dest/'page.md'),'model':raw.get('model'),'usage':raw.get('usage'),'review_status':'pending_independent_codex','checked':False}
   put(dest/'result.json',result);results.append(result);print(rid,n,'saved','suspects',len(flags),'model_issues',len(answer['issues']),flush=True)
  except Exception as e:
   fatal=dependency_error(e);put(dest/'error.json',{'type':type(e).__name__,'dependency':fatal,'error':str(e)[:400] if not fatal else fatal['reason']});results.append({**p,'error_type':type(e).__name__,'dependency':fatal,'checked':False})
   if fatal:break
  put(out/'summary.json',{'updated_at':stamp(),'version':a.run_version,'results':results,'full_source_fidelity_verified':False})
 put(out/'summary.json',{'updated_at':stamp(),'version':a.run_version,'results':results,'full_source_fidelity_verified':False})
if __name__=='__main__':main()
