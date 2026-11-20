import sys,json,re,html,collections
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
from layout_extract import extract,clean
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
out=Path('result');ck=out/'_проверка';s=json.load(open('source.json'));d=pymupdf.open(s['source_pdf']);meta=json.load(open(ck/'pages.json'))
new=ck/'structured_pages';new.mkdir(exist_ok=True)
def norm(s):return re.sub(r'[^\w]+','',html.unescape(re.sub('<[^>]+>','',s))).lower()
for i,p in enumerate(d):
 n=i+1;text,tables=extract(p)
 rec=meta['pages'][i];rec['tables']=tables
 # Source labels read from the actual top-margin text, not offset arithmetic.
 labels=[]
 for b in p.get_text('dict')['blocks']:
  if b['type']==0:
   for l in b['lines']:
    if l['bbox'][3]<42:
     for sp in l['spans']:
      st=sp['text'].strip()
      if st.isdigit():labels.append(st)
 rec['printed_page_labels']=sorted(set(labels),key=lambda z:int(z))
 # Audit every complete native line below navigation for occurrence in output.
 missing=[];flat=norm(text)
 for b in p.get_text('dict')['blocks']:
  if b['type']!=0:continue
  for l in b['lines']:
   if l['bbox'][3]<42:continue
   st=clean(''.join(sp['text'] for sp in l['spans'])).strip()
   if len(norm(st))>=3 and norm(st) not in flat: missing.append({'bbox':l['bbox'],'text':st})
 rec['native_lines_not_found']=missing
 rec['issues']=['Полная построчная визуальная сверка по оригиналу не выполнена; порядок сложных блоков, сноски и подписи диаграмм требуют проверки.']
 if missing:
  text+='\n\n> Техническая пометка: следующие строки текстового слоя не удалось однозначно включить в структуру выше; их расположение требует сверки с изображением.\n\n'
  text+='\n\n'.join(m['text'] for m in missing)
  rec['issues'].append(f'В отдельный блок сохранено {len(missing)} строк, не найденных при контроле охвата; связи требуют сверки.')
 if n==1:
  text='# Отчет об устойчивом развитии 2024\n\nНОВАТЭК — 30 лет\n\nБольше доступной, надежной энергии\n\nНа благо общества'
 # Remove only navigation glyphs with established visible meaning.
 text=text.replace('\ue58a','↗').replace('\ue58b','↗')
 (new/f'{n:04}.md').write_text(text)
 rec['conversion_status']='converted';rec['review_status']='checked' if n==1 else 'pending';rec['markdown_chars']=len(text)
 if n==1:rec['issues']=[]
 if n in (2,3,4,104,121,123,129):rec['review_scope']='Выборочный осмотр изображения; полная построчная сверка не заявляется.'
 if n==1:rec['review_scope']='Обложка: визуально сверены название, год, девиз и логотип; графика сохранена.'
 rec['content_type']='разворот: текстовый слой, таблицы, графика' if tables else 'разворот: текстовый слой и графика'
 if n==123:rec['content_type']='смешанный разворот: три страницы заключения аудитора с текстовым слоем, подпись и печать'
 if n%10==0:print('structured',n,flush=True)
 (ck/'pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
parts=[]
for rec in meta['pages']:
 n=rec['pdf_page'];text=(new/f'{n:04}.md').read_text()
 if n==1:
  title,text=text.split('\n',1);parts.append(title+'\n\n> Рабочая конвертация. Все 129 физических страниц учтены. Полная визуальная сверка не выполнена; статусы и ограничения приведены в `_проверка/pages.json`. Изображения служат визуальной опорой.\n')
 parts.append(f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+text.strip())
 if n!=1:parts.append('> Техническая пометка: визуальная сверка страницы не завершена; структура сложных таблиц и графики требует проверки по изображению ниже.')
 # Keep all source images available and visible independently from transcription.
 parts.append(f'\n![Исходный разворот, физическая страница {n}](assets/page_{n:04}.png)\n')
 links=rec.get('links',[])
 # Retain annotation destinations in an explicit technical block, deduplicated.
 unique=[];seen=set()
 for l in links:
  dest=l.get('uri') or f'#pdf-page-{l["page"]}'
  label=re.sub(r'\s+',' ',l.get('text','')).strip() or ('Переход на физическую страницу '+str(l['page']) if 'page' in l else l['uri'])
  key=(label,dest)
  if key in seen:continue
  seen.add(key);label=label.replace('[','\\[').replace(']','\\]')
  unique.append(f'- [{label}](<{dest}>)')
 if unique:parts.append('<details>\n<summary>Ссылки из аннотаций PDF (технический блок)</summary>\n\n'+'\n'.join(unique)+'\n\n</details>\n')
(out/'report.md').write_text('\n\n'.join(parts))
print('report saved',len((out/'report.md').read_text()),'missing lines',sum(len(r['native_lines_not_found']) for r in meta['pages']))
