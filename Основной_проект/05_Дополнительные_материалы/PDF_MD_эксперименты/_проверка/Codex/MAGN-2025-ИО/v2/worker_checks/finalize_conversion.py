import sys,json,html,re,importlib.util,inspect,hashlib,unicodedata,collections
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs');sys.path.insert(0,str(Path('result/_проверка').resolve()))
import fitz
from table_geometry import Proxy
source=json.loads(Path('source.json').read_text());tool=Path(source['index']).parents[3]/'tools/native_candidate.py';spec=importlib.util.spec_from_file_location('native',tool);native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
# Fix shared helper's assumption that every link page is an integer; retained destinations are source annotations.
src=inspect.getsource(native.source_links).replace("0 <= link.get('page', -1) < page_count", "isinstance(link.get('page', -1), int) and 0 <= link.get('page', -1) < page_count")
exec(src,native.__dict__)
doc=fitz.open('result/_проверка/font_working.pdf');names=doc.resolve_names();base=Path('result/_проверка');records=json.loads((base/'previous_reports/native_pages.json').read_text())['pages'];parts=[];fixes=[];geometry=[]
class FixedProxy(Proxy):
 def __init__(self,page,n):super().__init__(page);self.n=n;self.controls=[]
 def get_text(self,*args,**kwargs):
  data=self.page.get_text(*args,**kwargs)
  if args and args[0]=='rawdict':
   trace={(round(c[2][0],2),round(c[2][1],2)):chr(c[0]) for sp in self.page.get_texttrace() for c in sp['chars']}
   for b in data['blocks']:
    for l in b.get('lines',[]):
     for s in l['spans']:
      for c in s['chars']:
       if unicodedata.category(c['c'])=='Cc':
        new=trace.get(tuple(round(v,2) for v in c['origin']))
        if new and unicodedata.category(new)!='Cc' and new!='�':self.controls.append({'from':ord(c['c']),'to':new,'origin':c['origin']});c['c']=new
  return data
 def find_tables(self,**kwargs):
  if self.n==32:
   class Obj:pass
   t=Obj();t.bbox=(60,147,1860,1040);xs=[60,192,391,599,874,1053,1253,1433,1860];ys=[147,205,587,1040];t.rows=[]
   for ri in range(3):
    row=Obj();row.cells=[]
    for ci in range(8):
     if ri==2 and ci in [0,2,3,4,5]:row.cells.append(None)
     else:row.cells.append((xs[ci],ys[ri],xs[ci+1],1040 if ri==1 and ci in [0,2,3,4,5] else ys[ri+1]))
    t.rows.append(row)
   r=Obj();r.tables=[t];self.changes=[{'manual_source_geometry':'8 columns; shared cells and two initiatives; source image reviewed'}];return r
  return super().find_tables(**kwargs)
for n,page in enumerate(doc,1):
 proxy=FixedProxy(page,n);body,info=native.convert_page(proxy);record=records[n-1]
 if n in [278,279,280,281]:body+='\n\n'+(base/f'ocr/corrected_{n}.md').read_text()
 if n==1:body='<p>МАГНИТОГОРСКИЙ МЕТАЛЛУРГИЧЕСКИЙ КОМБИНАТ</p>\n\n<p>ГОДОВОЙ ОТЧЕТ</p>\n\n<p>2025</p>\n\n<p>mmk.ru</p>'
 links,unresolved=native.source_links(page,names,len(doc));
 # Annotation captions use the same phantom spacing controls on some CFF pages.
 links=''.join(' ' if unicodedata.category(c)=='Cc' and c not in '\n\t\r' else c for c in links)
 body+=links
 issues=[]
 if info['unresolved_unicode']:issues.append('Остаются неоднозначные символы текстового слоя; требуется сверка с изображением.')
 if info['ambiguous_cell_assignments']:issues.append('Неоднозначное распределение глифов по ячейкам; исходная геометрия и изображения сохранены.')
 if unresolved:issues.append('Не разрешены отдельные назначения ссылок PDF.');record['unresolved_source_links']=unresolved
 if n in [278,279,280,281]:issues.append('Текст сканов добавлен после OCR и визуального чтения; мелкие надписи, адреса и отдельные цифры требуют дополнительной проверки.');record['ocr_body_processed']=True;record['ocr_verified']=False
 if proxy.changes:issues.append('Сетка таблицы дополнена по сегментам исходных линий; полная сверка ячеек не завершена.');geometry.append({'pdf_page':n,'changes':proxy.changes})
 if n!=1:issues.append('Полная постраничная сверка порядка чтения, таблиц и графики по оригиналу не завершена.')
 record.update(info);record.update({'conversion_status':'converted','review_status':'checked' if n==1 else 'pending','issues':issues,'semantic_source_review_completed':n==1,'verification_scope':'Cover fully read visually' if n==1 else 'Mechanical glyph transfer; font repair and diagnostic/source checks, not full-page acceptance','source_visual_inspected':n in [1,32,278,279,280,281,308,312,315,317,318,320,321,371]})
 if proxy.controls:fixes.append({'pdf_page':n,'controls':proxy.controls})
 if n!=1:
  notice='> Служебная пометка: рабочая транскрипция; полная сверка этой страницы по оригиналу не завершена.'
  if info['unresolved_unicode']:notice+=' Неоднозначные символы сверяйте с изображением страницы.'
  if info['ambiguous_cell_assignments']:notice+=' Требуется проверка связей ячеек таблицы.'
  body=notice+'\n\n'+body
 parts.append(f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n{body}\n\n<details>\n<summary>Источник: PDF-страница {n}</summary>\n\n![Полная исходная страница {n}](assets/page_{n:04d}.png)\n\n</details>')
 (base/'pages.json').write_text(json.dumps({'pages':records},ensure_ascii=False,indent=2))
 if n%25==0:print(n,flush=True)
Path('result/report.md').write_text('# ГОДОВОЙ ОТЧЕТ\n\n'+'\n\n'.join(parts)+'\n')
(base/'control_repairs.json').write_text(json.dumps(fixes,ensure_ascii=False,indent=2));(base/'table_geometry_repairs.json').write_text(json.dumps(geometry,ensure_ascii=False,indent=2))
print('DONE',len(parts),'unicode',sum(r['unresolved_unicode'] for r in records),'geometry',len(geometry))
