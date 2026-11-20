from pathlib import Path
import sys,json,base64,hashlib,time,threading,argparse,concurrent.futures
import pymupdf
WORK=Path.cwd();P=WORK/'11_Проект_Сбер/3_итерация/greenwashing/03_итерация_3_пайплайн';O=P/'outputs/gazprom_2023_deepseek';BASE=P/'outputs/gazprom_2023_local_only'
sys.path.insert(0,str(WORK/'05_Инструменты/15_DeepSeek_API'));from deepseek_client import Client
for x in ['images','v1','v2','errors','baseline']:(O/x).mkdir(exist_ok=True)
REPORTS={'social':('gazprom_social_2023.pdf','social_final',136),'environment':('gazprom_environment_2023.pdf','environment_final',84)}
SYSTEM='''Ты выполняешь точную транскрипцию исходных изображений PDF в Markdown. Изображение — единственный источник. Не пересказывай, не сокращай, не исправляй стиль/цифры/названия, не добавляй причин и вычислений. Перенеси ВСЁ содержательное: заголовки, абзацы в порядке чтения по колонкам, все строки таблиц (включая первую и последнюю), формулы, подписи, сноски, диаграммы с названиями рядов, единицами и годами. Не переносить повторяющееся боковое навигационное меню. Колонтитулы и номера страниц сохрани в printed_pages. Сохраняй реальные названия и числа; не нормализуй проценты. 0, прочерк и пустая ячейка различаются. Сноски показывай <sup>N</sup>, не склеивай их с числами, не удаляй последнюю цифру без визуального основания. Не заполняй отсутствующие данные. Для таблиц допустим Markdown или HTML с colspan/rowspan; запрещены обрезанные таблицы, потерянные строки/годы/единицы/периметры, дополнительные пустые столбцы, объединение изменения и пояснения. Диаграммы переводи в таблицы чисел только если они читаются; укажи название каждой серии/компании, не дублируй рисунок как вторую таблицу. Различай одинаковое число в диаграмме и поясняющем тексте. Два изображения одной PDF-страницы читай сначала левое, затем правое; внутри каждого сохраняй порядок колонок. Надписи на сканах распознай полностью, не ограничивайся заголовком. Неразборчивое отмечай [НЕРАЗБОРЧИВО], не угадывай. До ответа проверь количество колонок и строк, последнюю строку, цифры, связи сноски и порядок абзацев. Ответ JSON object: {"pdf_page":integer,"printed_pages":string|null,"markdown":string,"problems":array of strings,"review_status":"converted"}. Даже после собственной проверки не ставь verified. Никаких ограждающих ```json. Не выводи рассуждения.'''

# Persist the model prompt and baseline once; independent pass does not read baseline text into API messages.
(O/'system_v1.txt').write_text(SYSTEM)
for report,(pdf,sub,n)in REPORTS.items():
 src=BASE/sub/'document_working.md';dst=O/'baseline'/f'{report}.md'
 if not dst.exists():dst.write_bytes(src.read_bytes())

lock=threading.Lock()
def process(report,n,version='v1',extra=''):
 pdf,sub,total=REPORTS[report];dest=O/version/f'{report}_{n:03d}.json'
 if dest.exists():return 'cached'
 t=time.monotonic();client=Client();client.config['timeout_seconds']=240
 d=pymupdf.open(P/'data/gazprom_parser_pilot'/pdf);page=d[n-1];w,h=page.rect.width,page.rect.height
 boxes=[pymupdf.Rect(0,0,w/2,h),pymupdf.Rect(w/2,0,w,h)]if w/h>1.2 else[page.rect]
 content=[{'type':'text','text':f'PDF-страница {n}. Изображений {len(boxes)}. Сохрани всё содержание. '+extra}];imh=[]
 for i,rect in enumerate(boxes):
  imagefile=O/'images'/f'{report}_{n:03d}_{i}.png'
  if not imagefile.exists():page.get_pixmap(matrix=pymupdf.Matrix(1.8,1.8),clip=rect).save(imagefile)
  b=imagefile.read_bytes();imh.append(hashlib.sha256(b).hexdigest());content.append({'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(b).decode(),'detail':'original'}})
 try:
  r=client.complete([{'role':'system','content':SYSTEM},{'role':'user','content':content}],max_tokens=14000,json_mode=True)
  answer=r['choices'][0]['message']['content'];a=json.loads(answer)
  if r['choices'][0].get('finish_reason')!='stop':raise ValueError('Truncated or non-stop answer')
  if a.get('pdf_page')!=n or not isinstance(a.get('markdown'),str):raise ValueError('Invalid response schema/page')
  result={'report':report,'pdf_page':n,'version':version,'response':a,'model':r.get('model'),'usage':r.get('usage'),'finish_reason':r['choices'][0].get('finish_reason'),'seconds':round(time.monotonic()-t,2),'image_sha256':imh,'system_sha256':hashlib.sha256(SYSTEM.encode()).hexdigest(),'extra_instruction':extra}
  dest.write_text(json.dumps(result,ensure_ascii=False,indent=2))
  with lock:print('DONE',report,n,'chars',len(a['markdown']),'seconds',result['seconds'],flush=True)
  return 'done'
 except Exception as e:
  if 'r' in locals(): (O/'errors'/f'{version}_{report}_{n:03d}_raw_response.json').write_text(json.dumps(r,ensure_ascii=False))
  (O/'errors'/f'{version}_{report}_{n:03d}.json').write_text(json.dumps({'report':report,'page':n,'error':str(e),'seconds':round(time.monotonic()-t,2)},ensure_ascii=False,indent=2))
  with lock:print('ERROR',report,n,type(e).__name__,str(e)[:150],flush=True)
  return 'error'

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--pilot',action='store_true');ap.add_argument('--workers',type=int,default=6);a=ap.parse_args()
 jobs=[('social',57),('social',115),('environment',13),('environment',24),('environment',40)]if a.pilot else[(r,i)for r,(_,_,n)in REPORTS.items()for i in range(1,n+1)]
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers)as ex:
  results=list(ex.map(lambda job:process(*job),jobs))
 print('BATCH', {k:results.count(k)for k in set(results)},flush=True)
