import sys,json,hashlib,shutil,re,time
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
s=json.loads(Path('source.json').read_text()); src=Path(s['source_pdf']); base=Path(s['index']).parents[3]; idx=json.loads(Path(s['index']).read_text()); out=Path('result'); d=pymupdf.open(src)
meta={'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'physical_pages':len(d),'method':'pymupdf4llm legacy; no layout model; local OCR where needed','pages':[]}
(out/'_проверка/source.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
for i,p in enumerate(d):
 n=i+1; item=idx['pages'][i]; image=base/item['image']; target=out/'assets'/f'page_{n:04}.png'; shutil.copy2(image,target)
 raw=p.get_text(); (out/'_проверка/pages'/f'{n:04}.txt').write_text(raw)
 try: md=pymupdf4llm.to_markdown(d,pages=[i],force_text=True,ignore_images=True,ignore_graphics=True,show_progress=False)
 except Exception as e: md=raw; print(n,str(e),flush=True)
 # Retain exact text as a separate layout-preserving transcription if extraction loses significant words.
 def words(t): return set(re.findall(r'[\w]+',t.lower()))
 a=words(raw); b=words(md); missing=a-b; coverage=1-len(missing)/max(1,len(a))
 issues=['Полная визуальная сверка текста, таблиц, сносок и графики не выполнена.']
 if coverage<.96:
  md+='\n\n<details><summary>Дополнительное извлечение текстового слоя (возможны повторы; порядок блоков требует сверки)</summary>\n\n<pre>'+__import__('html').escape(raw)+'</pre>\n</details>\n'; issues.append('Неполный охват основного извлечения; сохранён дополнительный текстовый слой.')
 md+='\n\n'+f'![Страница {n}: визуальная опора](assets/page_{n:04}.png)'+'\n'
 (out/'_проверка/pages'/f'{n:04}.md').write_text(md)
 rec={'pdf_page':n,'printed_page':None,'content_type':'text_and_graphics' if p.get_images() else 'text_or_vector','conversion_status':'converted','review_status':'pending','issues':issues,'text_chars':len(raw),'lexical_coverage':round(coverage,4),'source_image':f'assets/page_{n:04}.png'}
 meta['pages'].append(rec); (out/'_проверка/pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
 if n%10==0: print('saved',n,flush=True)
parts=['# Годовой отчет АО «ИНК-Капитал» за 2025 год\n\n> Техническое примечание: рабочая конвертация. Полная визуальная сверка не выполнена; статусы и нерешённые вопросы — в `_проверка/pages.json`. Изображения страниц дополняют текст.\n']
for n in range(1,len(d)+1): parts.append(f'\n<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+(out/'_проверка/pages'/f'{n:04}.md').read_text())
(out/'report.md').write_text('\n'.join(parts)); print('DONE',flush=True)
