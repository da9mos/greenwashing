import sys,json
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf
pymupdf._layout_enabled=False
d=pymupdf.open(json.load(open('source.json'))['source_pdf']);p=d[132];data=p.get_text('dict');parts=['Приложение 8\n\n## Отчет независимого аудитора по заданию, обеспечивающему ограниченную уверенность']
for l,r in [(0,420),(420,775),(775,1191)]:
 blocks=[]
 for b in data['blocks']:
  ls=[]; ys=[]
  for line in b.get('lines',[]):
   spans=[s for s in line['spans'] if l<=(s['bbox'][0]+s['bbox'][2])/2<r and s['bbox'][1]>230]
   if spans:ls.append(''.join(s['text'] for s in spans));ys.append(min(s['bbox'][1] for s in spans))
  if ls:blocks.append((min(ys),'\n'.join(ls)))
 parts.append('Технологии Доверия\n\n'+'\n\n'.join(t for y,t in sorted(blocks)))
Path('result/_проверка/pages/fixed_0133.md').write_text('\n\n'.join(parts))
