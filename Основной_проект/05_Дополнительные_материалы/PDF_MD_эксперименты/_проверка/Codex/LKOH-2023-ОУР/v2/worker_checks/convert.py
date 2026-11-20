import os,json,hashlib,shutil,re,time
from pathlib import Path
import pymupdf as fitz
import pymupdf4llm
pymupdf4llm.use_layout(False)
s=json.load(open('source.json')); doc=fitz.open(s['source_pdf']); idx=json.load(open(s['index'])); base=Path(s['index']).parents[3]
out=Path('result'); entries=[]
meta={'source_pdf':s['source_pdf'],'source_sha256':hashlib.sha256(Path(s['source_pdf']).read_bytes()).hexdigest(),'physical_pages':len(doc),'method':'PyMuPDF4LLM legacy, no layout model, pagewise; source images preserved','pages':entries}
for i,p in enumerate(doc):
 n=i+1; im=Path(s['index']).parent/f'page_{n:04}.png'; target=out/'assets'/im.name
 if im.exists(): shutil.copy2(im,target)
 raw=p.get_text(); (out/'_проверка/pages'/f'{n:04}.txt').write_text(raw)
 try:
  md=pymupdf4llm.to_markdown(doc,pages=[i],force_text=True,ignore_images=True,ignore_graphics=True,show_progress=False,margins=0,table_strategy='lines_strict')
 except Exception as e:
  md=raw; print(n,str(e),flush=True)
 (out/'_проверка/pages'/f'{n:04}.md').write_text(md)
 images=p.get_images(); blocks=p.get_text('dict')['blocks']; areas=[b for b in blocks if b['type']==1]; large=[b for b in areas if (b['bbox'][2]-b['bbox'][0])*(b['bbox'][3]-b['bbox'][1])>p.rect.get_area()*.35]
 e={'pdf_page':n,'printed_page_labels':None,'content_type':'text_with_graphics' if images or len(p.get_drawings()) else 'text','text_layer_chars':len(raw),'markdown_chars':len(md),'large_raster_regions':len(large),'conversion_status':'converted','review_status':'pending','issues':['Полная визуальная сверка страницы не выполнена; порядок колонок, ячейки таблиц и подписи графики требуют проверки.'],'source_image':f'assets/{im.name}'}
 entries.append(e); (out/'_проверка/pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2));print(n,len(raw),len(md),'large',len(large),flush=True)
 parts=['# Отчет об устойчивом развитии Группы «ЛУКОЙЛ»\n\n> Техническое примечание: рабочая версия конвертации. Статусы и ограничения постраничной сверки приведены в `_проверка/pages.json`. Изображения страниц служат визуальной опорой.\n']
 for ent in entries:
  j=ent['pdf_page'];parts.append(f'\n<!-- pdf_page: {j} -->\n<a id="pdf-page-{j}"></a>\n\n'+(out/'_проверка/pages'/f'{j:04}.md').read_text()+f'\n\n[Изображение исходной страницы {j}](assets/page_{j:04}.png)\n')
 (out/'report.md').write_text('\n'.join(parts))
