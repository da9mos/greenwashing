from pathlib import Path
code=Path('result/_проверка/tables.py').read_text().split('counts={};records=[]')[0]
code=code.replace("rows=[]\n for ya,yb", "bands=[item[1] for dr in p.get_drawings() for item in dr['items'] if item[0]=='re' and item[1].width>xs[-1]-xs[0]-5]\n rows=[]\n for ya,yb")
code=code.replace("cells=[p.get_textbox", "if any(q.y0-.5<=ya and q.y1+.5>=yb for q in bands):\n   text=p.get_textbox(f.Rect(xs[0]+.2,ya+.2,xs[-1]-.2,yb-.2));rows.append('<tr><td colspan=\"'+str(len(xs)-1)+'\">'+clean(text)+'</td></tr>');continue\n  cells=[p.get_textbox")
code=code.replace("for path in (r/'_проверка/before-tables').glob('*.md'):shutil.copyfile(path,r/'_проверка/pages'/path.name)",'')
code=code.replace(')*.94',')*.75')
exec(code)
for n in range(117,128):
 p=d[n-1];xs=[39.685,113.5,654.9,1150.87] if n<=118 else [39.685,181.417,651.024,857.857,1150.87];ymin=238 if n==117 else 94
 table=grid(p,xs,ymin);prefix=p.get_text(clip=f.Rect(0,70,p.rect.width,ymin)).strip() if n==117 else '';new=prefix+'\n\n'+table
 if n==127:new+='\n\n'+p.get_text(clip=f.Rect(0,530,p.rect.width,805)).strip()
 path=r/f'_проверка/pages/{n:04}.md';match=re.search(r'(<a id="pdf-page-'+str(n)+r'"></a>\n\n)(.*?)(\n\n> Техническая пометка:)',report,re.S);assert match,n;report=report[:match.start(2)]+new+report[match.end(2):];path.write_text(new+'\n')
(r/'report.md').write_text(report)
