from PIL import Image,ImageOps,ImageDraw
from pathlib import Path
for start in range(1,139,12):
 sheet=Image.new('RGB',(1600,4*310),'white'); draw=ImageDraw.Draw(sheet)
 for k,n in enumerate(range(start,min(start+12,139))):
  im=Image.open(f'result/assets/page_{n:04}.png'); im.thumbnail((530,285)); x=k%3*533; y=k//3*310
  sheet.paste(im,(x,y+22)); draw.text((x+5,y+3),str(n),fill='black')
 sheet.save(f'result/_проверка/contact_{start:03}.jpg')
