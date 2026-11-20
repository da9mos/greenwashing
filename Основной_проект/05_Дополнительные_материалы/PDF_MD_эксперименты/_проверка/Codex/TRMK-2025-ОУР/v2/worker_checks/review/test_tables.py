import sys,json,importlib.util
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import fitz
s=json.load(open('source.json')); d=fitz.open(s['source_pdf']);p=d[89]
for strategy in ['lines','lines_strict','text']:
 for half in [0,1]:
  clip=fitz.Rect(half*p.rect.width/2,100,(half+1)*p.rect.width/2,p.rect.height-30)
  t=p.find_tables(clip=clip,strategy=strategy)
  print(strategy,half,[(x.row_count,x.col_count,x.bbox) for x in t.tables]); print(str([x.extract()[:4] for x in t.tables])[:2000])
