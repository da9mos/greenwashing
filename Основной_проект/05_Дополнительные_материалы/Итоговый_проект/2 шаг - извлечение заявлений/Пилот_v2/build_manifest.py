"""Reproducible selection; automatic test-page scanning is not semantic annotation."""
import hashlib,json,random,re
from pathlib import Path
from urllib.parse import unquote
BASE=Path(__file__).resolve().parent
ROOT=next(p for p in BASE.parents if (p/'11_Проект_Сбер').exists())
INDEX=ROOT/'11_Проект_Сбер/Итоговый проект/Корпус_92_отчёта.md'
CHOICE=[('GAZP','dev','нефтегаз'),('LKOH','test','нефтегаз'),('MAGN','dev','металлургия'),('CHMF','test','металлургия'),('AKRN','dev','химия'),('PHOR','test','химия')]
def sha(b):return hashlib.sha256(b).hexdigest()
def getpages(text):
 parts=re.split(r'<!-- pdf_page: (\d+) -->',text)
 pages={}
 for i in range(1,len(parts),2):
  t=parts[i+1]
  m=re.search(r'<!-- source_text_begin -->(.*?)<!-- source_text_end -->',t,re.S)
  if m:t=m[1]
  else:
   t=re.sub(r'<details>.*?</details>','',t,flags=re.S)
   t=re.sub(r'<a id="pdf-page-\d+"></a>','',t)
   t=re.sub(r'^> (?:Техническая пометка|Служебная информация):.*$','',t,flags=re.M)
  pages[int(parts[i])]=t.strip()
 return pages
manifest={'version':1,'seed':20261117,'split_frozen_before_semantic_annotation':True,'test_semantic_read':False,'selection':'10 uniform random physical pages + 10 distinct mechanically ranked challenge pages; no claim-quality prefilter','reports':[]}
for symbol,split,sector in CHOICE:
 line=next(l for l in INDEX.read_text().splitlines() if f'[{symbol}-2023-' in l and '-ЭО]' not in l)
 match=re.search(r'\[([^]]+)\]\(([^)]+)\)',line);rid=match[1];p=(INDEX.parent/unquote(match[2])).resolve()
 raw=p.read_bytes();pages=getpages(raw.decode('utf-8-sig'));assert list(pages)==list(range(1,len(pages)+1))
 rng=random.Random(f'20261117:{rid}');random_pages=sorted(rng.sample(list(pages),10))
 def score(n):
  t=pages[n].lower()
  return (t.count('|')+t.count('<td')*3+t.count('<sup')*2+len(re.findall(r'\d+[,.]\d+',t))+sum(t.count(w)*3 for w in ['антикорруп','совет директор','персонал','обучен','выброс','эколог','планиру','цель']),-n)
 hard=sorted(sorted((n for n in pages if n not in random_pages),key=score,reverse=True)[:10]);selected=sorted(random_pages+hard)
 folder=BASE/'sources'/rid;folder.mkdir(parents=True,exist_ok=True)
 adapted='\n\n'.join(f'<!-- pdf_page: {n} -->\n<!-- source_text_begin -->\n{t}\n<!-- source_text_end -->' for n,t in pages.items())+'\n'
 (folder/'report.md').write_text(adapted)
 entry={'report_id':rid,'company':line.split('|')[1].strip(),'sector':sector,'split':split,'source_path':str(p.relative_to(ROOT)),'source_sha256':sha(raw),'adapted_path':str((folder/'report.md').relative_to(BASE)),'adapted_sha256':sha(adapted.encode()),'pages':len(pages),'random_pages':random_pages,'challenge_pages':hard,'selected_pages':selected,'adapter':'preserve source markup; remove page image details, anchors, service preamble; no OCR correction','selected_page_status':{str(n):'not_semantically_reviewed' for n in selected}}
 manifest['reports'].append(entry)
(BASE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
for annotator in ('A','B'):
 template={'annotator_id':None,'independent':True,'model_labels_visible':False,'manifest_sha256':sha((BASE/'manifest.json').read_bytes()),'status':'blank_not_annotated','reports':[{'report_id':r['report_id'],'source_sha256':r['adapted_sha256'],'pages_assigned':r['selected_pages'],'pages_reviewed':[],'claims':[],'excluded_blocks':[],'uncertain_blocks':[]} for r in manifest['reports']]}
 (BASE/f'human_{annotator}.blank.json').write_text(json.dumps(template,ensure_ascii=False,indent=2)+'\n')
print([(r['report_id'],r['split'],r['selected_pages']) for r in manifest['reports']])
