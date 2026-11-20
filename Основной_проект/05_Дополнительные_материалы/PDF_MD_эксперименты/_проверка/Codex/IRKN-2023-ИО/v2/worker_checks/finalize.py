import json,re,hashlib,sys,collections,html
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf,pymupdf4llm
from markdown_it import MarkdownIt
pymupdf4llm.use_layout(False)
out=Path('result');m=json.load(open(out/'_проверка/pages.json'));src=json.load(open('source.json'));d=pymupdf.open(src['source_pdf'])
for i,p in enumerate(d):
 row=m['pages'][i];n=i+1
 nums=[]
 for b in p.get_text('dict')['blocks']:
  for line in b.get('lines',[]):
   for sp in line['spans']:
    if (sp['bbox'][1]>p.rect.height-45 or sp['bbox'][3]<45) and re.fullmatch(r'\s*\d+\s*',sp['text']):nums.append(sp['text'].strip())
 row['printed_page']=list(dict.fromkeys(nums)) or None
 row['source_image']=f'assets/page_{n:04}.png'
 row['visual_objects']=len(p.get_images())
 if row['review_status']=='pending':
  if len(p.get_drawings())>25:row['issues'].append('Векторная графика/цветные блоки: подписи извлечены, связи и численные ряды требуют полной сверки.')
 # keep exact text layer as audit evidence, not another transcription source
 (out/'_проверка/pages'/f'{n:04}_text_layer.txt').write_text(p.get_text())
 row['issues']=list(dict.fromkeys(row['issues']))
 row.pop('extraction_missing_tokens',None)
 # word-level audit separates markup and superscripts; not used as proof of correctness
 s=(out/'_проверка/pages'/f'{n:04}.md').read_text();plain=re.sub(r'<[^>]+>',' ',s)
 a=collections.Counter(re.findall(r'[^\W_]+',p.get_text().lower()));b=collections.Counter(re.findall(r'[^\W_]+',plain.lower()))
 row['coverage_audit']={'text_layer_tokens':sum(a.values()),'unmatched_tokens':dict(a-b),'note':'Механический контроль; надстрочные знаки и переносы меняют токенизацию. Не подтверждает визуальную точность.'}
m['review_summary']={'checked_pages':[r['pdf_page'] for r in m['pages'] if r['review_status']=='checked'],'pending_pages':[r['pdf_page'] for r in m['pages'] if r['review_status']=='pending'],'rendering':'Локальный HTML из Markdown; проверка структуры и скриншотов описана в protocol.md.'}
(out/'_проверка/pages.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
parts=['# Интегрированный годовой отчет АО «ИНК-Капитал» за 2023 год\n\n> Техническая пометка: рабочая конвертация 143 физических страниц. Полная сверка всего документа по оригиналу не выполнена. Статусы и нерешённые места перечислены в `_проверка/pages.json`. Сложные графические связи сохраняются также в изображениях страниц; отдельные такие связи ещё не проверены.\n']
for r in m['pages']:
 n=r['pdf_page'];parts.append(f'\n<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+(out/'_проверка/pages'/f'{n:04}.md').read_text())
report='\n'.join(parts);(out/'report.md').write_text(report)
assert [int(n) for n in re.findall(r'<!-- pdf_page: (\d+) -->',report)]==list(range(1,144))
missing=[]
for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',report):
 if target.startswith(('http:','https:','mailto:')):continue
 if target.startswith('#'):
  if f'id="{target[1:]}"' not in report:missing.append(target)
 elif not (out/target).exists():missing.append(target)
assert not missing,missing
render=MarkdownIt('commonmark',{'html':True}).enable('table').render(report)
page='<!doctype html><meta charset="utf-8"><style>body{font-family:Arial;max-width:1200px;margin:30px auto;line-height:1.45}table{border-collapse:collapse;display:block;overflow:auto;margin:1em 0}td,th{border:1px solid #bbb;padding:7px;min-width:80px}img{max-width:100%}details{margin:1em 0}a[id]{display:block;border-top:2px solid #ddd;margin:30px 0}blockquote{background:#f1f3f4;padding:10px}</style>'+render
(out/'_проверка/preview.html').write_text(page.replace('src="assets/','src="../assets/'))
print(json.dumps({'pages':len(m['pages']),'checked':m['review_summary']['checked_pages'],'converted':sum(r['conversion_status']=='converted' for r in m['pages']),'report_bytes':(out/'report.md').stat().st_size,'images':len(list((out/'assets').glob('*.png'))),'local_links_missing':missing},ensure_ascii=False))
