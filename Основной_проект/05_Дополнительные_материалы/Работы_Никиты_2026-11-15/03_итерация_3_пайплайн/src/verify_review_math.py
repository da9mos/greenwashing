"""Independent Decimal-based cross-check of resolved goal comparisons.

This does not establish semantic comparability; the 49-row source audit does.
Two explicitly justified earlier measurements and one direct achievement
statement are handled separately, never silently assigned to a later year.
"""
import argparse,csv,json
from decimal import Decimal
from pathlib import Path
P=Path(__file__).resolve().parents[1]
def check(dynamic_path):
    with Path(dynamic_path).open(encoding='utf-8-sig')as f:rows=list(csv.DictReader(f,delimiter=';'))
    with(P/'data/out/targets.csv').open(encoding='utf-8-sig')as f:targets={r['target_id']:r for r in csv.DictReader(f,delimiter=';')}
    checks=[]
    for r in rows:
        if r['status']not in {'выполнена','не выполнена'}:continue
        tid=r['target_id'];year=int(r['target_year']);basis='numeric'
        if tid=='T-MAGN-001':
            checks.append({'target_id':tid,'basis':'explicit report statement:163% of original target','passed':True});continue
        if tid in {'T-PHOR-002','T-URCH-002'}:
            year=2024;basis='officially adopted prior measurement'if tid=='T-PHOR-002'else'one-time completion before deadline'
        value=Decimal(r['value_'+str(year)]);threshold=Decimal(r['target_value']);direction=targets[tid]['direction']
        if direction not in {'down','decrease','up','increase'}:raise ValueError('Unknown direction: '+direction)
        operator='<='if direction in {'down','decrease'}else'>='
        actual=value<=threshold if operator=='<='else value>=threshold
        expected=r['status']=='выполнена'
        if actual!=expected:raise ValueError('Numeric verdict mismatch: '+tid)
        checks.append({'target_id':tid,'year':year,'value':str(value),'operator':operator,'threshold':str(threshold),'basis':basis,'passed':True})
    result={'checks':checks,'count':len(checks),'errors':0}
    (P/'data/review_v3/independent_numeric_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(f'{len(checks)} resolved goals checked; 0 mismatches')
    return result
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--dynamic',default=str(P/'data/review_v2/metrics_dynamics.csv'));args=a.parse_args();check(args.dynamic)
