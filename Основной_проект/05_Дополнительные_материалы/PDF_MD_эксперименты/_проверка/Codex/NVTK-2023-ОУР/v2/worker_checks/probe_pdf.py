import sys,json
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
s=json.load(open('source.json'));d=pymupdf.open(s['source_pdf'])
for i in [0,1,2,12,108,130,132]:
 p=d[i]; text=pymupdf4llm.to_markdown(d,pages=[i],force_text=True,ignore_images=True,ignore_graphics=True,show_progress=False)
 open(f'result/_проверка/pages/test_{i+1:04}.md','w').write(text)
 print(i+1,len(p.get_text()),len(text),text[:180].replace('\n',' '))
