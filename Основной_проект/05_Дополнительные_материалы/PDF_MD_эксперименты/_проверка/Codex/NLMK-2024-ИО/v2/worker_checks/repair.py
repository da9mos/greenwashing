from pathlib import Path
import sys,json,re,hashlib,importlib.util,collections
cfg=json.load(open('source.json'))
tool=Path(cfg['source_pdf']).parent.parent/'tools/native_candidate.py'
spec=importlib.util.spec_from_file_location('native',tool);native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
text=tool.read_text();start=text.index('def convert_page(');end=text.index('\ndef source_links',start)
fn=text[start:end]
needle='        values = {rect: [] for rect in positions}'
insert='''        # Source-reviewed GRI boundaries: indicator, printed reference, comment.
        refined = {}
        for rect, slots in positions.items():
            left = table.bbox[0]
            if abs(rect[0] - (left + 72.992)) < 1 and rect[2] > left + 500:
                cuts = [rect[0], left + 294.1, left + 367.1, rect[2]]
                for a, b in zip(cuts, cuts[1:]):
                    refined[(a, rect[1], b, rect[3])] = slots
            else:
                refined[rect] = slots
        positions = refined
'''
fn=fn.replace(needle,insert+needle)
exec(fn,native.__dict__)
doc=native.fitz.open(cfg['source_pdf'])
path=Path('result/report.md');raw=Path('result/_проверка/report.native-original.md').read_text();parts=re.split(r'<!-- pdf_page: (\d+) -->',raw);pages={int(parts[i]):parts[i+1] for i in range(1,len(parts),2)}
changes=[]
for n in range(111,116):
 body,diag=native.convert_page(doc[n-1])
 # Keep original links and full-page reference; replace only the mechanically rendered body.
 old=pages[n];tail=old[old.index('> Служебная информация: ссылки'):] if '> Служебная информация: ссылки' in old else old[old.index('<details>'):]
 for h in ['Стандарт GRI','Показатель GRI','Стр.','Комментарий']:
  body=body.replace('<p>'+h+'</p>','')
 body=body.replace('<table>','<table>\n<thead><tr><th>Стандарт GRI</th><th>Показатель GRI</th><th>Стр.</th><th>Комментарий</th></tr></thead>')
 pages[n]=f'\n<a id="pdf-page-{n}"></a>\n\n'+body+'\n\n'+tail
 changes.append({'page':n,'change':'GRI: split detector-merged indicator/reference/comment cells at source-reviewed x boundaries; retained source row spans and original glyphs','native_accounting':{k:v for k,v in diag.items() if k!='objects'}})
ocrpages=[]
for n,t in pages.items():
 if 'точность OCR не подтверждена.' in t:
  t,count=re.subn(r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\.\n\n.*?(?=> Служебная информация: ссылки|<details>)','',t,flags=re.S)
  pages[n]=t;ocrpages.append(n);changes.append({'page':n,'change':'Removed unverified OCR overlay: duplicate native words, icon/decorative false positives and TSV metadata; image reviewed, native body retained.'})
for n,t in pages.items():
 controls=t.count('\x07');bullets=t.count('\uf0b7')
 if controls or bullets:changes.append({'page':n,'change':'Source-font cleanup','removed_control_BEL':controls,'mapped_symbol_bullet':bullets})
 pages[n]=t.replace('\x07','').replace('\uf0b7','•')
 # Empty native lines carry no source text.
 pages[n]=re.sub(r'<p>\s*(?:<sup>\s*</sup>)?\s*</p>\s*','',pages[n])
# Cover independently read from image.
pages[1]='\n<a id="pdf-page-1"></a>\n\n<p>НЛМК</p>\n\n<p>ГОДОВОЙ ОТЧЕТ 2024</p>\n\n'+pages[1][pages[1].index('<details>'):]
changes.append({'page':1,'change':'Visually transcribed logo НЛМК; restored space between ОТЧЕТ and 2024.'})
# The contents is read by sections, not by interleaving the two columns.
toc=[('О Компании',[(6,'Об Отчете',4),(8,'Обращение руководства',5),(10,'Обзор бизнеса',6),(16,'Управление устойчивым развитием',9),(25,'Процесс определения существенных тем',13)]),('Охрана окружающей среды',[(28,'Изменение климата',15),(44,'Энергоэффективность',23),(56,'Охрана окружающей среды',29)]),('Социальное партнерство',[(94,'Диалог с заинтересованными сторонами',48),(102,'Взаимодействие с поставщиками и подрядчиками',52),(110,'Соблюдение прав человека',56),(116,'Наши сотрудники',59),(144,'Охрана труда и промышленная безопасность',73),(158,'Развитие местных сообществ',80)]),('Корпоративное управление',[(168,'Система корпоративного управления',85),(186,'Комплаенс и корпоративная этика',94),(198,'Контроль деятельности и управление рисками',100),(210,'Внутренний аудит',106),(214,'Независимый аудитор',108)])]
# Targets are taken from original PDF link annotations, verified below, never from an offset.
links=doc[1].get_links();dest={}
for l in links:
 if str(l.get('page','')).isdigit():
  label=doc[1].get_textbox(l['from']).replace('\x07','').strip()
  dest[int(l['page']) if isinstance(l['page'],str) else l['page']+1]=label
Path('result/_проверка/toc_source_links.json').write_text(json.dumps(dest,ensure_ascii=False,indent=2))
b='\n<a id="pdf-page-2"></a>\n\n<p>ГОДОВОЙ ОТЧЕТ 2024</p>\n\n## Содержание\n\n'
for title,items in toc:
 b+='### '+title+'\n\n'
 for printed,label,target in items:
  assert target in dest,(target,dest)
  b+=f'- {printed} — [{label}](#pdf-page-{target})\n'
 b+='\n'
b+='### Приложения\n\n<p>3</p>\n\n'+pages[2][pages[2].index('<details>'):];pages[2]=b
changes.append({'page':2,'change':'Reassembled contents by source section and associated each printed page number with its title; targets verified using original PDF annotations.'})
# Page 27: chart has exact printed values; preserve their year/series association.
t=pages[27]
a=t.index('<p>72,2%</p>');z=t.index('<p>Реализованные проекты',a)
chart='''<table>
<thead><tr><th>Год</th><th>Выработка собственной электроэнергии, МВт</th><th>Доля выработки собственной электроэнергии на вторичных топливных газах</th></tr></thead>
<tbody>
<tr><td>2020</td><td>480,2</td><td>72,2%</td></tr>
<tr><td>2021</td><td>489,2</td><td>77,2%</td></tr>
<tr><td>2022</td><td>486,8</td><td>80,6%</td></tr>
<tr><td>2023</td><td>488,3</td><td>81,9%</td></tr>
<tr><td>2024</td><td>453,8</td><td>83,2%</td></tr>
</tbody></table>

'''
pages[27]=t[:a]+chart+t[z:]
changes.append({'page':27,'change':'First chart: associated printed year, generation value and percentage in an explicit table after source-image comparison.'})
# Keep working-copy limitations visible, per-page, without altering source prose.
notes={n:'Полная сверка текста, порядка чтения, таблиц и графики по оригиналу не завершена; статус страницы — converted / pending.' for n in range(1,173)}
notes[1]=''
notes[2]=''
notes[109]=''
for n in range(111,116):notes[n]+=' Столбцы индекса GRI восстановлены; требуется полная построчная сверка и проверка продолжений.'
notes[169]+=' Таблицы финансового приложения содержат слитые числовые колонки; связи значений требуют восстановления и сверки.'
header='# ГОДОВОЙ ОТЧЕТ 2024\n\n> Служебная информация: рабочая версия полной конвертации 172 физических страниц. Полная сверка по оригиналу не завершена. Ограничения приведены на страницах и в `_проверка/pages.json`.\n\n'
out=header
for n in range(1,173):
 t=pages[n]
 if notes[n]:t=t.replace(f'<a id="pdf-page-{n}"></a>',f'<a id="pdf-page-{n}"></a>\n\n> Служебная пометка: '+notes[n],1)
 out+=f'<!-- pdf_page: {n} -->'+t+'\n\n'
path.write_text(out)
Path('result/_проверка/changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
print('Saved',len(out),'characters;',len(changes),'change records; OCR pages',ocrpages)
