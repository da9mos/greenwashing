import sys,json,re,collections
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
s=json.load(open('source.json')); doc=pymupdf.open(s['source_pdf']); root=Path('result/_проверка'); meta=json.load(open(root/'pages.json')); hdr=pymupdf4llm.IdentifyHeaders(doc)
for i,p in enumerate(doc):
 n=i+1; target=root/'pages'/f'page_{n:04}.md'; old=target.read_text(); (root/'pages'/f'geometric_candidate_{n:04}.md').write_text(old)
 t=pymupdf4llm.to_markdown(doc,pages=[i],hdr_info=hdr,ignore_images=True,ignore_graphics=True,force_text=True,show_progress=False)
 t=t.replace('\x07',''); target.write_text(t)
 rec=meta['pages'][i]; rec['markdown_chars']=len(t)
 norm=lambda x:re.sub(r'[^\w]','',x).lower()
 a=collections.Counter(norm(p.get_text())); b=collections.Counter(norm(t)); rec['character_deficit']=sum((a-b).values()); rec['possible_omitted_blocks']=[]
 rec['issues']=['Полная визуальная сверка страницы не выполнена; проверить колонки, таблицы, сноски и текст внутри графики.']
 (root/'pages.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
 print(n,len(t),rec['character_deficit'],flush=True)
