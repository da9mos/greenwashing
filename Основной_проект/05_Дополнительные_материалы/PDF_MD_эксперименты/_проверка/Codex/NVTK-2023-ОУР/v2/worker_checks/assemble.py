import sys,json,re,collections,html
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf
from bs4 import BeautifulSoup
pymupdf._layout_enabled=False
root=Path('result');check=root/'_проверка';s=json.load(open('source.json'));doc=pymupdf.open(s['source_pdf']);base=Path(s['index']).parent;meta=json.load(open(check/'pages.json'))
norm=lambda x:re.sub(r'[^\w]','',x).lower()
def count(x):return collections.Counter(norm(x))
def plain(x):return BeautifulSoup(x,'html.parser').get_text(' ')
report=['# Ответственность и развитие\n\nОтчет об устойчивом развитии 2023\n\n> **Техническая пометка. Рабочая версия.** Текст извлечён для всех 138 физических страниц. Полная сверка с оригиналом не завершена. Непроверенные страницы имеют статусы `converted/pending`; таблицы, колонки, сноски и подписи внутри графики требуют дальнейшего контроля. Изображения страниц служат визуальной опорой.\n']
for i,p in enumerate(doc):
 n=i+1;rec=meta['pages'][i];packet=json.load(open(base/f'page_{n:04}.json'));text=(check/'pages'/f'page_{n:04}.md').read_text();source=p.get_text()
 candidate=check/'pages'/f'tables_{n:04}.md';rec['table_reconstruction']='none'
 if candidate.exists():
  c=candidate.read_text();deficit=sum((count(source)-count(plain(c))).values())
  if deficit<=max(10,len(norm(source))*.005):
   text=c;rec['table_reconstruction']='coordinate_html';rec['issues'].append('Таблицы восстановлены по координатам линеек и текста; объединения и полная клеточная сверка остаются pending.')
  else:rec['issues'].append(f'Координатный табличный кандидат отклонён: дефицит {deficit} символов; сохранено полное текстовое извлечение.')
 if n==1:
  text='НОВАТЭК\n\nОтветственность и развитие\n\nОтчет об устойчивом развитии 2023\n';rec['review_status']='checked';rec['issues']=[];rec['review_scope']='Полная обложка визуально сверена; название и логотип прочитаны.'
 if n==2:
  text=text.replace('Международные\n','Международные\n\nGRI; SASB; TCFD — Task Force on Climate-related Financial Disclosures; ipieca; AccountAbility; TNFD — Taskforce on Nature-related Financial Disclosures.\n\nSustainability reporting guidance for the oil and gas industry — IPIECA/API/OGP.\n',1)
  rec['issues'].append('Названия стандартов в графических логотипах добавлены по изображению; весь разворот не сверен.')
 if n==4:
  text+='\n\n> **Техническая пометка:** подписи вертикальной оси матрицы (из текстового слоя):\n\nВоздействие Компании на тему\n\nОчень высокое; Высокое; Умеренное.\n'
  rec['issues'].append('Восстановлены пропущенные повёрнутые подписи вертикальной оси; точное положение требует визуальной сверки.')
 if n==37:
  text+='\n\n> **Техническая пометка:** повёрнутые подписи схемы (из текстового слоя):\n\nУстойчивость; Доступность.\n'
  rec['issues'].append('Восстановлены пропущенные повёрнутые подписи схемы; полная сверка схемы pending.')
 if n==133:
  text=(check/'pages'/'fixed_0133.md').read_text();rec['issues'].append('Исправлен порядок трёх вложенных страниц заключения: слева направо. Локальный OCR выполнен; полная посимвольная сверка не завершена.')
 if n in [1,2,133,138]:rec['ocr']='Tesseract rus+eng, psm 3; raw output in _проверка/pages/ocr_NNNN.txt'
 # Find substantive spans absent from both Markdown and coordinate tables. Do not infer lost words.
 if n!=1:
  rendered=norm(plain(text)); additions=[]
  for b in packet['text_blocks']:
   bt=b['text'].replace('\x07','').strip();bn=norm(bt)
   if len(bn)<15 or bn in rendered:continue
   # Skip expensive alignment when the full text already contains the block's characters.
   if sum((count(bt)-count(plain(text))).values())<8:continue
   # Ordered subsequence matching tolerates inserted Markdown while detecting skipped text.
   seq=__import__('difflib').SequenceMatcher(None,bn,rendered,autojunk=False)
   match=max((m.size for m in seq.get_matching_blocks()),default=0)
   if match<len(bn)*.5:
    # Character count audit first; do not append common text just because of layout changes.
    missing=sum((count(bt)-count(plain(text))).values())
    if missing>=8:additions.append(bt)
  if additions:
   text+='\n\n> **Техническая пометка:** следующие блоки текстового слоя не удалось уверенно разместить в структуре страницы; требуется сверка порядка.\n\n'+'\n\n'.join(additions)
   rec['issues'].append('Сохранены дополнительно блоки с неопределённым положением: '+str(len(additions)))
 rec['printed_labels']=[]
 for b in packet['text_blocks']:
  if b['bbox'][1]<45:
   for token in re.findall(r'(?<!\w)\d{1,3}(?!\w)',b['text']):
    if token not in rec['printed_labels']:rec['printed_labels'].append(token)
 rec['links']=[];destseen=set()
 for l in packet.get('links',[]):
  dest=l.get('uri') or l.get('target')
  if not dest:continue
  if dest.startswith('#') and not re.fullmatch(r'#pdf-page-(?:[1-9]|[1-9]\d|1[0-2]\d|13[0-8])',dest):
   rec['issues'].append('Неустановленный внутренний адрес: '+dest);continue
  label=' '.join(p.get_textbox(pymupdf.Rect(l['bbox'])).split()) or dest
  if l['bbox'][1]<50:continue # established navigation bar
  if (label,dest) in destseen:continue
  destseen.add((label,dest));rec['links'].append({'label':label,'destination':dest,'bbox':l['bbox']})
 text=re.sub(r'\n{4,}','\n\n\n',text)
 report.extend([f'\n<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n',text.strip()+'\n'])
 if rec['review_status']!='checked': report.append('\n> **Техническая пометка к странице:** полная сверка не завершена; колонки, ячейки таблиц, знаки сносок и подписи графики — pending.\n')
 report.append(f'\n![Физическая страница {n} — визуальная опора](assets/page_{n:04}.png)\n')
 if rec['links']:
  report.append('\n<details>\n<summary>Ссылки из аннотаций PDF — технический реестр страницы</summary>\n\n')
  for l in rec['links']:
   label=l['label'].replace('[','\\[').replace(']','\\]'); dest=l['destination'];report.append(f'- [{label}](<{dest}>)\n')
  report.append('\n</details>\n')
 rec['markdown_chars']=len(text);rec['character_deficit']=sum((count(source)-count(plain(text))).values());rec['possible_omitted_blocks']=[]
 (check/'pages'/f'final_{n:04}.md').write_text(text)
(root/'report.md').write_text('\n'.join(report))
meta['method']='PyMuPDF4LLM legacy, ignore_graphics=True; coordinate HTML reconstruction for selected ruled tables; local Tesseract on selected mixed pages'
meta['diagnostic_deviation']='One diagnostic Page.find_tables call automatically activated installed local layout component. Subsequently disabled layout and used geometric detection only. No downloads, external APIs or child agents.'
(check/'pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
print('pages',len(meta['pages']),'tables',sum(p['table_reconstruction']!='none' for p in meta['pages']),'chars',len((root/'report.md').read_text()))
print('deficits',[(p['pdf_page'],p['character_deficit']) for p in meta['pages'] if p['character_deficit']>10])
