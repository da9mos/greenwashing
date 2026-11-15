"""Check review quotations against original Drive files, without changing parsed data.

python src/check_pdf_sample.py --review-list ... --output ... --download
Downloads only reports named in the review list, never the full corpus.
"""
import argparse
import csv
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path
import fitz
from build_extract import norm,write_csv
from download import drive_download,site_download,is_pdf
from parse import normalize
from parse_txt import split_pages

ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--review-list',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
 ap.add_argument('--download',action='store_true');a=ap.parse_args()
 if a.output.exists():raise FileExistsError(a.output)
 rows=list(csv.DictReader(a.review_list.open(encoding='utf-8-sig'),delimiter=';'))
 reports={r['report_id']:r for r in csv.DictReader((ROOT.parent/'01_итерация_1_сбор_данных/выборка_30/reports.csv').open(encoding='utf-8-sig'),delimiter=';')}
 result=[]
 for rid in sorted({r['report_id'] for r in rows}):
  meta=reports[rid];pdf=ROOT/'data/reports'/f'{rid}.pdf';doc=None;err='';source_hash='';textdoc=None
  try:
   source_txt=ROOT/'data/reports'/f'{rid}.txt'
   if source_txt.exists() and not pdf.exists():
    b=source_txt.read_bytes();textdoc=b.decode('utf-8-sig');source_hash=hashlib.sha256(b).hexdigest()
   if not pdf.exists() and textdoc is None and a.download:
    if meta['status'].strip()=='pdf':
     b,_,_=drive_download(meta['drive_id'],'pdf')
    elif meta['status'].startswith('архив'):
     zdata,_,_=drive_download(meta['drive_id'],'zip')
     with zipfile.ZipFile(io.BytesIO(zdata)) as z:
      members=sorted([m for m in z.infolist() if m.filename.lower().endswith('.pdf')],key=lambda m:m.file_size,reverse=True)
      if not members:raise ValueError('No PDF in archive')
      b=z.read(members[0])
    else:
     b,_,_=site_download(meta['drive_id'],meta['year'])
    if not is_pdf(b):raise ValueError('Not a PDF')
    with pdf.open('xb') as f:f.write(b)
   if pdf.exists():
    source_hash=hashlib.sha256(pdf.read_bytes()).hexdigest();doc=fitz.open(pdf)
   elif textdoc is None:raise FileNotFoundError(pdf)
  except Exception as e:err=f'{type(e).__name__}: {str(e)[:200]}'
  for r in [r for r in rows if r['report_id']==rid]:
   status='';page_text=''
   try:
    if err:raise ValueError(err)
    if doc is not None:
     page_text=normalize(doc[int(r['page'])-1].get_text('text'))
     status='PDF: точное совпадение после нормализации' if norm(r['text']) in norm(page_text) else 'НЕ СОВПАЛО'
    else:
     clean=re.sub(r'(?<=[а-яё])\x02(?=[а-яё])','',textdoc).replace('\x02','-')
     printed_pages={page:normalize(text) for page,text in split_pages(clean)}
     status='TXT: точное совпадение на восстановленной печатной странице, исходного PDF нет' if norm(r['text']) in norm(printed_pages.get(int(r['page']),'')) else 'НЕ СОВПАЛО'
   except Exception as e:status=f'НЕ ПРОВЕРЕНО: {e}'
   result.append(dict(claim_id=r['claim_id'],review_group=r['review_group'],report_id=rid,page=r['page'],
    quote=r['text'],status=status,source_sha256=source_hash,check_method='PyMuPDF text extraction + parse.normalize + whitespace' if doc is not None else 'parse_txt control-character cleanup + split_pages + normalize + whitespace',visual_checked=''))
  print(rid, 'done' if not err else err,flush=True)
  if doc is not None:doc.close()
 write_csv(a.output,result,['claim_id','review_group','report_id','page','quote','status','source_sha256','check_method','visual_checked'])
 print(json.dumps({'checked':len(result),'unmatched':sum(r['status']=='НЕ СОВПАЛО' for r in result),'unavailable':sum(r['status'].startswith('НЕ ПРОВЕРЕНО') for r in result)},ensure_ascii=False))
if __name__=='__main__':main()
