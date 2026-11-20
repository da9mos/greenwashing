import sys,json,io,hashlib
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf as f
from fontTools.cffLib import CFFFontSet
s=json.load(open('source.json'));d=f.open(s['source_pdf'])
m={3:' ',4:' ',5:'!',9:'%',12:'(',13:')',16:',',17:'-',18:'.',19:'/',30:':',31:';',67:'_',109:'«',124:'»',385:'–',386:'—',421:'№',444:'fi',632:'\u00a0',215:'Й',941:'Ё'}
for c in range(20,30):m[c]=str(c-20)
for c in range(37,63):m[c]=chr(c+28)
for c in range(69,95):m[c]=chr(c+28)
for c,t in zip(range(216,234),'БДЖЗИЛУФЦЧШЩЪЫЬЭЮЯ'):m[c]=t
for c,t in zip(range(234,258),'бвгджзиклмнптфцчшщъыьэюя'):m[c]=t
for c,t in {825:'К',828:'А',829:'В',831:'Е',832:'Й',834:'Н',835:'О',836:'П',837:'Р',838:'С',839:'Т',841:'а',842:'е',845:'Ё',947:'К',950:'А',951:'В',952:'Г',953:'Е',954:'Й',955:'М',956:'Н',957:'О',958:'П',959:'Р',960:'С',961:'Т',962:'Х',963:'а',964:'е',965:'й',966:'о',967:'р',968:'с',969:'у',970:'х'}.items():m[c]=t
fonts={t[0]:t for p in d for t in p.get_fonts(full=True) if t[1]=='cid'}
records=[]
for x,t in fonts.items():
 c=CFFFontSet();c.decompile(io.BytesIO(d.extract_font(x)[3]),None);codes=sorted(int(v[3:]) for v in c[c.fontNames[0]].charset if v.startswith('cid'))
 assert not set(codes)-set(m),set(codes)-set(m)
 fm=dict(m)
 if x==308: fm.update({21:'3',19:'1',3:' ',232:'д',842:'е',236:'к',841:'а',229:'б',845:'р',252:'я',20:'2',18:'0'})
 if x==323: fm.update({216:'Л',217:'У',219:'Ц',224:'Ы',225:'Ь',228:'Я',235:'и'})
 if x==374: fm[215]='И'
 lines=['/CIDInit /ProcSet findresource begin','12 dict begin','begincmap','/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def','/CMapName /Restored-UCS def','/CMapType 2 def','1 begincodespacerange','<0000> <FFFF>','endcodespacerange']
 for start in range(0,len(codes),90):
  batch=codes[start:start+90];lines+=[f'{len(batch)} beginbfchar']+[f'<{k:04X}> <{fm[k].encode("utf-16-be").hex().upper()}>' for k in batch]+['endbfchar']
 lines+=['endcmap','CMapName currentdict /CMap defineresource pop','end','end'];xr=d.get_new_xref();d.update_object(xr,'<<>>');d.update_stream(xr,'\n'.join(lines).encode());d.xref_set_key(x,'ToUnicode',f'{xr} 0 R');records.append({'font_xref':x,'font':t[3],'codes':codes,'mapping':{k:fm[k] for k in codes}})
d.save('result/_проверка/font_repaired_v2.pdf')
Path('result/_проверка/font_mapping.json').write_text(json.dumps({'mapping':m,'fonts':records,'basis':'Visual glyph atlases rendered from embedded source PDF fonts; no external font or model.'},ensure_ascii=False,indent=2))
