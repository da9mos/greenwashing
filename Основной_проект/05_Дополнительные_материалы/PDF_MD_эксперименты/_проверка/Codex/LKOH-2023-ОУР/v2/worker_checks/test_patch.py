from pathlib import Path
import types,sys,json,pymupdf
import pymupdf4llm
pymupdf4llm.use_layout(False)
src=Path('/private/tmp/sber-pdf-libs/pymupdf4llm/helpers/pymupdf_rag.py').read_text().replace('clusters = page.cluster_drawings(drawings=paths)','paths = []  # Preserve vector labels as text; tables already detected.\n        clusters = []')
m=types.ModuleType('local_rag');sys.modules[m.__name__]=m;exec(compile(src,'local_rag','exec'),m.__dict__)
d=pymupdf.open(json.load(open('source.json'))['source_pdf'])
for n in [3,15,90]:
 text=m.to_markdown(d,pages=[n-1],ignore_graphics=False,ignore_images=True,force_text=True,show_progress=False)
 Path(f'result/_проверка/patched{n}.md').write_text(text);print(n,len(text))
