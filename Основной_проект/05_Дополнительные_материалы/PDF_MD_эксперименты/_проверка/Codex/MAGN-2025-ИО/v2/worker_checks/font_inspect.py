import fitz,json,io,collections
from pathlib import Path
from fontTools.ttLib import TTFont
s=json.loads(Path('source.json').read_text()); d=fitz.open(s['source_pdf']);fs={x[0]:x for p in d for x in p.get_fonts()};print('fonts',len(fs))
for x in fs.values():
 try:
  f=TTFont(io.BytesIO(d.extract_font(x[0])[3]));cm=f.getBestCmap() if 'cmap' in f else {};print(x[0],x[3],x[2],len(f.getGlyphOrder()),len(cm))
 except Exception as e:print(x[0],str(e))
