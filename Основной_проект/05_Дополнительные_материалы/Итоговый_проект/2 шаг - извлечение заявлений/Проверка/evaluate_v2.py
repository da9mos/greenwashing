"""Evaluate independently adjudicated one-to-one matches; never infer a gold standard."""
import argparse
import json
from pathlib import Path


def evaluate(data):
    if data.get('human_gold_complete') is not True:
        raise ValueError('Нужен завершённый независимый человеческий эталон')
    gold, predicted = data['gold'], data['predicted']
    def index(rows):
        result = {}
        for row in rows:
            if not isinstance(row.get('id'), str) or row['id'] in result:
                raise ValueError('Неверный или повторный id')
            if row.get('type') not in ('обязательство','результат','декларация') or row.get('primary_topic') not in ('E','S','G',None):
                raise ValueError('Неверная метка')
            result[row['id']] = row
        return result
    g, p = index(gold), index(predicted)
    pairs = data['adjudicated_matches']
    gs, ps = set(), set()
    for a,b in pairs:
        if a not in g or b not in p or a in gs or b in ps:
            raise ValueError('Сопоставление должно быть один-к-одному и содержать существующие id')
        gs.add(a); ps.add(b)
    def divide(a,b): return a/b if b else None
    result = {'gold':len(g),'predicted':len(p),'matched':len(pairs),
              'precision':divide(len(pairs),len(p)), 'recall':divide(len(pairs),len(g)),
              'missed_ids':sorted(set(g)-gs),'extra_ids':sorted(set(p)-ps)}
    for field, labels in [('type',('обязательство','результат','декларация')),('primary_topic',('E','S','G'))]:
        metrics = {}
        for label in labels:
            tp=sum(g[a][field]==label and p[b][field]==label for a,b in pairs)
            fp=sum(g[a][field]!=label and p[b][field]==label for a,b in pairs)
            fn=sum(g[a][field]==label and p[b][field]!=label for a,b in pairs)
            support=sum(g[a][field]==label for a,b in pairs)
            metrics[label]={'support':support,'precision':divide(tp,tp+fp),'recall':divide(tp,tp+fn),'f1':divide(2*tp,2*tp+fp+fn)}
        result[field]={'per_label':metrics,'macro_f1':sum((x['f1'] or 0) for x in metrics.values())/len(labels),
                       'all_labels_represented':all(x['support'] for x in metrics.values()),'scope':'matched claims only'}
    correct=sum(g[a]['type']==p[b]['type'] and g[a]['primary_topic']==p[b]['primary_topic'] for a,b in pairs)
    result['end_to_end_recall']=divide(correct,len(g))
    result['end_to_end_precision']=divide(correct,len(p))
    result['limitations']='No confidence intervals, secondary-label metrics or annotator agreement computed by this tool.'
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input');args=parser.parse_args()
    print(json.dumps(evaluate(json.loads(Path(args.input).read_text())),ensure_ascii=False,indent=2))
