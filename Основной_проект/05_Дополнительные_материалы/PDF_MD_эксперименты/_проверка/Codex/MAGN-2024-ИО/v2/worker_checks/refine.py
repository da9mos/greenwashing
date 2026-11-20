import json,re,html,hashlib
from pathlib import Path
import fitz
root=Path('result');s=(root/'report.md').read_text();parts=re.split(r'<!-- pdf_page: \d+ -->',s);meta=json.load(open('source.json'));doc=fitz.open(meta['source_pdf'])
logs=[]
def clip(n,box):
 p=doc[n-1];w=p.rect.width;h=p.rect.height
 text=p.get_text('text',clip=fitz.Rect(box[0]*w/2048,box[1]*h/1152,box[2]*w/2048,box[3]*h/1152),sort=True)
 return html.escape(text.strip()).replace('\n','<br/>')
# Explicit, visually established grid on source page 34.
xs=[62,184,389,592,874,1065,1256,1713,1985];ys=[121,171,480,1057]
t='<a id="pdf-page-34"></a>\n\n<p>СТРАТЕГИЧЕСКИЙ ОТЧЕТ · СТРАТЕГИЯ</p>\n<table>\n'
for ya,yb in zip(ys,ys[1:]):
 t+='<tr>'+''.join('<td>'+clip(34,(xa,ya,xb,yb))+'</td>' for xa,xb in zip(xs,xs[1:]))+'</tr>\n'
t+='</table>\n<p>¹ Малобюджетные и быстроокупаемые проекты.</p>\n<p>ГОДОВОЙ ОТЧЕТ ММК · 34</p>\n'
old=parts[34];tail=old[old.index('> Служебная информация: ссылки'):];parts[34]='\n'+t+'\n'+tail
logs.append({'page':34,'change':'Rebuilt 8-column, 2-body-row table using visually verified source grid; retained source glyph text per cell.','review':'Table and its footnote visually inspected; full page comparison pending.'})
# Remove nonprinting controls after visual examination of their contexts.
for n in range(1,330):
 controls=re.findall('[\x00-\x08\x0b\x0c\x0e-\x1f]',parts[n])
 if controls:
  parts[n]=parts[n].replace('\x03',' ').replace('\x07','').replace('\x08','')
  logs.append({'page':n,'change':'Removed nonprinting font-map controls; U+0003 between № and number replaced with space, U+0007/U+0008 layout controls removed.','count':len(controls),'review':'Context review only; page not checked.'})
parts[229]=parts[229].replace('> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена.\n\nTUV<br/>&lt;\n\n','')
logs.append({'page':229,'change':'Removed OCR noise TUV/<; native TÜV AUSTRIA already present.','review':'Source image inspected.'})
# Cover contains company name inside logo image, omitted from native glyphs.
parts[1]=parts[1].replace('<p>ГОДОВОЙ</p>\n\n<p>ОТЧЕТ</p>','<p>МАГНИТОГОРСКИЙ МЕТАЛЛУРГИЧЕСКИЙ КОМБИНАТ</p>\n\n<p>ГОДОВОЙ ОТЧЕТ</p>')
logs.append({'page':1,'change':'Transcribed company name in cover logo; joined title.','review':'Cover visually read.'})
# Contents page 229: pair titles and displayed destinations, verified against image and annotations.
titles=['Об Отчете','Отчет по заданию, обеспечивающему уверенность','Информация о совершенных (заключенных) ПАО «ММК» в отчетном году крупных сделках и сделках, в совершении которых имеется заинтересованность','Бухгалтерская отчетность за 2024 год и аудиторское заключение независимого аудитора','Верификация выбросов парниковых газов, заключение TÜV AUSTRIA Standards & Compliance','Отчет о соблюдении ПАО «ММК» принципов и рекомендаций Кодекса корпоративного управления','Таблица GRI','Таблица SASB','Раскрытие показателей в соответствии с рекомендациями Минэкономразвития','Раскрытие вклада Компании в национальные цели развития РФ','Глоссарий','Контактная информация']
nums=[230,233,235,236,279,283,303,320,321,324,328,329]
t='\n<a id="pdf-page-229"></a>\n\n<h2>ПРИЛОЖЕНИЯ</h2>\n\n<table>\n'+''.join(f'<tr><td><a href="#pdf-page-{n}">{html.escape(title)}</a></td><td>{n}</td></tr>\n' for title,n in zip(titles,nums))+'</table>\n<p>ГОДОВОЙ ОТЧЕТ ММК</p>\n\n'
parts[229]=t+parts[229][parts[229].index('<details>'):]
# Explicitly flag remaining review limits beside affected content.
issues=json.load(open(root/'_проверка/pages.json'))
for p in issues['pages']:
 n=p['pdf_page'];p['review_status']='pending';p['semantic_source_review_completed']=False
 p['verification_scope']='Mechanical coverage; selective source-image review only'
 p['review_notes']=[]
 if n in [1,34,60,229,236,263,269,328] or 303<=n<=320:
  p['review_notes'].append('Diagnostic source image viewed; selective context checks do not establish full-page fidelity.')
 if p['issues']:
  p['original_diagnostics']=p['issues'][:]
  if n in [1,60,229,236,328] or 303<=n<=320:
   p['issues']=['Full-page source comparison remains pending after targeted diagnostic corrections.']
  if n==34:p['issues']=['Table reconstructed after false merged-cell detection; full-page comparison remains pending.']
  if n in [263,269]:p['issues'].append('Ambiguity concerns whitespace at a cell boundary; full table comparison remains pending.')
  parts[n]=parts[n].replace('\n<a id=', '\n> Служебная пометка: выполнена частичная проверка; полная сверка страницы и связей данных с оригиналом не завершена.\n\n<a id=',1)
 if not p['issues']:p['issues']=['Full-page source comparison pending.']
 p['conversion_status']='converted'
prefix='# ГОДОВОЙ ОТЧЕТ 2024\n\n> Служебная информация: рабочая конвертация всех 329 физических страниц. Текстовый слой перенесён механически, выполнены адресные исправления. Полная постраничная сверка текста, таблиц, графики и порядка чтения не завершена. Статусы и ограничения: `_проверка/pages.json`.\n\n'
out=prefix+''.join(f'<!-- pdf_page: {n} -->'+parts[n] for n in range(1,330));(root/'report.md').write_text(out)
(root/'_проверка/pages.json').write_text(json.dumps(issues,ensure_ascii=False,indent=2))
(root/'_проверка/corrections.json').write_text(json.dumps(logs,ensure_ascii=False,indent=2))
print('saved',len(out),'chars;',len(logs),'correction entries')
