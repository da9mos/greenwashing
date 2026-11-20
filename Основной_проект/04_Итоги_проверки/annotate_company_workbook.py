"""Keep concise visible evidence, with clickable sources and full URLs in Excel cell notes."""
from pathlib import Path
import json,sys
from openpyxl import load_workbook
from openpyxl.comments import Comment

filename=Path(sys.argv[1]);data=json.loads(Path(sys.argv[2]).read_text())
book=load_workbook(filename)
expected=[]
for year in data['sheets']:
    sheet=book[year['title']]
    for number,citation in enumerate(year.get('citations',[]),2):
        page=citation['pages'][0]
        quote_url=citation['quote_url']
        if '#' not in quote_url: quote_url+=f'#page={page}'
        cell=sheet[f'B{number}'];cell.hyperlink=quote_url
        cell.comment=Comment(f"Источник цитаты, физическая страница {page}:\n{quote_url}",'Источники')
        sources=citation.get('external_sources',[])
        if sources:
            cell=sheet[f'F{number}'];cell.hyperlink=sources[0]['url']
            note='\n\n'.join(f"{s.get('name',s.get('publisher','Источник'))}: {s['url']}\n{s.get('assertion','')}" for s in sources)
            cell.comment=Comment(note,'Источники');cell.comment.width=600;cell.comment.height=280
        expected.append((year['title'],number,quote_url,sources))
book.save(filename)
readback=load_workbook(filename)
for year,row,quote_url,sources in expected:
    assert readback[year][f'B{row}'].hyperlink.target==quote_url
    assert readback[year][f'B{row}'].comment.text.endswith(quote_url)
    if sources:
        assert readback[year][f'F{row}'].hyperlink.target==sources[0]['url']
        assert all(s['url'] in readback[year][f'F{row}'].comment.text for s in sources)
