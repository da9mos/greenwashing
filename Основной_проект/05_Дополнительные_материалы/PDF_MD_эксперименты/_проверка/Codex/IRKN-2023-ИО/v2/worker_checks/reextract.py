import sys,json,re,collections
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
o=Path('result'); m=json.load(open(o/'_проверка/pages.json'));d=pymupdf.open(json.load(open('source.json'))['source_pdf'])
for i,p in enumerate(d):
 f=o/'_проверка/pages'/f'{i+1:04}.md';old=f.read_text();tail=old[old.find('\n\n> Техническая пометка: ниже приведено OCR'):] if '\n\n> Техническая пометка: ниже приведено OCR' in old else old[old.find('\n\n<!-- PDF link annotations -->'):] if '\n\n<!-- PDF link annotations -->' in old else old[old.find('\n\n<details>'):]
 md=pymupdf4llm.to_markdown(d,pages=[i],ignore_graphics=True,ignore_images=True,force_text=True,show_progress=False,table_strategy='lines_strict')
 md=re.sub(r'</?(?:mark|u)>','',md)
 f.write_text(md+tail)
 a=collections.Counter(re.findall(r'\w+',p.get_text().lower()));b=collections.Counter(re.findall(r'\w+',md.lower()));missing=a-b
 row=m['pages'][i];row['text_word_count']=sum(a.values());row['extraction_missing_tokens']=sum(missing.values())
 if sum(missing.values())>max(8,sum(a.values())*.025):
  # Preserve blocks omitted by converter, according to exact source text; retain page context.
  missblocks=[]
  for bl in p.get_text('blocks'):
   if bl[6]!=0:continue
   tokens=collections.Counter(re.findall(r'\w+',bl[4].lower()))
   if sum((tokens & missing).values())>=2:
    missblocks.append(bl[4].strip());missing-=tokens
  if missblocks:
   md+='\n\n> Техническая пометка: текстовые блоки, пропущенные автоматической разметкой; сохранены отдельно в порядке объектов PDF. Связи с графикой см. на изображении страницы.\n\n'+'\n\n'.join(missblocks)+'\n'
   row['issues'].append('Восстановлены текстовые блоки, пропущенные извлечением; их положение и связи требуют проверки.')
 f.write_text(md+tail)
 print(i+1,row['extraction_missing_tokens'],flush=True)
(o/'_проверка/pages.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
