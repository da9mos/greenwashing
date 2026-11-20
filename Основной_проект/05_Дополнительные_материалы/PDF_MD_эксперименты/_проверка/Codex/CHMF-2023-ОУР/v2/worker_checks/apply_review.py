from pathlib import Path
import json,re,hashlib,html
root=Path(__file__).resolve().parents[1]
p=root/'report.md'; s=p.read_text(); parts=re.split(r'<!-- pdf_page: (\d+) -->',s)
changes=[]
def replace(n,body):
 old=parts[2*n]
 source=old[old.index('<details>'):]
 parts[2*n]=f'\n<a id="pdf-page-{n}"></a>\n\n'+body+'\n\n'+source
 changes.append({'pdf_page':n,'change':'Reconstructed page body from source image; retained original page image.'})
def table(rows):
 return '\n'.join(['| Показатель | Прим. | 2023 | 2022 |','| --- | --- | --- | --- |']+['| '+' | '.join(r)+' |' for r in rows])
replace(1,'# Новые цели на пути к устойчивой металлургии будущего\n\nСеверсталь\n\n2023\n\nЕдиный отчет\n\nНа фотографии: «Северсталь»; «Череповецкий металлургический комбинат»; «Cherepovets steel mill».')
dividers={7:'01. Об Отчете и существенности',13:'02. «Северсталь» сегодня',25:'03. Стратегический отчет',33:'04. Корпоративное управление',63:'05. Управление устойчивым развитием',81:'06. Ответственная цепочка поставок',97:'07. Социальный аспект',151:'08. Экологический аспект',221:'09. Приложения'}
for n,title in dividers.items():replace(n,'## '+title)
head='### ПАО «Северсталь» и его дочерние предприятия\n\n'
foot='Прилагаемые примечания являются неотъемлемой частью данной раскрываемой консолидированной финансовой отчетности.'
rows=[
['Выручка','','728,314','682,226'],['Себестоимость продаж','','(409,355)','(403,980)'],['Валовая прибыль','','318,959','278,246'],['Общехозяйственные и административные расходы','','(24,968)','(25,934)'],['Затраты на сбыт','','(46,869)','(52,457)'],['Прочие налоги и отчисления','4','(22,162)','(20,051)'],['Доля в прибылях ассоциированных и совместных предприятий','','1,490','1,517'],['Убыток от выбытия основных средств и нематериальных активов','','(2,599)','(1,824)'],['Чистые прочие операционные расходы','','(151)','(4,676)'],['Прибыль от операционной деятельности','','223,700','174,821'],['Восстановление убытка/(убыток) от обесценения долгосрочных активов','7','260','(48,042)'],['Чистые прочие неоперационные расходы','8','(16,725)','(9,307)'],['Прибыль до налога на прибыль и (расходов)/доходов от финансовой деятельности','','207,235','117,472'],['Финансовые доходы','','13,938','5,749'],['Финансовые расходы','','(16,641)','(8,311)'],['Прибыль от переоценки и выбытия финансовых инструментов','','-','1,075'],['Чистый результат по курсовым разницам','6','34,814','21,470'],['Прибыль до налога на прибыль','','239,346','137,455'],['Расход по налогу на прибыль','9','(45,471)','(29,094)'],['Прибыль за период','','193,875','108,361'],['Относимая на:','','',''],['акционеров ПАО «Северсталь»','','193,861','108,282'],['неконтролирующие доли','','14','79'],['Базовое и разводненное средневзвешенное количество акций, находящихся в обращении в течение периода (млн акций)','20','838','838'],['Базовая и разводненная прибыль на акцию (рублей)','','231.34','129.21']]
replace(264,head+'**Раскрываемые консолидированные отчеты о прибылях и убытках за годы, закончившиеся 31 декабря 2023 и 2022**\n\n(Суммы указаны в миллионах рублей, если не предусмотрено иное)\n\nГод, закончившийся 31 декабря\n\n'+table(rows)+'\n\n'+foot+'\n\nДанная раскрываемая консолидированная финансовая отчетность была утверждена руководством 1 февраля 2024 года.\n\nАО «Северсталь Менеджмент»\n\n> Служебная пометка: изображение печати сохранено на полной исходной странице ниже.\n\n3\n\n264 Единый отчет 2023')
rows=[['Прибыль за период','','193,875','108,361'],['Прочий совокупный (расход)/доход:','','',''],['Статьи, которые не будут реклассифицированы в состав прибыли или убытка','','',''],['Актуарные прибыли/(убытки)','18','334','(80)'],['Итого статьи, которые не будут реклассифицированы в состав прибыли или убытка','','334','(80)'],['Статьи, которые могут быть впоследствии реклассифицированы в состав прибыли или убытка','','',''],['Эффект пересчета в валюту представления – иностранные подразделения','','(6,834)','7,018'],['Итого статьи, которые могут быть впоследствии реклассифицированы в состав прибыли или убытка','','(6,834)','7,018'],['Статьи, которые были реклассифицированы в состав прибыли или убытка','','',''],['Накопленный резерв курсовых разниц по пересчету в валюту представления - иностранные подразделения','21','(2,028)','-'],['Итого статьи, которые были реклассифицированы в состав прибыли или убытка','','(2,028)','-'],['Прочий совокупный (расход)/доход за период','','(8,528)','6,938'],['Общий совокупный доход за период','','185,347','115,299'],['Относимый на:','','',''],['акционеров ПАО «Северсталь»','','185,095','115,275'],['неконтролирующие доли','','252','24']]
replace(265,head+'**Раскрываемые консолидированные отчеты о совокупном доходе за годы, закончившиеся 31 декабря 2023 и 2022**\n\n(Суммы указаны в миллионах рублей, если не предусмотрено иное)\n\nГод, закончившийся 31 декабря\n\n'+table(rows)+'\n\n'+foot+'\n\n4\n\n265')
for n in range(1,296):
 t=parts[2*n]
 for a,b in [('\uf0fc','✓'),('\uf0b7','•')]:
  if a in t:
   changes.append({'pdf_page':n,'change':f'Font symbol U+{ord(a):04X} → {b}; source image confirms checkmark/bullet.'});t=t.replace(a,b)
 parts[2*n]=t
parts[0]=''
s=''.join(parts[0:1]+[f'<!-- pdf_page: {parts[i]} -->'+parts[i+1] for i in range(1,len(parts),2)])
# Put source title first and explicitly separate the working-version notice.
s=s.replace('# Новые цели на пути к устойчивой металлургии будущего\n\n','# Новые цели на пути к устойчивой металлургии будущего\n\n> Служебная информация: рабочая версия полного переноса 295 страниц. Большинство страниц converted/pending; полная постраничная сверка текста, порядка чтения и таблиц не завершена. Статусы и ограничения — в `_проверка/pages.json`.\n\n',1)
p.write_text(s)
d=json.loads((root/'_проверка/pages.json').read_text())
reviewed=set([1,2,264,265,*dividers])
triaged={x['pdf_page'] for x in d['pages'] if x['issues']}
for x in d['pages']:
 n=x['pdf_page'];x['initial_issues']=x['issues'][:];x['diagnostic_triage']='source_image_contact_sheet_viewed' if n in triaged else 'not_reviewed';x['conversion_status']='converted';x['review_status']='checked' if n in reviewed else 'pending';x['semantic_source_review_completed']=n in reviewed
 x['verification_scope']='Source-image body review and correction; source graphics retained' if n in reviewed else ('Diagnostic image overview only; not a full source comparison' if n in triaged else 'Mechanical extraction; no visual source comparison')
 x['review_actions']=[c['change'] for c in changes if c['pdf_page']==n]
 if n in reviewed:x['issues']=[]
 else:
  x['issues']=[i for i in x['issues'] if not i.startswith('Source font mapping')]
  x['issues'].append('Full text, reading order, table-cell relations and footnotes await source comparison.')
  if x.get('ocr_chars',0):x['issues'].append('OCR body is present, but recognition has not been fully verified.')
 if n in [196,223,285,286,289]:x['issues'].append('Diagnostic assignment concerns a space crossing a cell boundary; full table review remains pending.')
 x['printed_page_label']='3; 264' if n==264 else ('4; 265' if n==265 else None)
 if n in dividers or n==1:x['content_type']='cover_or_section_title'
 elif x.get('ocr_chars',0) and n in range(250,265):x['content_type']='mixed_or_scanned_text'
 else:x['content_type']='native_text_and_or_graphics'
 for c in changes:
  if c['pdf_page']==n and 'Font symbol' in c['change']:x['unresolved_unicode']=0
(root/'_проверка/pages.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
(root/'_проверка/corrections.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
print('Saved pages:',len(d['pages']),'checked:',len(reviewed),'pending:',295-len(reviewed))
