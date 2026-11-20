from pathlib import Path
import sys,json,re,collections
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1]
pages=json.loads((root/'_проверка/session_input/pages.native.json').read_text())['pages'];s=(root/'report.md').read_text();parts={int(n):t for n,t in re.findall(r'<!-- pdf_page: (\d+) -->(.*?)(?=<!-- pdf_page:|\Z)',s,re.S)}
log=json.loads((root/'_проверка/corrections.json').read_text())
nums=[5,21,25,27,35,44,46,47,49,74,75,78,80,84,90,92,94,95,97,98,108,110,119,121,122,123,125,126,127,132,134,137,138,139,140,142,143,144,145,147,149,189]
for n in nums:
 t=parts[n];a=t.index('</a>')+4;b=t.find('> Служебная информация: ссылки исходного PDF');b=b if b>=0 else t.index('<details>')
 body=t[a:b];soup=BeautifulSoup(body,'html.parser');tags=[el for el in soup.contents if getattr(el,'name',None)]
 objects=pages[n-1]['objects']
 assert len(tags)==len(objects),(n,len(tags),len(objects))
 paired=list(zip(objects,tags));cuts=[315,552] if n in [125,127,189] else [283,519] if n==126 else [433] if n in [5,21,25,27,35,44,46,47,49,95,121,123,137,139,143,145,147,149] else [433 if n%2 else 400]
 header=[p for p in paired if p[0]['bbox'][3]<45]
 footer=[p for p in paired if p[0]['bbox'][1]>552]
 content=[p for p in paired if p not in header and p not in footer]
 def col(p):return sum(p[0]['bbox'][0]>=c for c in cuts)
 # Source-spanning headings/tables partition the vertical reading bands.
 spanning=[p for p in content if any(p[0]['bbox'][0]<c-1 and p[0]['bbox'][2]>c+1 for c in cuts)]
 ordered=header[:];remaining=content[:]
 for sp in sorted(spanning,key=lambda p:p[0]['bbox'][1]):
  if sp not in remaining:continue
  before=[p for p in remaining if p not in spanning and (p[0]['bbox'][1]+p[0]['bbox'][3])/2<sp[0]['bbox'][1]]
  ordered+=sorted(before,key=lambda p:(col(p),p[0]['bbox'][1],p[0]['bbox'][0]))+[sp]
  remaining=[p for p in remaining if p not in before and p!=sp]
 ordered+=sorted(remaining,key=lambda p:(col(p),p[0]['bbox'][1],p[0]['bbox'][0]))+footer
 assert len(ordered)==len(paired)
 newbody='\n\n'.join(str(tag) for _,tag in ordered)
 assert collections.Counter(BeautifulSoup(body,'html.parser').get_text())==collections.Counter(BeautifulSoup(newbody,'html.parser').get_text()) or collections.Counter(c for c in BeautifulSoup(body,'html.parser').get_text() if not c.isspace())==collections.Counter(c for c in BeautifulSoup(newbody,'html.parser').get_text() if not c.isspace())
 parts[n]=t[:a]+'\n\n'+newbody+'\n\n'+t[b:]
 log.append({'pdf_page':n,'change':'Порядок существующих объектов исправлен по видимым колонкам: заголовки на ширину страницы разделяют горизонтальные полосы, внутри полосы колонки читаются слева направо. Текст, глифы и ячейки не изменены. Полная пословная сверка не заявляется.','basis':'Обзор исходного макета; координаты objects механического кандидата.','cuts_pdf_points':cuts})
prefix=s[:s.index('<!-- pdf_page: 1 -->')]
(root/'report.md').write_text(prefix+''.join(f'<!-- pdf_page: {n} -->'+parts[n] for n in range(1,191)))
(root/'_проверка/corrections.json').write_text(json.dumps(log,ensure_ascii=False,indent=2))
print('reordered',len(nums))
