import json,subprocess
from pathlib import Path
s=json.loads(Path('source.json').read_text());out=Path('result/_проверка/layout-tables');out.mkdir(exist_ok=True)
nums=sorted({13,14,15,17,22,24,25,27,34,38,39,40,41,42,43,54,55,56,66,67,68,70,73,74,76,85,86,87,90,95,96,*range(113,134)})
for n in nums:
 parts=[]
 for x in [0,595]:
  cmd=['pdftotext','-f',str(n),'-l',str(n),'-r','72','-x',str(x),'-y','75','-W','595','-H','725','-layout','-enc','UTF-8',s['source_pdf'],'-']
  t=subprocess.run(cmd,capture_output=True,text=True,check=True).stdout.replace('\f','').strip('\n')
  parts.append('```text\n'+t+'\n```')
 (out/f'{n:04}.md').write_text('\n\n'.join(parts))
print(len(nums))
