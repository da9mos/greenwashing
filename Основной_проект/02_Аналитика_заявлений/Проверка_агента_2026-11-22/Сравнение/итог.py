"""Summarize the six runs and record reviewed alignment, including split/merged claims."""
import csv
import json
from collections import Counter
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
subprocess.run([sys.executable,str(HERE/'сопоставить.py')],check=True)
with (HERE.parent/'Эталон_ESG.csv').open(encoding='utf-8-sig',newline='') as f:
    gold={r['id']:r for r in csv.DictReader(f,delimiter=';') if r['status']=='scored'}
corrections={
    'PLZL-2025-ИО-old':{
        3:['PLZL-02-level','PLZL-02-cause'],
        5:['PLZL-03','PLZL-03-power'],
        27:['PLZL-12-change','PLZL-13'],
        28:['PLZL-14-level'],30:['PLZL-17-level'],
        36:[],23:[],
    },
    'PLZL-2025-ИО-new':{
        6:['PLZL-02-level','PLZL-02-cause'],
        9:['PLZL-03-power'],29:['PLZL-08'],30:['PLZL-08-power'],
        32:['PLZL-12-change','PLZL-13'],
        33:['PLZL-14-level'],35:['PLZL-17-level'],
        40:['PLZL-11-climate'],41:[],62:['PLZL-25'],
    },
}
summary=[]
review=[]
for stem in ['KMAZ-2024-ОУР','ALRS-2024-ОУР','PLZL-2025-ИО']:
    for version in ('old','new'):
        name=f'{stem}-{version}'
        data=json.loads((HERE/(name+'.json')).read_text(encoding='utf-8'))['claims']
        meta=json.loads((HERE/(name+'.meta.json')).read_text(encoding='utf-8'))
        with (HERE/(name+'.alignment.csv')).open(encoding='utf-8-sig') as f:
            aligned=list(csv.DictReader(f,delimiter=';'))
        covered=set()
        for index,(pred,match) in enumerate(zip(data,aligned),1):
            ids=corrections.get(name,{}).get(index,[match['gold_id']] if match['gold_id'] in gold else [])
            covered.update(ids)
            note=''
            if stem.startswith('KMAZ') and 6<=index<=10:
                note='Пять регулирующих документов соответствуют одной групповой записи KMAZ-06.'
            if name=='KMAZ-2024-ОУР-new' and index==19:
                note='Лишний повтор функции из записи 18.'
            if stem.startswith('PLZL') and index in ((36,) if version=='old' else (41,)):
                note='Пограничный форум: исключён из численной оценки по эталону.'
            if name=='PLZL-2025-ИО-old' and index==23:
                note='Дополнительное раскрытие сноски о периметре. Сохранено как контекст графика.'
            if stem.startswith('PLZL') and ((version=='old' and index in (3,5,27)) or (version=='new' and index in (6,32))):
                note='Связанный тезис присутствует в цитате. Отдельное аналитическое поле ему не выделено.'
            review.append(dict(run=name,prediction=index,gold_ids=','.join(ids),quote=pred['quote'],
                               locator=pred['locator'],note=note))
        expected={k for k,v in gold.items() if v['report_id']==stem}
        numeric={k for k in expected if gold[k]['value']}
        assert expected<=covered,(name,expected-covered)
        summary.append(dict(run=name,raw_records=len(data),source_coverage=len(expected&covered),
                            gold_records=len(expected),numeric_coverage=len(numeric&covered),
                            numeric_expected=len(numeric),elapsed_seconds=round(meta['elapsed_seconds'],3)))
with (HERE/'Проверенное_сопоставление.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(review[0]),delimiter=';')
    writer.writeheader();writer.writerows(review)
(HERE/'Результаты.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
