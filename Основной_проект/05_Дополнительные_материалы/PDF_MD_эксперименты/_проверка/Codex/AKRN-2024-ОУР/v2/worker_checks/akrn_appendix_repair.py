from pathlib import Path
import fitz,json,re,html
D=fitz.open(json.load(open('source.json'))['source_pdf']);p=Path('result/report.md');s=p.read_text();sp=re.split(r'<!-- pdf_page: (\d+) -->',s);P={int(sp[i]):sp[i+1] for i in range(1,len(sp),2)}
logs=[]
def cell(n,x0,y0,x1,y1):
 lines=[]
 for b in D[n-1].get_text('rawdict')['blocks']:
  for l in b.get('lines',[]):
   chars=[]
   for ss in l['spans']:
    for c in ss['chars']:
     a,b,cx,d=c['bbox'];x=(a+cx)/2;y=(b+d)/2
     if x0<=x<x1 and y0<=y<y1:chars.append(c['c'])
   if chars:lines.append((l['bbox'][1],l['bbox'][0],''.join(chars).strip()))
 return '<br/>'.join(html.escape(t) for y,x,t in sorted(lines) if t)
def manual(n,xs,bands,headers):
 out='<table>\n<tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr>\n'
 for y0,y1 in bands:out+='<tr>'+''.join('<td>'+cell(n,xs[j],y0,xs[j+1],y1)+'</td>' for j in range(len(xs)-1))+'</tr>\n'
 return out+'</table>'
def ruled(n,xs,ymin,ymax,desc_start):
 # Use source horizontal rules to recover row boundaries; a missing rule in the
 # last column is retained as a source rowspan, not replaced by a guessed value.
 lines=[]
 for dr in D[n-1].get_drawings():
  r=dr['rect']
  if r.height<.15 and r.width>1 and ymin-.2<=r.y0<=ymax+.2:lines.append(r)
 ys=sorted(set([round(ymin,1),round(ymax,1)]+[round(r.y0,1) for r in lines if abs(r.x0-desc_start)<2]))
 out='<table>\n';occupied={};count=0
 for i,(lo,hi) in enumerate(zip(ys,ys[1:])):
  out+='<tr>'
  for col in range(len(xs)-1):
   if occupied.get(col,0)>i:continue
   end=i+1
   if col==len(xs)-2 and len(xs)==3:
    # Only right-column rules determine the end of merged comment cells.
    while end<len(ys)-1 and not any(abs(r.y0-ys[end])<.3 and r.x0<=xs[col]+2 and r.x1>=xs[col+1]-2 for r in lines):end+=1
   val=cell(n,xs[col],lo,xs[col+1],ys[end]);out+=f'<td rowspan="{end-i}">'+val+'</td>';occupied[col]=end
  out+='</tr>\n';count+=1
 out+='</table>';logs.append({'page':n,'bounds':[xs,ymin,ymax],'rows':count});return out
for n,configs in {61:[([638,991.3,1148.2],191.4,737.1,687.9)],62:[([42,396,553],97,800.9,92.6),([638,991.3,1148.2],97,800.9,687.9)],63:[([42,396,553],97,494.9,92.6),([638,950.2,1103.3,1148.2],199.1,801,712.1)],64:[([42,396,553],191.4,800.2,92.6),([638,991.3,1148.2],191.4,800.2,687.9)]}.items():
 replacements=[ruled(n,*c) for c in configs];it=iter(replacements);P[n]=re.sub(r'<table>.*?</table>',lambda m:next(it),P[n],flags=re.S)
p.write_text(sp[0]+''.join(f'<!-- pdf_page: {n} -->'+P[n] for n in range(1,66)))
