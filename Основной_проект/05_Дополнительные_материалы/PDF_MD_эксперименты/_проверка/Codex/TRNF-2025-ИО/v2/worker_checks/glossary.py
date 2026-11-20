exec((__import__('pathlib').Path(__file__).parent/'refine.py').read_text().split('# OCR text retained')[0])
# Uses shared glyph renderer only, page-specific borders established visually.
U[188]=units(188)
left=[93.2,116.1,139.1,152.1,165,178,190.9,203.9,226.9,239.8,252.8,265.7,278.7,291.7,314.6,327.6,340.5,363.5,386.5,409.4,423.2,456,478.8,521.5]
mid=[93.2,116,139,152,164.9,177.9,210.8,223.8,246.8,259.7,272.7,295.6,308.6,321.6,344.5,357.5,390.4,403.4,416.4,429.3,442.3,455.2,468.2,491.2,505.7,519.9]
right=[93.2,116.1,149.1,162.1,175,188,200.9,223.9,246.9,269.8,292.8,305.7,328.7,341.7,354.6,367.6,390.5,403.5,416.5,429.4,443.2,477.1,502.1]
new=[]
for xs,starts in [([56,118,277],left),([292,354.5,513],mid),([529,590,750],right)]:
 new.append(table(188,xs,[y-2 for y in starts]+[544]))
s=(root/'report.md').read_text();pat=r'(<!-- pdf_page: 188 -->)(.*?)(?=<!-- pdf_page:|\Z)';m=re.search(pat,s,re.S);old=m[2];soup=BeautifulSoup(old,'html.parser');oldtable=str(soup.find('table'))
# Replace exact table markup as parsed, preserving all surrounding blocks.
soup.find('table').replace_with(BeautifulSoup('\n\n'.join(new),'html.parser'))
old_digits=collections.Counter(c for c in BeautifulSoup(old,'html.parser').get_text() if c.isdigit());new_digits=collections.Counter(c for c in soup.get_text() if c.isdigit());assert old_digits==new_digits
s=s[:m.start(2)]+str(soup)+s[m.end(2):]
# Navigation captions from overlapping annotation rectangles are not source prose.
def caption(m):
 target=m[1]
 return '<a href="#pdf-page-'+target+'">Переход исходного PDF: физическая страница '+target+'</a>'
s=re.sub(r'<a href="#pdf-page-(\d+)">.*?</a>',caption,s,flags=re.S)
(root/'report.md').write_text(s)
log=json.loads((root/'_проверка/corrections.json').read_text());log.append({'pdf_page':188,'change':'Слитый глоссарий разделён на три самостоятельных двухколоночных списка. Переносы определений присоединены к своему термину по изображению. Все термины и определения сверены с изображением, цифры сохранены из глифов.','basis':'Полноразмерное изображение страницы 188; исходные глифы.'});log.append({'pdf_page':3,'change':'В служебной навигации подписи из перекрывающихся прямоугольников аннотаций заменены явными техническими подписями физической целевой страницы. Текст исходного оглавления сохранён отдельно; адреса из аннотаций не изменены.','basis':'Проверка аннотаций исходного PDF и якорей результата.'})
(root/'_проверка/corrections.json').write_text(json.dumps(log,ensure_ascii=False,indent=2))
print('glossary corrected')
