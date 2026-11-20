from pathlib import Path
import json,re
code=Path('result/_проверка/refine.py').read_text().split('records=[];parts=[];doc=')[0];exec(code)
records=json.load(open(base/'pages.json'))['pages'];doc=m.fitz.open(S['source_pdf']);report=Path('result/report.md').read_text();log=[]
for n in [6,7,9,31,58,65,76]:
 page=doc[n-1];block_map.clear();font_map.clear();i=0
 for bi,b in enumerate(page.get_text('rawdict')['blocks']):
  for l in b.get('lines',[]):
   for sp in l['spans']:
    for c in sp.get('chars',[]):block_map[i]=bi;font_map[i]=sp['font'];i+=1
 class DiagramPage:
  def get_text(self,*a,**kw):return page.get_text(*a,**kw)
  def find_tables(self,*a,**kw):return type('Tables',(),{'tables':[]})()
 body,info=m.convert_page(DiagramPage());soup=BeautifulSoup(body,'html.parser')
 for e in soup.select('span.chart-code'):e.decompose()
 body=str(soup).replace('\ue135','◀').replace('\ue136','▶').replace('\x08','')
 part=(base/'native_pages'/f'{n:04}.md').read_text();tail=part[part.index('> Служебная пометка:'):]
 part=f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n'+body+'\n\n'+tail
 report=re.sub(r'<!-- pdf_page: '+str(n)+r' -->.*?(?=<!-- pdf_page: |\Z)',lambda _:part+'\n',report,flags=re.S)
 (base/'native_pages'/f'{n:04}.md').write_text(part)
 r=records[n-1];r['original_ambiguous_cell_assignments']=r['ambiguous_cell_assignments'];r.update({k:info[k] for k in ['tables','ambiguous_cell_assignments','objects']});r['issues']=['Полная сверка текста и чисел не завершена.','Диаграмма/схема: текстовые подписи сохранены; связи подписей с объектами и рядами требуют подробной визуальной сверки. Исходное изображение сохранено.'];r['review_notes']='Ложная таблица, построенная детектором из элементов схемы, удалена. Все исходные текстовые глифы сохранены; коды шрифта Chartwell исключены как графика.'
 log.append({'page':n,'fix':'Отклонено ложное распознавание схемы/диаграммы как таблицы. Текст перенесён общим native_candidate с отключением табличного детектора только для этой страницы.'})
for n in [12,63]:
 r=records[n-1];r['issues'].append('Есть неоднозначные связи ячеек: детектор таблиц захватил сложную вёрстку. Нужна построчная сверка таблицы с исходным изображением.')
 part=(base/'native_pages'/f'{n:04}.md').read_text();part=part.replace('> Служебная пометка:','> Служебная пометка: структура ячеек этой сложной таблицы не подтверждена; используйте исходное изображение для проверки связей.\n\n> Служебная пометка:',1)
 report=re.sub(r'<!-- pdf_page: '+str(n)+r' -->.*?(?=<!-- pdf_page: |\Z)',lambda _:part+'\n',report,flags=re.S)
 (base/'native_pages'/f'{n:04}.md').write_text(part)
Path('result/report.md').write_text(report);(base/'pages.json').write_text(json.dumps({'pages':records},ensure_ascii=False,indent=2)+'\n');(base/'diagram_fixes.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n')
print(log)
