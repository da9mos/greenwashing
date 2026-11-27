import csv
import difflib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
with (HERE.parent/'Эталон_ESG.csv').open(encoding='utf-8-sig',newline='') as f:
    GOLD=list(csv.DictReader(f,delimiter=';'))

def norm(s):
    return re.sub(r'[^а-яёa-z0-9]+','',s.lower().replace('ё','е').replace('CO₂','CO2'))

def sim(a,b):
    return difflib.SequenceMatcher(None,norm(a),norm(b),autojunk=False).ratio()

def num(s):
    return s.replace(' ','').replace('\u00a0','').replace('%','').replace(',','.').lstrip('+').replace('−','-').replace('–','-')

def score(p,g):
    if bool(g['value'])!=bool(p['value']):
        return -1
    if g['value']:
        try:
            if float(num(p['value']))!=float(num(g['value'])): return -1
        except ValueError:
            return -1
        if g['period'] not in p['period']:return -1
        desc=sim(p['metric']+' '+p['locator'],g['metric']+' '+g['locator'])
        return .6+.4*desc
    quotes=json.loads(g['source_evidence'])
    q=max(sim(p['quote'],q) for q in quotes)
    if any(norm(q) in norm(p['quote']) or norm(p['quote']) in norm(q) for q in quotes) and len(norm(p['quote']))>25:
        q=max(q,.9)
    return .85*q+.15*sim(p['metric'],g['metric'])

for path in sorted(HERE.glob('*-old.json'))+sorted(HERE.glob('*-new.json')):
    if not path.stat().st_size: continue
    rid=path.stem.rsplit('-',1)[0]
    version=path.stem.rsplit('-',1)[1]
    gold=[g for g in GOLD if g['report_id']==rid]
    predictions=json.loads(path.read_text(encoding='utf-8'))['claims']
    matches=[]
    for i,p in enumerate(predictions,1):
        ranked=sorted(((score(p,g),g) for g in gold),key=lambda x:x[0],reverse=True)
        val,g=ranked[0]
        matches.append({'version':version,'report_id':rid,'prediction':i,
                        'gold_id':g['id'] if val>.37 else '', 'score':round(val,3),
                        'quote':p['quote'],'metric':p['metric'],'value':p['value'],'period':p['period'],
                        'gold_metric':g['metric'],'gold_value':g['value'],'gold_period':g['period'],
                        'block':p['block'],'gold_block':g['block'],
                        'type':p['type'],'gold_type':g['claim_type']})
    target=HERE/(path.stem+'.alignment.csv')
    with target.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(matches[0]),delimiter=';');w.writeheader();w.writerows(matches)
    print(path.stem,len(predictions),len({r['gold_id'] for r in matches if r['gold_id']}))
