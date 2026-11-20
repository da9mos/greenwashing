import sys,json,re,collections,html,hashlib
from pathlib import Path
sys.path.insert(0,'/private/tmp/sber-pdf-libs');import pymupdf as f
s=json.loads(Path('source.json').read_text());d=f.open(s['source_pdf']);check=Path('result/_проверка');rows=[]
for n in range(1,135):
 p=d[n-1];path=check/'layout-tables'/f'{n:04}.md'
 if not path.exists():path=check/'refined'/f'{n:04}.md'
 if not path.exists() or n==112:continue
 raw=p.get_text(clip=f.Rect(0,75,p.rect.width,800));md=html.unescape(re.sub('<[^>]+>',' ',path.read_text()))
 def count(t):return collections.Counter(re.findall('[а-яА-ЯёЁ0-9]',t.lower()))
 a,b=count(raw),count(md);diff=a-b;rows.append({'pdf_page':n,'missing_character_fraction':round(sum(diff.values())/max(sum(a.values()),1),5),'missing_characters':dict(diff)})
(check/'coverage-final.json').write_text(json.dumps({'note':'Только автоматический охват букв и цифр; не проверяет порядок, таблицы или точность по оригиналу. OCR оценивается отдельно.','pages':rows},ensure_ascii=False,indent=2))
print('flagged',[(r['pdf_page'],r['missing_character_fraction']) for r in rows if r['missing_character_fraction']>.02])
print('sha_match',hashlib.sha256(Path(s['source_pdf']).read_bytes()).hexdigest()==json.loads(Path(s['index']).read_text())['source_sha256'])
