import sys,re,json,pathlib,hashlib,html
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
from bs4 import BeautifulSoup
root=pathlib.Path('result'); original=(root/'_проверка/baseline/report.md').read_text(); split=re.split(r'<!-- pdf_page: (\d+) -->',original);pages={int(split[i]):split[i+1] for i in range(1,len(split),2)};changes=[]
def log(n,msg):changes.append({'pdf_page':n,'change':msg,'evidence':f'assets/page_{n:04}.png'})
# Cover: all visible cover text read directly.
pages[1]='\n<a id="pdf-page-1"></a>\n\nАЛРОСА\n\nОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ\n\n2023\n\n![Обложка](assets/page_0001.png)\n\n';log(1,'Вместо единственного OCR-прочерка перенесены логотип, название и год с обложки.')
# Control characters: inspected every occurrence using source-rendered line crops.
for n,b in pages.items():
 c=re.sub('[\x03\x07]','',b)
 if c!=b:pages[n]=c;log(n,'Удалены управляющие символы U+0003/U+0007, не имеющие видимого печатного знака; просмотрены соответствующие строки оригинала.')
# Discard OCR fragments only where image inspection shows duplicates, navigation or photographic noise.
ocr_re=re.compile(r'> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\.\n\n.*?(?=> Служебная информация: ссылки исходного PDF|<details>)',re.S)
ocr_labels={12:'<p>МЫ ПОДДЕРЖИВАЕМ</p>\n<p>GLOBAL COMPACT</p>\n<p>UNITED NATIONS — NATIONS UNIES</p>\n',128:'<p>Методические ориентиры:</p>\n<ul><li>3 Хорошее здоровье и благополучие</li><li>4 Качественное образование</li><li>8 Достойная работа и экономический рост</li><li>9 Индустриализация, инновации и инфраструктура</li><li>11 Устойчивые города и населенные пункты</li></ul>\n<p>1; 2</p>\n<p>Национальные проекты России: Образование; Малое и среднее предпринимательство; Демография; Культура; Жилье и городская среда; Здравоохранение; Наука и университеты.</p>\n'}
for n in list(pages):
 if ocr_re.search(pages[n]):
  pages[n]=ocr_re.sub(ocr_labels.get(n,'' )+'\n',pages[n]);log(n,'Просмотрена компоновка страницы; удалена дополнительная OCR-строка с дублированием текстового слоя и ошибочным распознаванием навигации/фотографии. Уникальные подписи на просмотренных изображениях сохранены отдельно, где прочитаны. Полная построчная сверка страницы не заявлена.')
# 7: keep native strings and all numeric cells, reconstruct source row and merged-cell relationships.
soup=BeautifulSoup(pages[7],'html.parser');tbl=soup.find('table');rows=[[c.decode_contents() for c in row.find_all('td',recursive=False)] for row in tbl.find_all('tr')]
# 0 GRI; 1 header; 2/3 created; 7/8 associate; 11/12 distribution; 18/19 remainder.
rows[1][4]+='<br/>'+rows[2][4];rows[2][4]=''
for a,b in [(2,3),(7,8),(11,12),(18,19)]:
 rows[a][0]+=' '+rows[b][0]
 if a==7: rows[a][1:4]=rows[b][1:4]
keep=[1,2,4,5,6,7,9,10,11,13,14,15,16,17,18]
parts=['<p>GRI 201-1</p>','<table>']
for idx in keep:
 parts.append('<tr>')
 for j,c in enumerate(rows[idx]):
  if j==4 and idx in [4,5,6,7,9,10]:continue
  if j==4 and idx==2:c=rows[6][4]
  c=re.sub(r'<sup>\s*</sup>','',c)
  tag='th' if idx==1 else 'td'; span=' rowspan="7"' if j==4 and idx==2 else ''
  parts.append(f'<{tag}{span}>{c}</{tag}>')
 parts.append('</tr>')
parts.append('</table>');pages[7]=pages[7].replace(str(tbl),'\n'.join(parts))
# Footnote numbers were extracted separately; restore actual source pairing.
start=pages[7].index('<p>1</p>');end=pages[7].index('<p>РАЗВИТИЕ</p>',start)
foot=pages[7][start:end];ptexts=re.findall(r'<p>(.*?)</p>',foot,re.S)
pages[7]=pages[7][:start]+'<p><sup>1</sup> '+ ' '.join(ptexts[2:4])+'</p>\n<p><sup>2</sup> '+' '.join(ptexts[4:])+'</p>\n'+pages[7][end:]
log(7,'По всей исходной таблице проверены значения; восстановлены многострочные названия, шапка и объединенная ячейка заинтересованных сторон; восстановлена связь двух примечаний. Числа взяты из исходных ячеек кандидата.')
# 106: replace false table fragments of graphic labels with explicit category/value rows.
b=pages[106];start=b.index('<p>2021</p>');end=b.index('> Служебная информация: ссылки',start)
labels=['Обращение с отходами','Защита и реабилитация земель, поверхностных и подземных вод','Сбор и очистка сточных вод','Охрана атмосферного воздуха и предотвращение изменения климата','Научно-исследовательская деятельность и разработки по снижению негативных антропогенных воздействий на окружающую среду','Сохранение биоразнообразия и охрана природных территорий','Бюджетные платежи','Обеспечение радиационной безопасности окружающей среды','Защита окружающей среды от шумового, вибрационного и других видов физического воздействия','Другие направления']
region=b[start:end];nums=re.findall(r'<p>([\d ,]+)</p>',region);assert nums==['2021','2022','2023','6 714','7 558','10 675','10 675','6 930','2 571','473','257','144','134','82','1,4','0,7','82'],nums
new='<table><tr><th>Год</th><th>Расходы, млн рублей</th></tr>'+''.join(f'<tr><td>{year}</td><td>{val}</td></tr>' for year,val in zip(nums[:3],nums[3:6]))+'</table>\n<p>Расходы Группы АЛРОСА на охрану окружающей среды в 2023 году, млн рублей</p>\n<table><tr><th>Направление</th><th>млн рублей</th></tr><tr><td>Всего</td><td>'+nums[6]+'</td></tr>'+''.join(f'<tr><td>{label}</td><td>{val}</td></tr>' for label,val in zip(labels,nums[7:]))+'</table>\n\n'
pages[106]=b[:start]+new+b[end:];log(106,'Сверены вся страница и оба графических блока; восстановлены пары год/расходы и направление/сумма. Удалены ложные табличные строки внутри подписей диаграммы; значения перенесены из кандидата без пересчета.')
# 143: full body missing from native candidate, OCR plus manual visual reading of all three leaves.
b=pages[143];pos=b.index('> Служебная информация: ссылки');pages[143]=b[:pos]+(root/'_проверка/review/143_transcription.md').read_text()+'\n\n'+b[pos:];log(143,'Восстановлено отсутствовавшее тело заключения: локальный Tesseract rus+eng трех встроенных листов, затем ручная вычитка по каждому изображению, включая адрес, дату, доверенность, ОРНЗ, примечание и продолжения. Подпись сохранена в полном изображении страницы.')
# 144: rebuild small statement and the GRI table using native cell strings, preserve blank comments.
soup=BeautifulSoup(pages[144],'html.parser');tbl=soup.find('table');r=[[c.decode_contents() for c in row.find_all('td',recursive=False)] for row in tbl.find_all('tr')]
statement='<table><tr><td>Заявление о применении</td><td>'+r[0][1]+' '+r[1][1].replace('<br/>',' ').replace('по\xa031','января по\xa031')+'</td></tr><tr><td>GRI 1 применение</td><td>'+r[2][1]+' '+r[2][2]+'</td></tr></table>'
# First statement's native reading must place "января" immediately after "1".
statement=statement.replace('с\xa01 января по\xa031','с\xa01 января по\xa031')
first_label=r[7][0]+' '+r[7][1]; comments=r[7][4]+'<br/><br/>'+r[8][4]+'<br/><br/>'+r[9][4]+' '+r[10][4]
data=[(r[7][2],r[7][3],comments),(r[11][2],r[11][3],r[11][4]),(r[12][2]+' '+r[13][2],r[12][3]+'<br/>'+r[13][3],''),(r[14][2],r[14][3],''),(r[15][2],r[15][3]+'<br/>'+r[16][3],r[15][4]+' '+r[16][4])]
new=statement+'\n<table><tr><th colspan="2">Показатель</th><th>Раздел</th><th>Комментарии</th></tr><tr><td colspan="4">Общие элементы отчетности</td></tr><tr><td colspan="4">'+r[6][0]+'</td></tr>'
for i,(indicator,section,comment) in enumerate(data):new+='<tr>'+ ('<td rowspan="5">'+first_label+'</td>' if i==0 else '')+'<td>'+indicator+'</td><td>'+section+'</td><td>'+comment+'</td></tr>'
new+='</table>';pages[144]=pages[144].replace(str(tbl),new);log(144,'Полностью сверены обе таблицы. Устранены фиктивные столбцы и разбиение объединенных ячеек; слово «января» возвращено в период; восстановлен общий заголовок GRI 2. Диагностическая неоднозначность пробела на границе ячеек разрешена по оригиналу.')
# Source review is page-level only when complete; partial inspections remain pending.
checked={1,7,106,143,144};registry=json.loads((root/'_проверка/baseline/pages.json').read_text());original_issues={x['pdf_page']:x['issues'][:] for x in registry['pages']}
for x in registry['pages']:
 n=x['pdf_page'];x['diagnostic_issues_original']=original_issues[n];x['review_status']='checked' if n in checked else 'pending';x['conversion_status']='converted';x['semantic_source_review_completed']=n in checked;x['verification_scope']='Full page source image and corrected text/relationships' if n in checked else 'Native extraction; diagnostics inspected where flagged; full source review pending';x['review_notes']=[v['change'] for v in changes if v['pdf_page']==n]
 if n in checked:x['issues']=[]
 else:x['issues']=['Полная построчная сверка страницы, порядка чтения и всех связей по оригиналу не завершена.']+original_issues[n]
 if n not in checked:
  anchor=f'<a id="pdf-page-{n}"></a>'
  pages[n]=pages[n].replace(anchor,anchor+'\n\n> Служебная пометка: converted / review pending — полная сверка текста, колонок, таблиц и графических подписей по оригиналу не завершена. Изображение страницы приведено ниже для проверки.',1)
# keep original native inventory evidence unchanged, add independent final manifest.
header='# ОТЧЕТ ОБ УСТОЙЧИВОМ РАЗВИТИИ 2023\n\n> Служебная информация: рабочая версия полного переноса 170 физических страниц. Полностью сверены страницы 1, 7, 106, 143 и 144; остальные converted / review pending. Исходный механический кандидат и подробный протокол сохранены в `_проверка/`.\n\n'
result=header+''.join(f'<!-- pdf_page: {n} -->'+pages[n] for n in range(1,171));(root/'report.md').write_text(result);(root/'_проверка/pages.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2));(root/'_проверка/corrections.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
print('Saved pages',len(pages),'checked',sorted(checked),'changes',len(changes),'chars',len(result))
