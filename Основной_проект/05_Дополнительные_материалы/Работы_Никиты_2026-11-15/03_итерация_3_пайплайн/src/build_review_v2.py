"""Rebuild the second, evidence-linked review without changing v1 outputs.

Unfinished reviews cannot change verdicts. Non-comparable observations are kept
in a separate evidence register and never substituted into comparable series.
"""
import argparse, csv, hashlib, json, re
from collections import Counter
from pathlib import Path
from build_nikita import read_csv, csv_bytes, number, has_number, verify_calculation
P=Path(__file__).resolve().parents[1]
def normalized(s):
    s=str(s or '').replace('\u00ad','').replace('ё','е')
    return re.sub(r'\s+',' ',s).strip()
def finished(r):
    return r.get('review_complete') is True or r.get('review_status') in ('complete','completed')
def observations(r):
    return r.get('observations',r.get('new_observations',[]))+r.get('supporting_evidence',[])
def serialize_reported_value(observation):
    value=observation.get('reported_value')
    if value is not None and value != '':return value
    raw=observation.get('raw_reported_value')
    return json.dumps(raw,ensure_ascii=False) if raw is not None and raw != {} else ''

def validate_observation_values(obs, target_id):
    seen={}
    for o in obs:
        if 'comparison_valid' in o and type(o['comparison_valid']) is not bool:
            raise ValueError('comparison_valid must be bool: '+target_id)
        value=o.get('value');year=o.get('year')
        if value is not None and (type(value) not in (int,float) or number(value) is None):
            raise ValueError('Non-finite or invalid value: '+target_id)
        if o.get('comparison_valid') is True and value is not None:
            if type(year) is not int or year not in (2023,2024,2025):
                raise ValueError('Invalid measurement year: '+target_id)
            if not has_number(value,o.get('quote','')) and not verify_calculation(o.get('formula',''),value,o.get('quote','')):
                raise ValueError('Comparable value is not supported by quote: '+target_id)
            n=number(value)
            if year in seen and seen[year]!=n:raise ValueError('Conflicting values for one year: '+target_id)
            seen[year]=n

def apply_audit_patch(row, patch):
    result=dict(row)
    if not patch:return result
    if not patch.get('reason') or not patch.get('observations'):
        raise ValueError('Audit patch requires evidence and reason: '+row['target_id'])
    allowed={'unit','metric','base_year','base_value','target_value','target_year','restated','comparison_operator','target_upper_bound','weight_reference_year'}
    for key,value in patch.get('set_fields',{}).items():
        if key not in allowed:raise ValueError('Unsupported audit field: '+key)
        result[key]=value
    for year in patch.get('clear_annual_values',[]):
        if type(year) is not int or year not in (2023,2024,2025):raise ValueError('Invalid cleared year')
        result['value_'+str(year)]='';result['page_'+str(year)]=''
    return result

def apply_review(row, review):
    result=dict(row)
    result.update(old_status=row.get('old_status',row['status']),review_status='завершена' if finished(review) else 'не завершена',reason_category=review.get('reason_category',''),review_reason=review.get('reason',review.get('rationale','')))
    if not finished(review):return result
    status=review.get('new_status',review.get('status',row['status']))
    if status not in {'выполнена','не выполнена','нет данных','изменена','в процессе','несопоставимая база'}:raise ValueError('Unsupported status: '+status)
    obs=observations(review)
    if status!=row['status'] and not obs:raise ValueError('Changed verdict without evidence: '+row['target_id'])
    for o in obs:
        if not isinstance(o,dict) or not o.get('report_id') or not o.get('page') or len(normalized(o.get('quote','')))<8 or not o.get('url',o.get('source_url')):
            raise ValueError('Incomplete evidence: '+row['target_id'])
    validate_observation_values(obs,row['target_id'])
    result['status']=status
    result['assessment_year']=review.get('assessment_year','')
    result['measurement_year']=review.get('measurement_year','')
    clarification=review.get('base_clarification',{})
    if clarification.get('base_year') and not result.get('base_year') and str(clarification.get('base_value'))==str(result.get('base_value')):
        result['base_year']=clarification['base_year']
    if result['review_reason']:result['comment']=result['review_reason']
    for o in obs:
        year=o.get('year')
        if o.get('comparison_valid') is True and year in (2023,2024,2025) and o.get('value') is not None:
            result['value_'+str(year)]=o['value'];result['page_'+str(year)]=o.get('page','')
    return result

def build(output_root=None):
    dest=Path(output_root) if output_root else P/'data/review_v2';dest.mkdir(parents=True,exist_ok=True)
    (dest/'validation_review.json').write_text(json.dumps({'state':'building','note':'Do not publish until state=passed'}))
    source=P/'data/review_v2'
    rows,fields=read_csv(P/'data/out/metrics_dynamics.csv')
    reviews={}; inputs=[P/'data/out/metrics_dynamics.csv',P.parent/'01_итерация_1_сбор_данных/выборка_30/reports.csv']
    for group in ('A','B'):
        path=P/f'llm/nikita_dynamics/v2/review_{group}.json'
        d=json.loads(path.read_text());inputs.append(path)
        for r in d.get('updates',d.get('reviews',[])):
            if r['target_id'] in reviews:raise ValueError('Duplicate review')
            reviews[r['target_id']]=r
    unknown=set(reviews)-{r['target_id'] for r in rows}
    if unknown:raise ValueError('Unknown target IDs: '+','.join(sorted(unknown)))
    audit_patches={}
    patch_path=P/'data/review_v3/approved_patches.json'
    if patch_path.exists():
        inputs.append(patch_path)
        for patch in json.loads(patch_path.read_text())['updates']:
            tid=patch['target_id']
            if tid not in {r['target_id'] for r in rows} or tid in audit_patches:raise ValueError('Unknown/duplicate audit patch: '+tid)
            audit_patches[tid]=patch
            r=reviews.setdefault(tid,{'observations':[]})
            existing=observations(r)
            if patch.get('supersede_prior_observations'):
                for o in existing:
                    o['superseded_by']='review_v3/'+tid;o['comparison_valid']=False
            for o in existing:o.setdefault('review_version','v2')
            new_observations=patch.get('observations',[])
            for o in new_observations:o['review_version']='v3'
            r['observations']=existing+new_observations
            r.pop('new_observations',None);r.pop('supporting_evidence',None)
            r['review_complete']=True
            r['reason']=patch['reason'];r['reason_category']=patch.get('reason_category',r.get('reason_category',''))
            r['search_log']=patch.get('search_log',r.get('search_log',r.get('reports_full_text_scanned',{})))
            if patch.get('new_status'):r['new_status']=patch['new_status']
    appendix_path=source/'norn_appendix_check.json'
    if appendix_path.exists():
        appendix=json.loads(appendix_path.read_text());inputs.append(appendix_path)
        r=reviews[appendix['target_id']]
        r['reason']='В основном отчёте раскрыто соответствие объектов размещения отходов нормативам, а не размещение отходов новых проектов. Дополнительно проверена официальная Книга приложений 2025 (41 страница): '+appendix['conclusion']
        r.setdefault('search_log',[]).append({'report_id':'NORN-2025-Книга приложений','source_type':'official_company_pdf','pages_scanned':appendix['pdf_pages'],'source_url':appendix['source_url'],'method':appendix['method']})
    caches={}
    for path in sorted(list(source.glob('source_pages_*.jsonl'))+list((P/'data/review_v3').glob('source_pages_*.jsonl'))):
        inputs.append(path)
        for line in path.read_text().split('\n'):
            if not line.strip():continue
            s=json.loads(line);caches.setdefault((s['report_id'],int(s['page'])),[]).append(s['text'])
    evidence=[];issues=[];out=[];logs=[]
    registry,_=read_csv(P.parent/'01_итерация_1_сбор_данных/выборка_30/reports.csv');registry={r['report_id']:r for r in registry}
    for row in rows:
        r=reviews.get(row['target_id'])
        if not r:
            out.append(dict(row,old_status=row.get('old_status',row['status']),review_status='сохранена проверка v1',reason_category='',review_reason=''));continue
        for o in observations(r):
            report=o.get('report_id','');page=o.get('page');quote=o.get('quote','');url=o.get('source_url',o.get('url',''))
            reg=registry.get(report)
            if not reg or reg['company_id']!=row['company_id']:issues.append(row['target_id']+': неверный отчёт')
            if reg and reg.get('drive_id') and reg['drive_id'] not in url:issues.append(row['target_id']+': URL не совпадает с реестром')
            texts=list(caches.get((report,int(page)),[])) if page is not None else []
            text=None
            if not any(normalized(quote) in normalized(t) for t in texts):
                raw=P/'data/pages'/f'{report}.jsonl'
                if raw.exists():
                    if raw not in inputs:inputs.append(raw)
                    text=next((x.get('text','') for x in map(json.loads,(line for line in raw.read_text().split('\n') if line.strip())) if str(x.get('page'))==str(page)),None)
            if text:texts.append(text)
            check=bool(quote and any(normalized(quote) in normalized(t) for t in texts))
            if not check:issues.append(row['target_id']+': цитата требует сверки '+report+':'+str(page))
            evidence.append(dict(target_id=row['target_id'],company_id=row['company_id'],year=o.get('year',''),report_id=report,page=page,value=o.get('value'),reported_value=serialize_reported_value(o),derived_value=o.get('derived_value',''),formula=o.get('formula',''),note=o.get('note',''),comparison_valid=o.get('comparison_valid',False),quote=quote,source_url=url,quote_check='совпадает' if check else 'требует сверки',review_version=o.get('review_version','v2'),superseded_by=o.get('superseded_by','')))
        out.append(apply_audit_patch(apply_review(row,r),audit_patches.get(row['target_id'])))
        logs.append(dict(target_id=row['target_id'],review_status='завершена' if finished(r) else 'не завершена',reason_category=r.get('reason_category',''),reason=r.get('reason',r.get('rationale','')),search_log=json.dumps(r.get('search_log',r.get('reports_full_text_scanned',{})),ensure_ascii=False),source_observations=len(observations(r))))
    if issues:
        (dest/'validation_errors.json').write_text(json.dumps(issues,ensure_ascii=False,indent=2))
        raise ValueError('Evidence checks failed: '+str(len(issues)))
    prior_errors=dest/'validation_errors.json'
    if prior_errors.exists():
        suffix=hashlib.sha256(prior_errors.read_bytes()).hexdigest()[:12]
        prior_errors.rename(dest/('validation_errors_archived_'+suffix+'.json'))
    fields=fields+['old_status','review_status','reason_category','review_reason','assessment_year','measurement_year','comparison_operator','target_upper_bound','weight_reference_year']
    (dest/'metrics_dynamics.csv').write_bytes(csv_bytes(out,fields))
    ef=['target_id','company_id','year','report_id','page','value','reported_value','derived_value','formula','note','comparison_valid','quote','source_url','quote_check','review_version','superseded_by']
    (dest/'evidence_review.csv').write_bytes(csv_bytes(evidence,ef))
    (dest/'review_log.csv').write_bytes(csv_bytes(logs,['target_id','review_status','reason_category','reason','search_log','source_observations']))
    targets_path=P/'data/out/targets.csv'
    if targets_path.exists():
        inputs.append(targets_path)
        targets,target_fields=read_csv(targets_path)
        target_fields+=['comparison_operator','target_upper_bound','weight_reference_year']
        byid={r['target_id']:r for r in out}
        for target in targets:
            reviewed=byid[target['target_id']]
            for field in ('unit','metric','base_year','base_value','target_value','target_year','status','comment','comparison_operator','target_upper_bound','weight_reference_year'):
                target[field]=reviewed.get(field,target.get(field,''))
        (dest/'targets_review.csv').write_bytes(csv_bytes(targets,target_fields))
    summary={'state':'passed','semantic_version':'v3' if patch_path.exists() else 'v2','target_count':len(out),'statuses':dict(Counter(r['status'] for r in out)),'review_states':dict(Counter(r['review_status'] for r in out)),'changed_statuses':[{'target_id':r['target_id'],'before':r['old_status'],'after':r['status']} for r in out if r['old_status']!=r['status']],'evidence_count':len(evidence),'evidence_issues':issues,'inputs_sha256':{str(p.relative_to(P)) if p.is_relative_to(P) else '../'+str(p.relative_to(P.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    (dest/'validation_review.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='inputs_sha256'},ensure_ascii=False,indent=2))
    return summary
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output-root');args=ap.parse_args();build(args.output_root)
