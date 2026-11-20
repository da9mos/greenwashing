import sys,json,re,importlib.util,hashlib,html
from pathlib import Path
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf
from bs4 import BeautifulSoup
root=Path.cwd(); source=json.load(open('source.json'))
tool=Path(source['source_pdf']).parent.parent/'tools/native_candidate.py'
spec=importlib.util.spec_from_file_location('native',tool);native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
doc=pymupdf.open(source['source_pdf']); orig=Path('result/report.md').read_text();split=re.split(r'<!-- pdf_page: (\d+) -->',orig); changes=[]
class FixedPage:
 def __init__(self,p):self.p=p
 def __getattr__(self,k):return getattr(self.p,k)
 def get_text(self,*a,**kw):
  data=self.p.get_text(*a,**kw)
  if a and a[0]=='rawdict':
   for b in data['blocks']:
    for l in b.get('lines',[]):
     for s in l['spans']:
      for c in s.get('chars',[]):
       if s['font']=='TatSymbol-Regular' and c['c'] in '1238':c['c']={'1':'→','2':'→','3':'↗','8':'↗'}[c['c']]
       if c['c']=='\x07':c['c']=''
  return data
for n in range(1,201):
 part=split[n*2];head=f'\n<a id="pdf-page-{n}"></a>\n\n';assert part.startswith(head)
 fixed=FixedPage(doc[n-1]);body,stats=native.convert_page(fixed)
 tail=part[len(head):]; cut=re.search(r'(?m)^> Служебная|^<details>',tail)
 suffix=tail[cut.start():] if cut else ''
 old=tail[:cut.start()].strip() if cut else tail.strip()
 if body.strip()!=old:changes.append({'page':n,'change':'Native body rebuilt with shared converter; TatSymbol font codes mapped to visible arrows; U+0007 formatting control removed when present.'})
 split[n*2]=head+body+'\n\n'+suffix
 if n%20==0:
  Path('result/_проверка/current_run/progress.json').write_text(json.dumps({'native_pages':n}));print(n,flush=True)
Path('result/report.md').write_text('# Интегрированный годовой отчет 2024\n\n> Служебная информация: рабочая конвертация всех 200 физических страниц. Полная постраничная сверка не завершена; статусы и ограничения — в `_проверка/pages.json`. Изображения служат опорой к тексту.\n\n'+''.join('<!-- pdf_page: '+split[i]+' -->'+split[i+1] for i in range(1,len(split),2)))
Path('result/_проверка/current_run/native_changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
print('done',len(changes))
