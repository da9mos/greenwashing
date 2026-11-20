from pathlib import Path
import sys,json,re,hashlib,collections,shutil
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
root=Path('result');audit=root/'_проверка';path=root/'report.md';s=path.read_text();changes=json.load(open(audit/'changes.json'))
# Recover the first financial table only, using existing source-glyph strings.
m=re.search(r'<!-- pdf_page: 169 -->(.*?)(?=<!-- pdf_page:|\Z)',s,re.S);part=m[1]
a=part.index('<table>');z=part.index('</table>',a)+len('</table>');table=BeautifulSoup(part[a:z],'html.parser');rows=table.select('tr')
new='<p>(тыс. руб.)</p>\n<table>\n<thead><tr><th rowspan="2">Наименование</th><th colspan="2">За 2024 год</th><th colspan="2">За 2023 год</th></tr><tr><th>Поступило</th><th>Выбыло</th><th>Поступило</th><th>Выбыло</th></tr></thead>\n'
side=[]
for row in rows[2:]:
 cells=row.find_all('td',recursive=False)
 assert len(cells)==3
 if cells[0].get_text().strip():side.append(str(cells[0].decode_contents()))
 label=str(cells[1].decode_contents());values=str(cells[2].decode_contents()).split('<br/>')
 labels=[label]
 if len(values)==8:
  labels=label.split('<br/>',1);assert labels[0]=='Сооружения'
 assert len(values)==4*len(labels),(label,values)
 for k,l in enumerate(labels):new+='<tr><td>'+l+'</td>'+''.join('<td>'+v+'</td>' for v in values[k*4:k*4+4])+'</tr>\n'
new+='</table>\n'+''.join('<p>'+x+'</p>\n' for x in side)
part=part[:a]+new+part[z:];s=s[:m.start(1)]+part+s[m.end(1):]
changes.append({'page':169,'change':'First movement-of-fixed-assets table: restored four numeric columns and two year headings; split the two merged asset rows, retaining source-glyph strings. Remaining tables on page pending.'})
# Remove only explicit empty first-column continuation cells by extending the preceding source standard.
for n in range(111,116):
 m=re.search(r'<!-- pdf_page: '+str(n)+r' -->(.*?)(?=<!-- pdf_page:|\Z)',s,re.S);part=m[1]
 def repair_span(mt):
  soup=BeautifulSoup(mt[0],'html.parser');tab=soup.table;last=None;remaining=0
  for row in tab.find_all('tr',recursive=False):
   cells=row.find_all('td',recursive=False)
   if not cells:continue
   if int(cells[0].get('colspan',1))==4:last=None;remaining=0;continue
   if remaining>0:remaining-=1;continue
   first=cells[0]
   if len(cells)==4 and not first.get_text().strip() and last is not None:
    last['rowspan']=str(int(last.get('rowspan',1))+1);first.decompose()
   else:
    last=first if first.get_text().strip().startswith('GRI') else None
    remaining=int(first.get('rowspan',1))-1
  return str(tab)
 part=re.sub(r'<table>.*?</table>',repair_span,part,flags=re.S)
 s=s[:m.start(1)]+part+s[m.end(1):]
path.write_text(s)
(audit/'changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
original=audit/'pages.native-original.json'
if not original.exists():shutil.copyfile(audit/'pages.json',original)
data=json.load(open(original));reviewed={1,2,9,13,20,27,34,48,56,58,73,80,85,94,100,106,109,111,112,113,114,115,116,166,167,169};checked={1,2,109}
for p in data['pages']:
 n=p['pdf_page'];oldissues=p.get('issues',[]);p['native_diagnostics_original']=oldissues
 p['conversion_status']='converted';p['review_status']='checked' if n in checked else 'pending';p['semantic_source_review_completed']=n in checked
 p['verification_scope']='Complete source-page text/structure review' if n in checked else ('Targeted source-image diagnostic review; not complete page verification' if n in reviewed else 'Native mechanical conversion only; source semantic review pending')
 p['source_image_reviewed']=n in reviewed;p['diagnostics_reviewed']=True
 p['issues']=[] if n in checked else ['Полная сверка текста, порядка чтения, таблиц и графики по оригиналу не завершена.']
 if n in reviewed:p['reviewed_objects']=['Диагностические участки по исходному изображению; см. changes.json; статус всей страницы не повышен по частичной проверке.']
 if n in range(111,116):p['issues'].append('Столбцы GRI восстановлены по геометрии; нужна полная построчная сверка объединений и продолжений.')
 if n==169:p['issues'].append('Первая таблица движения основных средств восстановлена; прочие таблицы сохраняют слитые числовые колонки и требуют восстановления связей.')
 if n in [9,27,34,48,56,58,80,85,94,100,106,109]:p['ocr_review']={'scope':'OCR overlay compared with source image and native body','decision':'Removed duplicate/error overlay; body retained from native text layer','full_page_ocr_accuracy_claimed':False}
 p['final_unresolved_unicode']=0
 if n==1:p['printed_label']=None
 elif n==2:p['printed_label']='3'
 elif n in reviewed:p['printed_label']=f'{2*n-2}, {2*n-1}'
 else:p['printed_label']=None;p['printed_label_status']='pending: not visually established'
 p['source_content_type']='native_text_with_graphics';p['layout_review_status']='checked' if n in checked else 'pending'
data['summary']={'physical_pages':172,'converted_pages':172,'fully_source_checked_pages':sorted(checked),'targeted_source_image_review_pages':sorted(reviewed),'review_pending_pages':169,'render_status':'blocked: local Chrome launch SIGABRT / EPERM','document_status':'working_copy'}
(audit/'pages.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
# Structural validation of the saved final version.
markers=[int(x) for x in re.findall(r'<!-- pdf_page: (\d+) -->',s)];assert markers==list(range(1,173))
refs=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',s);missing=[x for x in refs if not (root/x).is_file()];assert not missing
ids=set(re.findall(r'id="([^"]+)"',s));targets=re.findall(r'(?:href="|\]\()#([^"\)]+)',s);broken=[x for x in targets if x not in ids];assert not broken
weird=[(hex(ord(c)),s.count(c)) for c in set(s) if c=='\ufffd' or 0xe000<=ord(c)<=0xf8ff or ord(c)<32 and c not in '\n\r\t'];assert not weird
cfg=json.load(open('source.json'));sourcehash=hashlib.sha256(Path(cfg['source_pdf']).read_bytes()).hexdigest();assert sourcehash==json.load(open(audit/'native_coverage.json'))['source_sha256']
validation={'source_sha256':sourcehash,'final_report_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'physical_page_markers':len(markers),'page_sequence_valid':True,'image_references':len(refs),'missing_assets':missing,'broken_internal_targets':broken,'unresolved_unicode':weird,'baseline_coverage_report_applies_to':'report.native-original.md; final repairs documented in changes.json','full_source_review_completed':False,'render_completed':False}
(audit/'final_validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(validation,ensure_ascii=False,indent=2))
