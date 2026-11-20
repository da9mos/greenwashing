from pathlib import Path
import json,sys,importlib.util,re,hashlib
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf
src=json.load(open('source.json'))
program=Path(src['source_pdf']).parent.parent/'tools/native_candidate.py'
code=program.read_text()
# Resolve only nested detector rectangles, using their existing edges.
patch='''        original_positions = positions
        ex = sorted({r[0] for r in positions} | {r[2] for r in positions})
        ey = sorted({r[1] for r in positions} | {r[3] for r in positions})
        owners = {}
        for yi in range(len(ey)-1):
            for xi in range(len(ex)-1):
                x, y = (ex[xi]+ex[xi+1])/2, (ey[yi]+ey[yi+1])/2
                candidates = [r for r in positions if r[0] < x < r[2] and r[1] < y < r[3]]
                if candidates:
                    owners[yi,xi] = min(candidates, key=lambda r: ((r[2]-r[0])*(r[3]-r[1]),r))
        tiles = {}
        for yi in range(len(ey)-1):
            xi=0
            while xi < len(ex)-1:
                owner=owners.get((yi,xi))
                if owner is None:
                    xi+=1
                    continue
                end=xi+1
                while end<len(ex)-1 and owners.get((yi,end))==owner:
                    end+=1
                key=(owner,xi,end)
                if key in tiles and tiles[key][-1][1]==yi:
                    tiles[key][-1][1]=yi+1
                else:
                    tiles.setdefault(key,[]).append([yi,yi+1])
                xi=end
        positions=defaultdict(list)
        for (owner,x0,x1), runs in tiles.items():
            for y0,y1 in runs:
                positions[(ex[x0],ey[y0],ex[x1],ey[y1])]=[(y0,x0)]
'''
needle='        values = {rect: [] for rect in positions}'
assert needle in code
local=Path('result/_проверка/native_candidate_repaired.py');local.write_text(code.replace(needle,patch+needle))
def module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
orig=module(program,'original');fixed=module(local,'fixed')
report=Path('result/report.md');text=report.read_text();parts=re.split(r'(<!-- pdf_page: \d+ -->)',text)
registry=json.load(open('result/_проверка/pages.json'));doc=pymupdf.open(src['source_pdf']);log=[]
for entry in registry['pages']:
 n=entry['pdf_page'];entry['review_status']='pending';entry['semantic_source_review_completed']=False
 if not entry.get('ambiguous_cell_assignments'):continue
 before,old=orig.convert_page(doc[n-1]);after,new=fixed.convert_page(doc[n-1]);k=2*n

 if before not in parts[k]:
  log.append({'page':n,'status':'skipped: candidate differs from current common program; original kept'})
  print(n,'skipped',flush=True)
  continue
 parts[k]=parts[k].replace(before,after,1)
 entry['original_ambiguous_assignments_count']=len(entry['ambiguous_cell_assignments'])
 entry['geometry_repair']={'method':'partition overlapping detector rectangles along source edges; smallest containing rectangle owns each elementary area','native_glyph_accounting_passed':new['all_native_glyphs_assigned_once'],'rendered_character_inventory_matches':new['rendered_native_character_inventory_matches'],'remaining_ambiguous_assignments':len(new['ambiguous_cell_assignments']),'semantic_review':'pending'}
 log.append({'page':n,'before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':hashlib.sha256(after.encode()).hexdigest(),'original_ambiguous':len(old['ambiguous_cell_assignments']),'remaining_ambiguous':len(new['ambiguous_cell_assignments'])})
 print(n,'repaired',flush=True)
report.write_text(''.join(parts));Path('result/_проверка/pages.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2));Path('result/_проверка/geometry_repairs.json').write_text(json.dumps(log,ensure_ascii=False,indent=2))
