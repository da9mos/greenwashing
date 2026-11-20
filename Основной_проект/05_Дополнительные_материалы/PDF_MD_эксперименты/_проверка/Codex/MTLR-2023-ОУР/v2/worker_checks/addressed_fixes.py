from pathlib import Path
import json,re,sys,hashlib,collections
# Reuse the shared converter and ordering adapter, without rerunning the batch.
code=Path('result/_проверка/refine.py').read_text().split('records=[];parts=[];doc=')[0]
exec(code)
records=json.load(open(base/'pages.json'))['pages'];report=Path('result/report.md').read_text();logs=[]
def replace_page(n,part):
 global report
 report=re.sub(r'<!-- pdf_page: '+str(n)+r' -->.*?(?=<!-- pdf_page: |\Z)',lambda _:part+'\n',report,flags=re.S)
 (base/'native_pages'/f'{n:04}.md').write_text(part)
# Explicitly restore the source-verified missing rightmost period on page 25.
n=25;doc=m.fitz.open(S['source_pdf']);page=doc[n-1];block_map.clear();font_map.clear();i=0
for bi,b in enumerate(page.get_text('rawdict')['blocks']):
 for l in b.get('lines',[]):
  for sp in l['spans']:
   for c in sp.get('chars',[]):block_map[i]=bi;font_map[i]=sp['font'];i+=1
class PageRepair:
 def get_text(self,*a,**kw):return page.get_text(*a,**kw)
 def find_tables(self,*a,**kw):
  xs=[616.7755,792.939,877.9785,962.073,1047.112,1135.416]
  grids=[[93.909,109.659,124.769,138.005,153.115],[192.707,208.457,222.630,236.804,251.914,267.024,282.134,297.245,312.355,327.465,342.576,357.686]]
  tables=[];holders=[]
  for ys in grids:
   finder=page.find_tables(clip=m.fitz.Rect(xs[0]-.1,ys[0]-.1,xs[-1]+.1,ys[-1]+.1),vertical_strategy='explicit',horizontal_strategy='explicit',vertical_lines=xs,horizontal_lines=ys)
   holders.append(finder);tables.extend(finder.tables)
  last=page.find_tables();holders.append(last);tables.extend(t for t in last.tables if t.bbox[1]>370)
  self.holders=holders
  return type('Tables',(),{'tables':tables})()
proxy=PageRepair();body,info=m.convert_page(proxy);soup=BeautifulSoup(body,'html.parser')
for el in soup.select('span.chart-code'):el.decompose()
body=str(soup).replace('\ue135','◀').replace('\ue136','▶').replace('\x08','')
part=(base/'native_pages'/'0025.md').read_text();tail=part[part.index('> Служебная пометка:'):];part='<!-- pdf_page: 25 -->\n<a id="pdf-page-25"></a>\n\n'+body+'\n\n'+tail
replace_page(25,part);records[24].update({k:info[k] for k in ['tables','ambiguous_cell_assignments','objects']})
records[24]['review_notes']='Сверены геометрия трёх таблиц и отсутствовавший столбец 2023; восстановлены все периоды по исходным глифам. Полная страница не сверена.'
logs.append({'page':25,'fix':'Восстановлены столбец 2023 и связи строк в таблицах выбросов посредством явно заданной по изображению сетки. Числа копировались из исходных глифов общим native_candidate.convert_page.'})
# Graphic checkmarks are absent from native text; visually transcribed in source column order.
masks={82:['111111101','111111101','111101101','011101101','111101101','011101101','111111101','111101101','010111101','011101111','111111111','111111111','111111111','111111111','111111111','011101111','011101111','111111101','111111101','011111101'],83:['011101101','011101111','011101101','111101101','111101101','011101101','000101101','010111101','000101101','010101111','010101111']}
for n,values in masks.items():
 part=(base/'native_pages'/f'{n:04}.md').read_text();soup=BeautifulSoup(part,'html.parser');tables=soup.find_all('table');header=tables[0].find('tr');rows=[];j=0
 for t in tables[1:]:
  for row in t.find_all('tr'):
   cells=row.find_all('td',recursive=False)
   if len(cells)==10:
    assert j<len(values)
    for cell,flag in zip(cells[1:],values[j]):
     assert not cell.get_text(strip=True)
     if flag=='1':cell.string='✓'
    j+=1
   rows.append(row)
 assert j==len(values),(n,j)
 merged=soup.new_tag('table');merged.append(header.extract())
 section=soup.new_tag('tr');td=soup.new_tag('td',colspan='10');td.string='МЕТАЛЛУРГИЧЕСКИЙ ДИВИЗИОН' if n==82 else 'ТРАНСПОРТНЫЙ ДИВИЗИОН';section.append(td);merged.append(section)
 for row in rows:merged.append(row.extract())
 tables[0].replace_with(merged)
 for t in tables[1:]:t.decompose()
 for p in soup.find_all('p'):
  if p.get_text(strip=True) in ['МЕТАЛЛУРГИЧЕСКИЙ ДИВИЗИОН','ТРАНСПОРТНЫЙ ДИВИЗИОН']:p.decompose()
 replace_page(n,str(soup));records[n-1]['review_notes']='Все графические отметки таблицы просмотрены и перенесены по строкам и девяти темам. Заголовок и тело сведены в единую таблицу. Полная страница не заявлена как checked.'
 logs.append({'page':n,'fix':'Восстановлены графические отметки ✓ в '+str(j)+' строках, пустые ячейки сохранены; объединены шапка и тело таблицы.'})
# Webdings/Wingdings characters are pictograms, not authorial text.
n=97;part=(base/'native_pages'/'0097.md').read_text();part=part.replace('<p>ý</p>','<p>🌐</p>').replace('<p>*</p>','<p>✉</p>').replace('<p>(</p>','<p>☎</p>');replace_page(n,part)
logs.append({'page':97,'fix':'Пиктограммы Webdings/Wingdings заменены читаемыми значками; видимые контакты сохранены.'})
# Clear source-mapping diagnostics only for the confirmed navigation codepoints.
for r in records:
 if r.get('unresolved_unicode'):
  r['unicode_resolution']='PUA E135/E136 — навигационные стрелки (подтверждено по изображениям); заменены ◀/▶. На стр. 7 отдельный управляющий код не является читаемым текстом; исключён.'
 r['review_status']='checked' if r['pdf_page'] in [1,98] else 'pending'
 r['conversion_status']='converted'
# Attach no false semantic approval to source-character accounting.
coverage=json.load(open(base/'native_coverage.json'));coverage['native_candidate_report_sha256']=coverage.pop('report_sha256',None);coverage['report_sha256']=hashlib.sha256(report.encode()).hexdigest();coverage['scope']='Исходный механический учёт символов сохранён; итог содержит документированные удаления кодов графических шрифтов, исправления структуры и визуальные дополнения. Учёт не доказывает семантическую точность.';coverage['pending_pages']=[r['pdf_page'] for r in records if r['review_status']=='pending'];coverage['semantic_source_review_completed']=False
Path('result/report.md').write_text(report);(base/'pages.json').write_text(json.dumps({'pages':records},ensure_ascii=False,indent=2)+'\n');(base/'native_coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n');(base/'addressed_fixes.json').write_text(json.dumps(logs,ensure_ascii=False,indent=2)+'\n')
print(logs)
