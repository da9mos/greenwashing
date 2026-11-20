from pathlib import Path
import re,json
p=Path('result/report.md');s=p.read_text()
def change(n,body):
 global s
 pat=r'(<!-- pdf_page: '+str(n)+r' -->)(.*?)(?=<!-- pdf_page: |\Z)'
 m=re.search(pat,s,re.S);old=m[2];tail=old[old.index('<details>'):]
 s=s[:m.start()]+m[1]+f'\n<a id="pdf-page-{n}"></a>\n\n'+body+'\n\n'+tail+s[m.end():]
change(1,'## ГОДОВОЙ ОТЧЁТ\n\nМечел\n\n2025')
for n,title in [(4,'СТРАТЕГИЧЕСКИЙ ОТЧЁТ'),(23,'КОРПОРАТИВНОЕ УПРАВЛЕНИЕ'),(50,'ПРИЛОЖЕНИЯ'),(67,'ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ')]:change(n,'## '+title)
# Preserve annotation destinations separately; attach visible page labels in TOC.
m=re.search(r'<!-- pdf_page: 2 -->(.*?)(?=<!-- pdf_page: 3 -->)',s,re.S);t=m[1];ps=re.findall('<p>(.*?)</p>',t,re.S)
# Original printed page labels, including two 69 labels, are retained.
out=['## СОДЕРЖАНИЕ','### СТРАТЕГИЧЕСКИЙ ОТЧЁТ']
for label,num in zip(ps[4:12],ps[12:20]):out.append(f'- {label} — {num}')
out.append('### КОРПОРАТИВНОЕ УПРАВЛЕНИЕ')
for i in range(21,41,2):out.append(f'- {ps[i]} — {ps[i+1]}')
out+=['### ПРИЛОЖЕНИЯ','- '+' '.join(ps[42:46])+' — '+ps[46],'- '+' '.join(ps[47:49])+' — '+ps[49],'### ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ',f'- {ps[51]} — {ps[53]}',f'- {ps[52]} — {ps[54]}']
# Keep the actual source annotation list as technical data.
annotations=t[t.index('> Служебная информация: ссылки'):t.index('<details>')]
change(2,'\n\n'.join(out)+'\n\n'+annotations)
# Source map is raster, so supply complete visually read labels rather than OCR fragments.
pat=r'(<!-- pdf_page: 7 -->.*?)(> Служебная пометка: распознанный текст изображения, точность OCR не подтверждена\..*?)(?=> Служебная информация: ссылки)'
labels=['Вяртсильский метизный завод','«Мечел-Сервис Бел»','«Москокс»','«Мечел-Сервис» (головной офис)','«Ижсталь»','«Мечел-Кокс»','«Порт Мечел-Темрюк»','БМК','ЧМК','«Уралкуз»','«Кузбассэнергосбыт»','Гурьевский филиал ПАО «ЧМК»','«Южный Кузбасс»','Южно-Кузбасская ГРЭС','ЯРК','«Якутуголь»','Коршуновский ГОК','Братский завод ферросплавов','«Торговый порт Посьет»']
body='### Подписи карты\n\n'+'\n'.join('- '+v for v in labels)+'\n\nЛегенда: МЕТАЛЛУРГИЯ; ГОРНАЯ ДОБЫЧА; ЭНЕРГЕТИКА; ПОРТЫ; СБЫТ.\n\nПримечание:\n\n- БМК — Белорецкий металлургический комбинат\n- ЧМК — Челябинский металлургический комбинат\n- Уралкуз — «Уральская кузница»\n- ЯРК — Якутская рудная компания\n\n'
s=re.sub(pat,lambda m:m[1]+body,s,flags=re.S)
p.write_text(s)
