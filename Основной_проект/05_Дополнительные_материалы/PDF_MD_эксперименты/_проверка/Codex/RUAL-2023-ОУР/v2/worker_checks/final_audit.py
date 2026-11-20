from pathlib import Path
import json,sys,re,hashlib,collections
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1];s=(root/'report.md').read_text();parts=re.split(r'(?=<!-- pdf_page: \d+ -->)',s)
r=json.load(open(root/'_проверка/pages.json'));audit=[]
for p in r['pages']:
 n=p['pdf_page'];soup=BeautifulSoup(parts[n],'html.parser');tables=soup.find_all('table');flags=[]
 for i,t in enumerate(tables,1):
  cells=t.find_all(['td','th']);empty=sum(not c.get_text(strip=True) for c in cells)
  if cells and empty/len(cells)>.35:flags.append({'table':i,'reason':'many_empty_cells','empty':empty,'total':len(cells)})
  widths=[];active={}
  for row in t.find_all('tr'):
   occupied={k for k,v in active.items() if v>0};new={k:v-1 for k,v in active.items() if v>1};x=0
   for c in row.find_all(['td','th'],recursive=False):
    while x in occupied:x+=1
    cs=int(c.get('colspan',1));rs=int(c.get('rowspan',1))
    for k in range(x,x+cs):
     occupied.add(k)
     if rs>1:new[k]=max(new.get(k,0),rs-1)
    x+=cs
   widths.append(max(occupied)+1 if occupied else 0);active=new
  if len(set(widths))>1:flags.append({'table':i,'reason':'inconsistent_logical_row_width','widths':widths})
 p['final_table_count']=len(tables);p['final_table_structure_flags']=flags
 if flags:
  audit.append({'pdf_page':n,'flags':flags})
  p['issues'].append('Автоматический контроль финальных таблиц: много пустых ячеек или неодинаковая логическая ширина строк; требуется сверка геометрии по оригиналу.')
  if p['review_status']=='checked':raise AssertionError(('checked with table flags',n))
 if p['original_diagnostics']:
  p['diagnostic_resolution']='Source image inspected; page-specific corrections recorded. Full source comparison '+('completed.' if p['review_status']=='checked' else 'pending for remaining objects.')
 p['render_review_status']='pending'
# Verify copied source image content against mechanically prepared index.
src=json.load(open(root.parent/'source.json'));idx=json.load(open(src['index']));mismatches=[]
for p in idx['pages']:
 asset=root/f"assets/page_{p['pdf_page']:04}.png"
 if hashlib.sha256(asset.read_bytes()).hexdigest()!=p['image_sha256']:mismatches.append(p['pdf_page'])
assert not mismatches,mismatches
(root/'_проверка/pages.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
(root/'_проверка/table_structure_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
coverage=json.load(open(root/'_проверка/native_coverage.json'));coverage['report_sha256_scope']='Original mechanical candidate, archived as versions/report.native.md';coverage['final_report_sha256']=hashlib.sha256(s.encode()).hexdigest();coverage['final_semantic_review']='See pages.json and review_summary.json; original character-accounting result does not certify corrected final order or table relations.';(root/'_проверка/native_coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n')
summary=json.load(open(root/'_проверка/review_summary.json'));summary['all_original_diagnostic_records_inspected']=True;summary['source_images_hash_verified']=206;summary['table_structure_flagged_pages']=[x['pdf_page'] for x in audit];summary['display_review']='Markdown rendered locally to HTML; headless Chrome exited 134 before screenshot. Visual display review not completed.';(root/'_проверка/review_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print('Original source image hashes verified:',len(idx['pages']));print('Table structure flagged pages:',[x['pdf_page'] for x in audit])
