import sys,json,re,collections,html
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs');import pymupdf as f
s=json.loads(Path('source.json').read_text());d=f.open(s['source_pdf']);out=Path('result/_проверка');rows=[]
for path in sorted((out/'refined').glob('*.md')):
 n=int(path.stem);p=d[n-1]; raw=p.get_text(clip=f.Rect(0,75,p.rect.width,800))
 md=html.unescape(re.sub('<[^>]+>',' ',path.read_text()))
 def chars(t): return collections.Counter(re.findall('[а-яА-ЯёЁ0-9]',t.lower()))
 a,b=chars(raw),chars(md);diff=a-b;ratio=sum(diff.values())/max(sum(a.values()),1)
 rows.append({'pdf_page':n,'missing_character_fraction':round(ratio,4),'source_chars':sum(a.values()),'output_chars':sum(b.values()),'missing_characters':dict(diff)})
(out/'coverage.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print([(r['pdf_page'],r['missing_character_fraction']) for r in rows if r['missing_character_fraction']>.02])
