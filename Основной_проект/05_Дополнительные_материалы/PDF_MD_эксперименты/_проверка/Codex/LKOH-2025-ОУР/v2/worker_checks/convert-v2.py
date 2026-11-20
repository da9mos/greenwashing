import json,hashlib,shutil,re,collections,time
from pathlib import Path
import pymupdf,pymupdf4llm
pymupdf4llm.use_layout(False)
base=Path.cwd();out=base/'result';check=out/'_проверка';assets=out/'assets';assets.mkdir(exist_ok=True)
s=json.load(open('source.json'));idx=Path(s['index']);reg=json.load(open(idx));root=idx.parents[3]
doc=pymupdf.open(s['source_pdf']);assert len(doc)==114
meta={'source_pdf':s['source_pdf'],'source_sha256':hashlib.sha256(Path(s['source_pdf']).read_bytes()).hexdigest(),'physical_pages':len(doc),'method':'PyMuPDF4LLM legacy, no layout model; native PDF text; page images from mechanical input registry','pages':[]}
(check/'source.json').write_text(json.dumps({k:v for k,v in meta.items() if k!='pages'},ensure_ascii=False,indent=2))
links=[]
for i,p in enumerate(doc):
 n=i+1;entry=reg['pages'][i];img=root/entry['image'];dest=assets/f'page_{n:04}.png';shutil.copyfile(img,dest)
 # Full-width infographics and chapter title pages retain their original layout.
 split=n>=9 and n!=114 and n not in [11,16,28,48,53,61]
 w=p.rect.width
 margins=[(0,65,0,25)] if n>1 else [(0,0,0,0)]
 if split:margins=[(0,65,w/2,25),(w/2,65,0,25)]
 chunks=[]
 for margin in margins:
  chunks.append(pymupdf4llm.to_markdown(doc,pages=[i],margins=margin,force_text=True,ignore_images=True,ignore_graphics=False,table_output='markdown',table_strategy='lines',show_progress=False))
 text='\n\n'.join(chunks)
 text=re.sub(r'\n{3,}','\n\n',text).strip()
 if n==1:text='# Отчет об устойчивом развитии Группы «ЛУКОЙЛ»\n\n2025\n\n35 лет в движении:\nэффективно, экологично, ответственно'
 # Preserve original links in a separate local block, never infer printed targets.
 pl=[]
 for l in p.get_links():
  label=p.get_textbox(l['from']).strip().replace('\n',' ')
  if not label:label='Переход из PDF'
  label=label.replace('[','\\[').replace(']','\\]')
  if l.get('uri'):pl.append(f'- [{label}]({l["uri"]})')
  elif l.get('page',-1)>=0:pl.append(f'- [{label}](#pdf-page-{l["page"]+1})')
 if pl:text+='\n\n<details><summary>Ссылки исходной страницы</summary>\n\n'+'\n'.join(dict.fromkeys(pl))+'\n\n</details>'
 issues=['Полная построчная и поячеечная сверка с оригиналом не выполнена.']
 if n in [112,113]:issues.append('Скан аудиторского заключения: OCR ещё не завершён.')
 item={'pdf_page':n,'printed_page_labels':[b[4].strip() for b in p.get_text('blocks') if b[1]>800 and re.fullmatch(r'\d+',b[4].strip())], 'content_type':'mixed' if p.get_images() else 'text_and_vector','layout':'spread' if split else 'full_width','conversion_status':'pending' if n in [112,113] else 'converted','review_status':'pending','issues':issues,'native_text_chars':len(p.get_text()),'markdown_chars':len(text),'image':f'assets/{dest.name}'}
 # Mechanical coverage comparison is diagnostic only.
 clip=p.rect+(0,65,0,-25) if n>1 else p.rect
 raw=p.get_text(clip=clip)
 def tokens(s):return re.findall(r'[\w]+',s.lower())
 a=collections.Counter(tokens(raw));b=collections.Counter(tokens(re.sub('<[^>]*>',' ',text)));missing=a-b
 item['native_word_coverage']=round(1-sum(missing.values())/max(1,sum(a.values())),4)
 item['missing_tokens']=dict(missing)
 (check/'pages-v2'/f'page_{n:04}.md').write_text(text+'\n')
 meta['pages'].append(item)
 (check/'pages-v2.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
 print(n,len(text),item['native_word_coverage'],flush=True)
