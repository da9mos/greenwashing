import sys,json,pathlib,unicodedata
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf as fitz
from PIL import Image,ImageDraw
s=json.load(open('source.json'));d=fitz.open(s['source_pdf']);ps=json.load(open('result/_проверка/pages.json'))['pages'];out=pathlib.Path('result/_проверка/review');crops=[]
for x in ps:
 if x.get('unresolved_unicode'):
  page=d[x['pdf_page']-1]
  for b in page.get_text('rawdict')['blocks']:
   for l in b.get('lines',[]):
    chars=[c for sp in l['spans'] for c in sp['chars']]
    if any((unicodedata.category(c['c']) in ('Co','Cs') or (unicodedata.category(c['c'])=='Cc' and not c['c'].isspace())) for c in chars):
     r=fitz.Rect(l['bbox']);r.x0=max(0,r.x0-25);r.x1=min(page.rect.width,r.x1+25);r.y0-=8;r.y1+=8
     pix=page.get_pixmap(matrix=fitz.Matrix(2,2),clip=r);im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples);crops.append((x['pdf_page'],repr(''.join(c['c'] for c in chars)),im))
for off in range(0,len(crops),16):
 subset=crops[off:off+16];sheet=Image.new('RGB',(2000,sum(im.height+35 for p,t,im in subset)),'white');draw=ImageDraw.Draw(sheet);y=0
 for p,t,im in subset:
  draw.text((5,y),f'PDF {p}: {t}',fill='black');sheet.paste(im,(5,y+25));y+=im.height+35
 sheet.save(out/f'unicode_{off//16}.png')
flag=[x['pdf_page'] for x in ps if x['issues'] and not x.get('unresolved_unicode') and x['pdf_page']!=1]
for off in range(0,len(flag),4):
 sheet=Image.new('RGB',(2400,1420),'#ddd');draw=ImageDraw.Draw(sheet)
 for j,n in enumerate(flag[off:off+4]):
  im=Image.open(f'result/assets/page_{n:04}.png');im.thumbnail((1200,675));xx=(j%2)*1200;yy=(j//2)*710;sheet.paste(im,(xx,yy+25));draw.text((xx+5,yy+5),f'PDF {n}',fill='black')
 sheet.save(out/f'flags_{off//4:02}.jpg')
print('unicode crops',len(crops),'flag',flag)
for x in ps:
 if x['issues']: print(x['pdf_page'],'unicode',x.get('unresolved_unicode'),'ambiguous',len(x.get('ambiguous_cell_assignments',[])),'OCR',x.get('ocr_chars'), 'overlap conflicts',len(x.get('overlapping_native_conflicts',[])))
