exec(open('result/_проверка/repair.py').read().split("report=Path('result/report.md')")[0])
from collections import Counter
from bs4 import BeautifulSoup
report=Path('result/report.md');parts=re.split(r'(<!-- pdf_page: \d+ -->)',report.read_text());doc=pymupdf.open(src['source_pdf']);log=[]
for n in [84,141]:
 k=n*2;c=parts[k];m=re.search(r'<a id="pdf-page-\d+"></a>\s*',c);start=m.end();ends=[c.find(x,start) for x in ['> Служебная','<details>']];end=min(x for x in ends if x>=0);native=c[start:end].strip();after,new=fixed.convert_page(doc[n-1]);chars=lambda t:Counter(x for x in BeautifulSoup(t,'html.parser').get_text() if not x.isspace())
 if chars(native)!=chars(after):print(n,'DIFFERENCE',chars(native)-chars(after),chars(after)-chars(native));continue
 parts[k]=c[:start]+after+'\n\n'+c[end:];log.append({'page':n,'native_inventory_matches':True,'repair':'same partition repair; replaced whole native region after exact character multiset comparison'})
 print(n,'repaired')
report.write_text(''.join(parts));Path('result/_проверка/remaining_geometry_repairs.json').write_text(json.dumps(log,ensure_ascii=False,indent=2))
