exec(open('result/_проверка/glyph_atlas.py').read().split('items=sorted')[0])
import io
from fontTools.cffLib import CFFFontSet
fonts={t[0]:t for p in d for t in p.get_fonts(full=True) if t[1]=='cid'}
codes=set()
for x in fonts:
 c=CFFFontSet();c.decompile(io.BytesIO(d.extract_font(x)[3]),None);codes.update(int(v[3:]) for v in c[c.fontNames[0]].charset if v.startswith('cid'))
# use font from a page that includes each cid; construct one atlas per font subset via source clips instead, using raw chars' code identity
print(sorted(codes));print(len(codes))
# atlas by drawing CID in existing page font G2 (font subset only)
x=278;c=CFFFontSet();c.decompile(io.BytesIO(d.extract_font(x)[3]),None);codes=sorted(int(v[3:]) for v in c[c.fontNames[0]].charset if v.startswith('cid'))
p=d[1]; content=['q 1 1 1 rg 0 0 1920 1080 re f Q']
for i,code in enumerate(codes):
 xx=30+(i%15)*120; yy=1000-(i//15)*110
 content.append(f'BT /G2 48 Tf 0 0 0 rg 1 0 0 1 {xx} {yy} Tm <{code:04X}> Tj ET')
xr=d.get_new_xref();d.update_object(xr,'<<>>');d.update_stream(xr,'\n'.join(content).encode());p.set_contents(xr)
for i,code in enumerate(codes):
 xx=30+(i%15)*120; yy=1000-(i//15)*110
 p.insert_text((xx,1080-yy+25),f'{code:04X}',fontsize=16,color=(1,0,0))
p.get_pixmap(matrix=f.Matrix(1,1)).save('result/_проверка/cid_atlas.png')
