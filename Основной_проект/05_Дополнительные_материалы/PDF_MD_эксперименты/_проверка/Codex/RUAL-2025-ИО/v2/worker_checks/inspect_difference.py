exec(open('result/_проверка/repair.py').read().split("report=Path('result/report.md')")[0])
import difflib
parts=re.split(r'<!-- pdf_page: \d+ -->',Path('result/_проверка/baseline/report.md').read_text());doc=pymupdf.open(src['source_pdf'])
for n in [84,141]:
 before,old=orig.convert_page(doc[n-1]);actual=parts[n];start=actual.find(before[:80]);actual=actual[start:];end=actual.find('> Служебная информация:');actual=actual[:end] if end>=0 else actual
 print(n)
 print('\n'.join(list(difflib.unified_diff(before.splitlines(),actual.strip().splitlines()))[:110]))
