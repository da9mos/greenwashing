import sys,io,json,re,hashlib,importlib.util,collections
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
import fitz
from fontTools.ttLib import TTFont
from fontTools.agl import toUnicode
base=Path('result/_проверка'); source=json.loads(Path('source.json').read_text())
tool=Path(source['index']).parents[3]/'tools/native_candidate.py'
spec=importlib.util.spec_from_file_location('native',tool); native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
doc=fitz.open(source['source_pdf']); fonts={x[0]:x for p in doc for x in p.get_fonts()};donors={};parsed={}
for x in fonts.values():
 try:f=TTFont(io.BytesIO(doc.extract_font(x[0])[3]));parsed[x[0]]=f
 except Exception:continue
 if 'cmap' in f and len(f.getGlyphOrder())==1716:donors[x[3].split('+')[-1]]=(x[0],f)
trusted={}
for x in fonts.values():
 if x[2]!='Type0':continue
 family=x[3].split('+')[-1]
 typ,val=doc.xref_get_key(x[0],'ToUnicode')
 if typ!='xref':continue
 cmap=doc.xref_stream(int(val.split()[0])).decode()
 for section in re.findall(r'beginbfchar(.*?)endbfchar',cmap,re.S):
  for code,uni in re.findall(r'<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>',section):
   key=(family,int(code,16));value=bytes.fromhex(uni).decode('utf-16-be')
   if key in trusted and trusted[key]!=value:raise ValueError(('mapping conflict',key))
   trusted[key]=value
logs=[]
for x in fonts.values():
 family=x[3].split('+')[-1]
 if x[2]!='Type0' or family not in donors:continue
 f=parsed[x[0]];donor_x,donor=donors[family];order=f.getGlyphOrder();dorder=donor.getGlyphOrder();cm=donor.getBestCmap();rev={}
 for code,name in cm.items():rev.setdefault(donor.getGlyphID(name),chr(code))
 for gid,name in enumerate(dorder):
  uni=toUnicode(name)
  if uni:rev[gid]=uni
 for (fam,gid),uni in trusted.items():
  if fam==family:rev[gid]=uni
 desc=doc.xref_get_key(x[0],'DescendantFonts')[1];refs=re.findall(r'(\d+) 0 R',desc)
 if not refs:continue
 ref=int(refs[0]);ob=doc.xref_object(ref)
 if ob.startswith('['):ref=int(re.search(r'(\d+) 0 R',ob).group(1))
 if doc.xref_get_key(ref,'CIDToGIDMap')[1]!='/Identity':raise ValueError(('not identity',x))
 oldref=int(doc.xref_get_key(x[0],'ToUnicode')[1].split()[0]);old=doc.xref_stream(oldref).decode();existing={int(a,16):bytes.fromhex(b).decode('utf-16-be') for a,b in re.findall(r'<([0-9A-Fa-f]{4})>\s*<([0-9A-Fa-f]{4,})>',old) if a!='0000'}
 additions={}
 for gid,uni in rev.items():
  if gid in existing:continue
  # Accept only an identical source glyph outline and metrics in the embedded donor.
  if gid>=len(order):continue
  if (family,gid) not in trusted and f['glyf'][order[gid]].getCoordinates(f['glyf']) != donor['glyf'][dorder[gid]].getCoordinates(donor['glyf']):continue
  if f['hmtx'][order[gid]]!=donor['hmtx'][dorder[gid]]:continue
  additions[gid]=uni
 if not additions:continue
 entries=list(additions.items());chunks=[]
 for i in range(0,len(entries),100):
  v=entries[i:i+100];chunks.append(str(len(v))+' beginbfchar\n'+'\n'.join(f'<{gid:04X}> <{u.encode("utf-16-be").hex().upper()}>' for gid,u in v)+'\nendbfchar\n')
 # New CMap per font avoids modifying shared streams for other subsets.
 stream=old.replace('endcmap',''.join(chunks)+'endcmap');new=doc.get_new_xref();doc.update_object(new,'<< >>');doc.update_stream(new,stream.encode());doc.xref_set_key(x[0],'ToUnicode',f'{new} 0 R')
 logs.append({'font_xref':x[0],'donor_xref':donor_x,'family':family,'added':additions})
(base/'font_repairs.json').write_text(json.dumps(logs,ensure_ascii=False,indent=2))
# Reopen repaired bytes to invalidate text/font caches. Original PDF is untouched.
doc=fitz.open(stream=doc.tobytes(),filetype='pdf');names=doc.resolve_names()
records=json.loads((base/'pages.json').read_text())['pages'];parts=[]
for n,page in enumerate(doc,1):
 body,info=native.convert_page(page)
 record=records[n-1];record['original_unresolved_unicode']=record.get('unresolved_unicode');record.update(info)
 record['issues']=[i for i in record['issues'] if not i.startswith('Source font mapping')]
 if info['unresolved_unicode']:record['issues'].append('Unresolved Unicode remains after outline-based font repair.')
 record['review_status']='pending';record['verification_scope']='Native glyph accounting; embedded-font outline repair; full page visual review pending'
 
 try:links,_=native.source_links(page,names,len(doc))
 except TypeError:
  original=Path('result/_проверка/previous_reports/native_initial.md').read_text().split(f'<!-- pdf_page: {n} -->')[1].split('<!-- pdf_page:')[0]
  links=('\n\n> Служебная информация: ссылки исходного PDF'+original.split('> Служебная информация: ссылки исходного PDF',1)[1].split('<details>')[0]) if '> Служебная информация: ссылки исходного PDF' in original else ''
 body+=links
 parts.append(f'<!-- pdf_page: {n} -->\n<a id="pdf-page-{n}"></a>\n\n{body}\n\n<details>\n<summary>Источник: PDF-страница {n}</summary>\n\n![Полная исходная страница {n}](assets/page_{n:04d}.png)\n\n</details>')
 (base/'pages.json').write_text(json.dumps({'pages':records},ensure_ascii=False,indent=2))
 if n%20==0:print(n,flush=True)
Path('result/report.md').write_text('# ГОДОВОЙ ОТЧЕТ\n\n'+'\n\n'.join(parts)+'\n')
print('done',len(logs),sum(r['unresolved_unicode'] for r in records))
