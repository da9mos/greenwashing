import pathlib,json,pymupdf
base=pathlib.Path('result/_проверка');out=[]
for f in sorted(base.glob('preview_[0-9]*.html')):
 story=pymupdf.Story(f.read_text(),user_css='body{font-size:13px;} td,th{padding:5px;border:1px solid #777;} table{border-collapse:collapse;}')
 dst=f.with_suffix('.pdf');writer=pymupdf.DocumentWriter(str(dst));more=True;count=0
 while more:
  dev=writer.begin_page(pymupdf.Rect(0,0,1200,1800));more,_=story.place(pymupdf.Rect(35,35,1165,1765));story.draw(dev);writer.end_page();count+=1
  if count>8:raise RuntimeError('Unexpected story overflow')
 writer.close();d=pymupdf.open(dst)
 for i,p in enumerate(d):p.get_pixmap(matrix=pymupdf.Matrix(1,1)).save(base/f'{f.stem}_render_{i+1}.png')
 out.append({'pdf_page':int(f.stem.split('_')[1]),'renderer':'PyMuPDF Story','render_pages':len(d),'rendered_pdf':dst.name})
(base/'render_checks.json').write_text(json.dumps({'method':'PyMuPDF Story HTML rendering of saved Markdown page bodies','browser_render_available':False,'browser_failure':'Headless Chrome aborted in sandbox. No permissions escalated.','pages':out},ensure_ascii=False,indent=2)+'\n')
print('rendered',len(out),'page bodies')
