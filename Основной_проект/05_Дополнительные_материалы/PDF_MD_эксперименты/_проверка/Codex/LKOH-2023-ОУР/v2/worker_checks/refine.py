import json,re,subprocess,math,collections,concurrent.futures
from pathlib import Path
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
s=json.load(open('source.json'));pdf=s['source_pdf'];out=Path('result');d=pymupdf.open(pdf)
# Every physical page except the cover is a two-page spread, confirmed by overview.
def task(n):
 doc=pymupdf.open(pdf);p=doc[n-1];w,h=p.rect.width,p.rect.height;parts=[];issues=[];labels=[]
 for k in range(1 if n==1 else 2):
  clip=pymupdf.Rect(w*k/2 if n>1 else 0,0,w*(k+1)/2 if n>1 else w,h)
  fn=out/'_проверка/pages'/f'{n:04}-layout{k+1}.txt'
  subprocess.run(['pdftotext','-f',str(n),'-l',str(n),'-x',str(math.floor(clip.x0)),'-y','0','-W',str(math.ceil(clip.width)),'-H',str(math.ceil(h)),'-layout',pdf,str(fn)],check=True)
  layout=fn.read_text().replace('\f','').strip();raw=p.get_text(clip=clip)
  foot=p.get_text(clip=pymupdf.Rect(clip.x0,h-35,clip.x1,h)).splitlines()
  labels.extend(t.strip() for t in foot if re.fullmatch(r'\d{1,3}',t.strip()))
  if n==114 or (n==115 and k==0):
   text=(out/'_проверка/pages'/f'{n:04}-half{k+1}.txt').read_text().strip()
   text=re.sub(r'\bke t\b','kept',text)
   parts.append('> Техническое примечание: текст этой части получен локальным OCR; посимвольная сверка не завершена. Подпись и печать — на изображении страницы.\n\n'+text)
   issues.append('Текст растрового заключения извлечён Tesseract rus+eng; OCR требует визуальной вычитки.')
   continue
  dense=(66<=n<=84 or 87<=n<=113)
  if dense:
   parts.append('```text\n'+layout+'\n```');continue
  temp=pymupdf.open();tp=temp.new_page(width=clip.width,height=h);tp.show_pdf_page(tp.rect,doc,n-1,clip=clip)
  md=pymupdf4llm.to_markdown(temp,ignore_graphics=True,ignore_images=True,force_text=True,show_progress=False,margins=0)
  def tokens(t):return collections.Counter(re.findall(r'[\w]+',t.lower().replace('\u00ad','')))
  a,b=tokens(raw),tokens(md);missing=sum((a-b).values());total=sum(a.values())
  if total and missing/total>.08:
   parts.append('```text\n'+layout+'\n```');issues.append(f'Часть {k+1}: недостаточный охват Markdown-экстрактора; использовано полное позиционное текстовое представление.')
  else:
   parts.append(md.strip())
  temp.close()
 # links are saved directly from actual PDF annotations, with resolved physical targets.
 links=[]
 for l in p.get_links():
  if l.get('uri'):links.append(l['uri'])
  elif l.get('kind')==pymupdf.LINK_GOTO and l.get('page',-1)>=0:links.append('#pdf-page-'+str(l['page']+1))
 links=list(dict.fromkeys(links))
 text='\n\n'.join(parts)
 if links:
  text+='\n\n<details><summary>Ссылки и переходы из аннотаций PDF (технический перечень)</summary>\n\n'+'\n'.join(f'- [Переход на физическую страницу {x.split("-")[-1]}]({x})' if x.startswith('#') else f'- <{x}>' for x in links)+'\n\n</details>\n'
 (out/'_проверка/pages'/f'{n:04}.md').write_text(text)
 doc.close();return n,labels,issues,len(text)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for n,labels,issues,length in pool.map(task,range(1,116)):
  (out/'_проверка/pages'/f'{n:04}.meta.json').write_text(json.dumps({'printed_page_labels':labels or None,'issues':issues,'markdown_chars':length},ensure_ascii=False,indent=2))
  print(n,length,flush=True)
