from pathlib import Path
from collections import Counter
import json,re,csv,hashlib
import argparse
ap=argparse.ArgumentParser();ap.add_argument('output');args=ap.parse_args();p=Path(args.output)
def nums(s):
 s=s.translate(str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹','          '));return Counter(re.findall(r'(?<!\w)\d+(?:[,.]\d+)?',s))
summary=[];allrows=[]
for name,root in [(p.name,p)]:
 local=json.loads((root/'local_manifest.json').read_text());cloud=json.loads((root/'cloud/result.json').read_text());pages=cloud['markdown']['pages'];assert len(pages)==local['page_count'];assert sorted(v['page_number']for v in pages)==list(range(1,local['page_count']+1));cr={v['page_number']:v['markdown']for v in pages};rows=[]
 for n in range(1,local['page_count']+1):
  lm=(root/'local_pages'/f'{n:03d}.md').read_text();raw=json.loads((root/'local_pages'/f'{n:03d}.json').read_text())['raw_text'];cm=cr[n];a=nums(lm);b=nums(cm)
  common=sum((a&b).values());den=sum((a|b).values());overlap=common/den if den else 1
  row={'report':name,'pdf_page':n,'raw_chars':len(raw),'local_chars':len(lm),'cloud_chars':len(cm),'local_table_rows':sum(l.startswith('|')for l in lm.splitlines()),'cloud_table_rows':sum(l.startswith('|')for l in cm.splitlines()),'numeric_token_overlap_signal':round(overlap,3),'only_local_numeric_tokens':' '.join((a-b).elements()),'only_cloud_numeric_tokens':' '.join((b-a).elements()),'review_trigger':';'.join(x for x,yes in [('empty_local',len(raw.strip())>80 and not lm.strip()),('empty_cloud',len(raw.strip())>80 and not cm.strip()),('number_difference',overlap<.8),('table_row_difference',abs(sum(l.startswith('|')for l in lm.splitlines())-sum(l.startswith('|')for l in cm.splitlines()))>5)]if yes)}
  rows.append(row)
 allrows.extend(rows);summary.append({'report':name,'pages':len(rows),'local_md_bytes':(root/'01_local.md').stat().st_size,'cloud_md_bytes':(root/'02_llamaparse.md').stat().st_size,'local_errors':sum(bool(v['error'])for v in local['pages']),'empty_cloud_where_raw_nonempty':sum('empty_cloud'in r['review_trigger']for r in rows),'triggered_pages':sum(bool(r['review_trigger'])for r in rows),'numeric_difference_pages':sum('number_difference'in r['review_trigger']for r in rows),'cloud_job_id':cloud['job']['id'],'local_seconds':round(local['seconds'],2),'source_sha256':local['source_sha256']})
 # save table cells as independent JSON, not flattened MD only
 tables=[]
 for pg in cloud['items']['pages']:
  for i,it in enumerate(pg['items']):
   if it.get('type')=='table':tables.append({'pdf_page':pg['page_number'],'item_index':i,**it})
 (root/'cloud/tables.json').write_text(json.dumps(tables,ensure_ascii=False));summary[-1]['cloud_tables']=len(tables)
with(p/'page_comparison.csv').open('w',encoding='utf-8-sig',newline='')as f:
 w=csv.DictWriter(f,fieldnames=list(allrows[0]),delimiter=';');w.writeheader();w.writerows(allrows)
(p/'comparison_summary.json').write_text(json.dumps({'reports':summary,'total_pdf_pages':len(allrows),'all_pages_compared':True,'metric_warning':'Numeric token overlap is a triage signal, not accuracy/recall; PDF raw text and both parsers may be wrong. Manual review is required.','estimated_base_credits':len(allrows)*10},ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False))
