import sys, re, json, hashlib
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1]
report=(root/'report.md').read_text()
diagnostics=json.loads((root/'_проверка/table_structure_diagnostics.json').read_text())
lookup={(d['pdf_page'],d['table']):d for d in diagnostics}
parts=re.split(r'<!-- pdf_page: (\d+) -->',report)
corrections=json.loads((root/'_проверка/corrections.json').read_text())
for i in range(1,len(parts),2):
    n=int(parts[i]);counter=[0]
    def clean(match):
        counter[0]+=1
        d=lookup.get((n,counter[0]))
        if not d:return match.group()
        empty={c-1 for c in d['empty_columns']}
        soup=BeautifulSoup(match.group(),'html.parser'); occupied=set();cells=[]
        before=[c.get_text() for c in soup.find_all(['td','th']) if c.get_text().strip()]
        for r,tr in enumerate(soup.find_all('tr')):
            c=0
            for cell in tr.find_all(['td','th'],recursive=False):
                while (r,c) in occupied:c+=1
                rs=int(cell.get('rowspan',1));cs=int(cell.get('colspan',1))
                for rr in range(r,r+rs):
                    for cc in range(c,c+cs):occupied.add((rr,cc))
                keep=sum(cc not in empty for cc in range(c,c+cs))
                cells.append((cell,keep));c+=cs
        for cell,keep in cells:
            if keep==0:
                assert not cell.get_text().strip()
                cell.decompose()
            else:cell['colspan']=str(keep)
        after=[c.get_text() for c in soup.find_all(['td','th']) if c.get_text().strip()]
        assert before==after
        d['action']='Удалены полностью пустые геометрические колонки, текст и последовательность непустых ячеек сохранены без изменения.'
        d['source_image_viewed']=True
        d['review_status']='pending'
        corrections.append({'pdf_page':n,'change':f"Таблица {counter[0]}: удалены пустые геометрические колонки {d['empty_columns']}; последовательность и содержимое всех непустых ячеек совпадают до/после.",'basis':'Просмотр общей структуры исходного изображения; пустоты определены по развёрнутой сетке rowspan/colspan. Полная сверка ячеек не выполнена.'})
        return str(soup)
    parts[i+1]=re.sub(r'<table>.*?</table>',clean,parts[i+1],flags=re.S)
report=parts[0]+''.join('<!-- pdf_page: '+parts[i]+' -->'+parts[i+1] for i in range(1,len(parts),2))
(root/'report.md').write_text(report)
(root/'_проверка/table_structure_diagnostics.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2))
(root/'_проверка/corrections.json').write_text(json.dumps(corrections,ensure_ascii=False,indent=2))
reg=json.loads((root/'_проверка/pages.json').read_text())
for x in reg['pages']:
    ds=[d for d in diagnostics if d['pdf_page']==x['pdf_page']]
    if ds:
        x['source_image_viewed']=True
        x['table_structure_review']='Просмотр общей структуры; удалены полностью пустые геометрические колонки. Все ячейки не сверены.'
        x['corrections']=[c['change'] for c in corrections if c['pdf_page']==x['pdf_page']]
        x['issues'].append('Таблицы содержали пустые геометрические колонки; после уплотнения требуется полная сверка связей ячеек и отображения.')
(root/'_проверка/pages.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2))
val=json.loads((root/'_проверка/validation.json').read_text())
val['report_sha256']=hashlib.sha256(report.encode()).hexdigest()
val['empty_geometric_columns_removed']=sum(len(d['empty_columns']) for d in diagnostics)
val['table_nonempty_cell_content_and_sequence_unchanged']=True
val['rendering_note']='Markdown преобразован в HTML локально; попытка визуального рендера Chrome завершилась кодом 134, итоговое отображение не проверено.'
(root/'_проверка/validation.json').write_text(json.dumps(val,ensure_ascii=False,indent=2))
print('Tables cleaned:',len(diagnostics),'empty geometric columns:',val['empty_geometric_columns_removed'])
