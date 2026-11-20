import json,re,shutil,sys,collections,html
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-diff-libs','/private/tmp/sber-pdf-libs']
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
out=Path('result');check=out/'_проверка';state=json.loads((check/'pages.json').read_text());stats={r['pdf_page']:r for r in json.loads((check/'refine-stats.json').read_text())}
shutil.copy2(out/'report.md',check/'report-first-pass.md')
chunks=[]
for row in state['pages']:
 n=row['pdf_page']; old=(check/'pages'/f'{n:04}.md').read_text(); bodypath=check/'refined'/f'{n:04}.md'
 start=f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'
 note='> **Примечание к конвертации:** рабочая транскрипция; полная сверка страницы по оригиналу не завершена. Изображение сохраняет исходную вёрстку и графику.\n\n'
 if bodypath.exists():
  body=bodypath.read_text();row['printed_page_label']=stats[n]['printed_page_label'];row.pop('printed_page_label_note',None)
  row['reading_order']='левая полоса, затем правая; внутри полосы — эвристика колонок pymupdf4llm'
  if '<details>' in old: body+='\n\n'+old[old.index('<details>'):old.index('</details>')+10]
 else:
  body=old.split('\n\n',2)[-1].rsplit('\n\n![Оригинал',1)[0]
 layoutpath=check/'layout-tables'/f'{n:04}.md'
 if layoutpath.exists():
  body=layoutpath.read_text()
  if '<details>' in old: body+='\n\n'+old[old.index('<details>'):old.index('</details>')+10]
  row['table_representation']='fixed-width text from pdftotext -layout; left sheet then right sheet'
  row['issues'].append('Таблицы и соседние блоки сохранены моноширинным текстом с выравниванием столбцов. Объединения ячеек и знаки сносок не полностью сверены.')
  note='> **Примечание к конвертации:** рабочая версия. Таблицы и соседние блоки ниже переданы моноширинным текстом с исходным расположением строк и столбцов; сначала левая полоса, затем правая. Полная сверка не завершена.\n\n'
 if n==1:
  body='РОСНЕФТЬ\n\n# ОДНА КОМАНДА – ОБЩИЕ ЦЕЛИ\n\nОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ 2023'
  row['review_status']='checked';row['issues']=[];row['review_scope']='Визуально сверены логотип и издательский текст обложки; фото сохранено.'
  note=''
 if n==111:
  body='#10\n\n# ПРИЛОЖЕНИЯ\n\nРОСНЕФТЬ'
  row['issues']=['Заголовок прочитан по изображению; полная визуальная проверка страницы не выполнена.']
 if n==112:
  a=(check/'pages/0112-scan-0.txt').read_text();b=(check/'pages/0112-scan-1.txt').read_text()
  eng=a[a.index('TSATR -'):a.index('www.bl.ru')+len('www.bl.ru')];a=a.replace(eng,'');a=a.replace('НОВЫЕ ВЫЗОВЫ',eng+'\n\nНОВЫЕ ВЫЗОВЫ',1)
  sig='Н.Г. Старыгина\nПартнер\nОбщество с ограниченной ответственностью'
  b=b.replace(sig,'').replace('Стр. 2\n','');b=b.replace('«Центр аудиторских технологий',sig+'\n«Центр аудиторских технологий',1)
  a=a.replace('Россия, 15035, Москва','Россия, 115035, Москва')
  body='## Заключение независимого практикующего специалиста по заданию, обеспечивающему уверенность, в отношении существенных показателей деятельности, включенных в Отчет об устойчивом развитии ПАО «НК «Роснефть» за 2023 год\n\n'+a+'\n\n'+b
  body=re.sub(r'^>\s*(?:—\s*)?', '- ',body,flags=re.M)
  row['content_type']='mixed: title text layer and two scanned audit pages';row['conversion_status']='converted';row['review_status']='pending';row['issues']=['Тело обеих сканированных полос распознано Tesseract rus+eng, 216 dpi. Исправлены порядок английского блока реквизитов и подписи, почтовый индекс. Полная посимвольная сверка OCR по оригиналу не выполнена; возможны ошибки символов, переносов, мелких реквизитов и маркера заверяемых показателей.']
  note='> **Примечание к конвертации:** тело заключения ниже получено локальным OCR. Полная сверка распознавания не завершена; спорные символы и реквизиты требуют проверки по сохранённому оригиналу.\n\n'
 if n==134:
  body='';row['content_type']='photographic back cover';row['issues']=['Фотография сохранена; надписи внутри фотографии не считаются текстом тела. Полная визуальная сверка не выполнена.']
 chunk=start+note+body.strip()+f'\n\n![Оригинал физической страницы {n}](assets/page_{n:04}.png)\n'
 (check/'pages'/f'{n:04}.final.md').write_text(chunk);chunks.append(chunk)
 row['extracted_markdown_chars']=len(body)
report='# ОДНА КОМАНДА – ОБЩИЕ ЦЕЛИ\n\nОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ 2023\n\n'+ '\n\n'.join(chunks)
(out/'report.md').write_text(report);(check/'pages.json').write_text(json.dumps(state,ensure_ascii=False,indent=2))
md=MarkdownIt('commonmark',{'html':True}).enable('table'); rendered=md.render(report)
htmltext='<!doctype html><html lang="ru"><meta charset="utf-8"><title>Конвертация отчета</title><style>body{font:16px/1.5 sans-serif;max-width:1400px;margin:32px auto}img{max-width:100%}table{display:block;overflow:auto;border-collapse:collapse}td,th{border:1px solid #bbb;padding:5px}blockquote{color:#666}pre{overflow:auto;max-width:100%;font-size:13px}</style><body>'+rendered+'</body></html>'
(check/'preview.html').write_text(htmltext.replace('src="assets/','src="../assets/'))
soup=BeautifulSoup(rendered,'html.parser');missing=[];badanchors=[];ids={x.get('id') for x in soup.find_all(id=True)}
for tag in soup.find_all(['img','a']):
 link=tag.get('src') or tag.get('href','')
 if link.startswith('#') and link[1:] not in ids:badanchors.append(link)
 elif link and not re.match(r'^(?:https?:|mailto:|tel:|#)',link) and not (out/link).exists():missing.append(link)
markers=[int(n) for n in re.findall(r'<!-- pdf_page: (\d+) -->',report)]
validation={'page_markers':len(markers),'pages_in_order':markers==list(range(1,135)),'registry_pages':len(state['pages']),'source_page_images':len(list((out/'assets').glob('page_*.png'))),'missing_local_targets':missing,'missing_anchors':badanchors,'html_tables':len(soup.find_all('table')),'review_status_counts':dict(collections.Counter(r['review_status'] for r in state['pages'])),'rendered_html':'preview.html','visual_render_review':'pending'}
(check/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2));print(validation)
