from pathlib import Path
import json,re,hashlib,csv,difflib,html,unicodedata
from collections import Counter
import sys
from rapidfuzz.distance import Levenshtein
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
P=Path('11_Проект_Сбер/3_итерация/greenwashing/03_итерация_3_пайплайн');O=P/'outputs/gazprom_2023_deepseek';(O/'char_diff').mkdir(exist_ok=True)
renderer=MarkdownIt('commonmark',{'html':True}).enable('table')
def render(md):
 s=BeautifulSoup(renderer.render(md),'html.parser')
 for tag in s.find_all(['script','style','iframe','object','embed','img']):tag.decompose()
 for tag in s.find_all(True):
  for attr in list(tag.attrs):
   if attr not in ['colspan','rowspan','href']:del tag.attrs[attr]
   elif attr=='href'and not re.match(r'^(https?://|#)',str(tag[attr])):del tag.attrs[attr]
 return str(s)
def split_baseline(report):
 text=(O/'baseline'/f'{report}.md').read_text();parts=re.split(r'<!-- pdf_page: (\d+);[^>]*-->\n## PDF-страница \d+\n\n',text)
 return {int(parts[i]):parts[i+1].rstrip()for i in range(1,len(parts),2)}
def visible(s):
 x=BeautifulSoup(render(s),'html.parser').get_text(' ',strip=True);return ' '.join(unicodedata.normalize('NFC',x).split())
def nums(s):
 x=BeautifulSoup(render(s),'html.parser')
 for t in x.find_all('sup'):t.decompose()
 x=x.get_text(' ',strip=True).translate(str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹','          '))
 return Counter(re.findall(r'(?<!\w)[+−–-]?\d+(?:[,.]\d+)?',x))
rows=[];web=[];man=[];allinitial=[];allselected=[]
for report,total in [('social',136),('environment',84)]:
 baseline=split_baseline(report);initial=[];selected=[]
 for n in range(1,total+1):
  f=O/'v1'/f'{report}_{n:03d}.json'
  if not f.exists():continue
  r=json.loads(f.read_text());v2=O/'v2'/f'{report}_{n:03d}.json';selection=json.loads((O/'selection.json').read_text())if (O/'selection.json').exists()else{}; selected_path=O/selection.get(f'{report}_{n:03d}',{}).get('file',str(f.relative_to(O)));chosen=json.loads(selected_path.read_text())
  a=baseline[n];b=r['response']['markdown'].rstrip();bfinal=chosen['response']['markdown'].rstrip()
  for version,new in [('v1',b),('selected',bfinal)]:
   ops=Levenshtein.opcodes(a,new);d=[];rebuild=[];edits=0
   for op in ops:
    oldseg=a[op.src_start:op.src_end];newseg=new[op.dest_start:op.dest_end];rebuild.append(newseg if op.tag!='equal'else oldseg)
    if op.tag!='equal':d.append({'operation':op.tag,'old_start':op.src_start,'old_end':op.src_end,'new_start':op.dest_start,'new_end':op.dest_end,'old':oldseg,'new':newseg});edits+=max(len(oldseg),len(newseg))
   assert ''.join(rebuild)==new
   (O/'char_diff'/f'{report}_{n:03d}_{version}.json').write_text(json.dumps({'report':report,'pdf_page':n,'comparison':version,'baseline_sha256':hashlib.sha256(a.encode()).hexdigest(),'candidate_sha256':hashlib.sha256(new.encode()).hexdigest(),'unicode_character_diff':True,'reconstruction_verified':True,'changes':d},ensure_ascii=False))
   if version=='selected':dist=Levenshtein.distance(a,new)
  va,vb=visible(a),visible(bfinal);na,nb=nums(a),nums(bfinal)
  missing=list((na-nb).elements());added=list((nb-na).elements())
  row={'report':report,'pdf_page':n,'selected_version':chosen['version'],'baseline_chars':len(a),'deepseek_chars':len(bfinal),'raw_char_distance':dist,'raw_char_similarity_signal':round(1-dist/max(len(a),len(bfinal),1),5),'visible_text_equal':va==vb,'only_baseline_numeric_tokens':' '.join(missing),'only_deepseek_numeric_tokens':' '.join(added),'model_problems':'; '.join(chosen['response'].get('problems',[])),'source_review_status':'pending_or_targeted'}
  rows.append(row);initial.append(f'<!-- pdf_page: {n} -->\n## PDF-страница {n}\n\n'+b);selected.append(f'<!-- pdf_page: {n} -->\n## PDF-страница {n}\n\n'+bfinal)
  web.append({'id':f'{report}_{n:03d}','report':report,'page':n,'version':chosen['version'],'left':render(a),'right':render(bfinal),'stats':row,'raw_left':a,'raw_right':bfinal,'diff':render('```diff\n'+''.join(difflib.unified_diff(a.splitlines(True),bfinal.splitlines(True),fromfile='Локально',tofile='DeepSeek'))+'\n```')})
 (O/f'{report}_deepseek_v1.md').write_text('# DeepSeek: '+report+' · первый независимый проход\n\n'+'\n\n'.join(initial))
 (O/f'{report}_deepseek_selected.md').write_text('# DeepSeek: '+report+' · выбранные ответы после адресных переработок\n\n'+'\n\n'.join(selected))
with(O/'page_comparison.csv').open('w',encoding='utf-8-sig',newline='')as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=';');w.writeheader();w.writerows(rows)
summary={'compared_pages':len(rows),'expected_pages':220,'all_char_diffs_reconstruct_candidate':True,'comparison_metric':'Exact Unicode character alignment + raw Levenshtein distance; difference is not proof of error or accuracy','initial_version_preserved':True,'changed_selected_pages':[r['report']+':'+str(r['pdf_page'])for r in rows if r['selected_version']!='v1'],'numeric_difference_pages':sum(bool(r['only_baseline_numeric_tokens']or r['only_deepseek_numeric_tokens'])for r in rows),'baseline_hashes':{r:hashlib.sha256((O/'baseline'/f'{r}.md').read_bytes()).hexdigest()for r in ['social','environment']}}
(O/'comparison_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(O/'review_data.json').write_text(json.dumps(web,ensure_ascii=False))
print(json.dumps(summary,ensure_ascii=False))
