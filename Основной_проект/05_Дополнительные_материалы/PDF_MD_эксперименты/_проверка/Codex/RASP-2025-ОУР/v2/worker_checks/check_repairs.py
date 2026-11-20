import runpy,collections,re,json,sys
v=runpy.run_path('result/_проверка/review_repairs.py');sys.path.insert(0,'/private/tmp/sber-diff-libs');from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
M=MarkdownIt('commonmark',{'html':True})
for n in [18,47,52,54,57,62,89,99,118,165,183]:
 body=v['P'][n].split('> Служебная информация: ссылки')[0].split('<details>')[0]
 src=''.join(u['text'] for u in v['U'](n) if u['bbox'][1]>80)
 out=BeautifulSoup(M.render(body),'html.parser').get_text()
 f=lambda t:collections.Counter(c for c in t if not c.isspace())
 miss=f(src)-f(out);extra=f(out)-f(src)
 print(n,'missing',dict(miss),'extra',dict(extra))
 if n in [18,54,57,62,89,118]:print(BeautifulSoup(M.render(body),'html.parser').get_text(' ',strip=True))
