from pathlib import Path
code=Path('result/_проверка/convert.py').read_text().split('\nrecords=[]')[0]
code=code.replace('ignore_images=True,force_text=True,show_progress=False','ignore_images=True,ignore_graphics=True,force_text=True,show_progress=False')
code=code.replace("src=clean(p.get_text(clip=r)); words=", "src=clean('\\n'.join(''.join(s['text'] for s in l['spans']) for block in p.get_text('dict',clip=r)['blocks'] for l in block.get('lines',[]) if abs(l['dir'][1])<.1)); words=")
exec(compile(code,'result/_проверка/convert.py','exec'))
CH=AUD/'repaired';CH.mkdir(exist_ok=True)
records=[]
for n in range(1,len(doc)+1):
 if n in (132,133):continue
 rec=convert(n);records.append(rec)
 (AUD/'repair-pages.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
 print(n,rec['extraction_methods'],flush=True)
