import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
p=Path('result/report.md');soup=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).enable('table').render(p.read_text()),'html.parser')
issues=[]
for k,t in enumerate(soup.find_all('table'),1):
 occupied={};widths=[]
 for i,row in enumerate(t.find_all('tr')):
  col=0
  for cell in row.find_all(['td','th'],recursive=False):
   while occupied.get(col,0)>i:col+=1
   w=int(cell.get('colspan',1));h=int(cell.get('rowspan',1))
   for j in range(col,col+w):
    if occupied.get(j,0)>i:issues.append({'table':k,'row':i,'error':'overlapping rowspan'})
    occupied[j]=i+h
   col+=w
  widths.append(sum(v>i for v in occupied.values()))
 if len(set(widths))>1:issues.append({'table':k,'row_widths':widths})
css='body{font:16px/1.5 sans-serif;max-width:1300px;margin:24px auto;padding:16px}table{border-collapse:collapse;min-width:600px}td,th{border:1px solid #aaa;padding:8px;vertical-align:top}.scroll{overflow-x:auto}img{max-width:100%}'
for t in list(soup.find_all('table')):
 wrap=soup.new_tag('div');wrap['class']='scroll';t.wrap(wrap)
for im in soup.find_all('img'):im['src']='../../'+im['src']
Path('result/_проверка/render/report.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+css+'</style>'+str(soup))
out={'report_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'tables':len(soup.find_all('table')),'table_grid_issues':issues,'html_generated_from_final_report':True,'browser_status':'failed: Chrome SIGABRT / TargetClosedError','screenshots':[],'visual_display_review':'pending'}
Path('result/_проверка/render/render_check.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False))
