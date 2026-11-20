from pathlib import Path
out=Path('result/_проверка/pages')
for n in [13,17]:
 f=out/f'{n:04}.md';s=f.read_text();title='### Матрица существенности' if n==13 else '### Связь ценностей';pos=s.find(title)
 assert pos>=0
 s=s[pos:];f.write_text(s)
# Insert visually transcribed figures at their original positions in the body.
for n,startkey,target in [(10,'### Как мы определяем','**Определение существенных тем'),(16,'### Миссия и ценности Группы\n','В своей деятельности'),(30,'### Структура ИСМ\n','В 2023 году Группа'),(80,'### Структура Молодежного совета\n','Основные требования'),(43,'### Сценарный анализ','**Переходные риски**')]:
 f=out/f'{n:04}.md';s=f.read_text();start=s.find(startkey)
 if start<0:continue
 end=s.find('<!-- PDF link annotations -->',start)
 if end<0:end=s.find('<details>',start)
 block=s[start:end];s=s[:start]+s[end:];pos=s.find(target)
 if pos>=0:s=s[:pos]+block+'\n\n'+s[pos:]
 else:continue
 f.write_text(s)
# Place supply-chain graphic in reading order, keep national-goal text by opening heading.
f=out/'0114.md';s=f.read_text();a=s.find('<!-- Текст графических объектов -->');b=s.find('<details>',a)
if a>=0:
 block=s[a:b];s=s[:a]+s[b:];key='##### **Ключевые внутренние документы**';pos=s.find(key)
 if pos>=0:s=s[:pos]+block+'\n\n'+s[pos:]
 f.write_text(s)
