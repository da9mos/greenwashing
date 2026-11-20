import sys,re,json,hashlib,html
from pathlib import Path
from collections import Counter
sys.path[:0]=['/private/tmp/sber-pdf-libs','/private/tmp/sber-diff-libs']
import pymupdf
pymupdf._layout_enabled=False
from markdown_it import MarkdownIt
root=Path(__file__).resolve().parents[2];out=root/'result';w=out/'_проверка';s=json.loads((root/'source.json').read_text());d=pymupdf.open(s['source_pdf']);r=json.loads((w/'pages.json').read_text());report=(out/'report.md').read_text();idx=json.loads(Path(s['index']).read_text())
checks={};checks['page_markers_in_order']=list(map(int,re.findall(r'<!-- pdf_page: (\d+) -->',report)))==list(range(1,117));checks['registry_complete']=[a['pdf_page'] for a in r['pages']]==list(range(1,117));checks['sha256_matches_input']=r['source_sha256']==idx['source_sha256'];checks['assets_match_input']=all(hashlib.sha256((out/a['image']).read_bytes()).hexdigest()==idx['pages'][a['pdf_page']-1]['image_sha256'] for a in r['pages']);checks['missing_local_assets']=[p for p in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',report) if not (out/p).is_file()];ids=set(re.findall(r'<a id="([^"]+)"',report));checks['missing_internal_anchors']=[p for p in re.findall(r'\]\(#([^)]+)\)',report) if p not in ids]
# Independent count of visible numeric characters in native body vs saved transcription.
counts=[]
letter_counts=[]
for i,p in enumerate(d):
 if i==114:continue
 cs=[]
 for b in p.get_text('rawdict')['blocks']:
  if b['type']!=0:continue
  for l in b['lines']:
   for sp in l['spans']:
    for c in sp['chars']:
     y=(c['bbox'][1]+c['bbox'][3])/2
     if sp['font']!='icon_font_lukoil' and (i in (0,115) or 45<=y<=735):cs.append(c['c'])
 md=(w/'pages'/f'{i+1:04}.md').read_text();md=md[md.index('\n\n',md.index('> **Техническая пометка.**')):];md=md.split('<details>')[0].split('![Физическая страница')[0];md=re.sub(r'<[^>]+>','',md)
 a=Counter(c for c in ''.join(cs) if c.isdigit());b=Counter(c for c in md if c.isdigit())
 aa=Counter(c for c in ''.join(cs) if c.isalpha());bb=Counter(c for c in html.unescape(md) if c.isalpha())
 if aa!=bb:letter_counts.append({'pdf_page':i+1,'missing':dict(aa-bb),'extra':dict(bb-aa)})
 if a!=b:counts.append({'pdf_page':i+1,'source':dict(a),'markdown':dict(b)})
checks['native_letter_count_differences']=letter_counts;checks['native_digit_count_differences']=counts;checks['tables']=report.count('<table>');checks['table_tags_balanced']=report.count('<table>')==report.count('</table>') and report.count('<tr>')==report.count('</tr>');checks['report_bytes']=(out/'report.md').stat().st_size;checks['review_status_counts']=dict(Counter(a['review_status'] for a in r['pages']));checks['conversion_status_counts']=dict(Counter(a['conversion_status'] for a in r['pages']))
(w/'validation.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
md=MarkdownIt('commonmark',{'html':True});render=md.render(report).replace('src="assets/','src="../assets/');style='body{font:16px/1.5 sans-serif;max-width:1200px;margin:30px auto;padding:20px}td{border:1px solid #bbb;padding:7px;min-width:85px}table{border-collapse:collapse}img{max-width:100%}blockquote{color:#555;background:#f3f3f3;padding:8px}h2{margin-top:40px}'
(w/'rendered.html').write_text('<!doctype html><meta charset="utf-8"><title>Проверка конвертации</title><style>'+style+'</style>'+render)
for n in [6,31,91,115]:
 text=(w/'pages'/f'{n:04}.md').read_text();text=text.split('![Физическая страница')[0]
 (w/f'preview-{n}.html').write_text('<!doctype html><meta charset="utf-8"><style>'+style+'</style>'+md.render(text))
print(json.dumps(checks,ensure_ascii=False,indent=2))
