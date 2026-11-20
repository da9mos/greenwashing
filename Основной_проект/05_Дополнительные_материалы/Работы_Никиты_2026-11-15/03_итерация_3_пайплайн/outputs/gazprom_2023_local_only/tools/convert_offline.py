"""Local PDF -> Markdown candidates, geometry and selective Tesseract OCR. No API."""
import argparse,csv,hashlib,json,re,socket,subprocess,time
from pathlib import Path
import pymupdf,pymupdf4llm

def deny_network(*a,**kw):raise RuntimeError('Network disabled during conversion')
socket.socket.connect=deny_network
socket.socket.connect_ex=deny_network
socket.create_connection=deny_network

def split_regions(page):
    w,h=page.rect.width,page.rect.height
    words=page.get_text('words')
    crossing=sum(1 for x in words if x[0]<w/2-3 and x[2]>w/2+3)
    if w/h>1.2 and crossing<=2:
        return [('left',pymupdf.Rect(0,0,w/2,h)),('right',pymupdf.Rect(w/2,0,w,h))]
    return [('page',page.rect)]

def convert(src,out):
    out.mkdir(parents=True,exist_ok=True)
    if(out/'manifest.json').exists():raise ValueError('Use a new output directory; previous results are immutable')
    for name in ['pages','images','tables']:(out/name).mkdir(exist_ok=True)
    doc=pymupdf.open(src);review=[];records=[];start=time.time()
    for i,page in enumerate(doc):
        n=i+1;raw=page.get_text();regions=split_regions(page);lay=[];legacy=[];problems=[];ocr=[];tables=[]
        spans=[]
        for b in page.get_text('dict')['blocks']:
            for l in b.get('lines',[]):
                for s in l['spans']:spans.append({k:s[k]for k in ['text','size','flags','origin','bbox']})
        image_rects=[r for img in page.get_images()for r in page.get_image_rects(img[0])]
        image_area=min(page.rect.get_area(),sum(r.get_area()for r in image_rects))
        scan=len(re.findall(r'[A-Za-zА-Яа-я]',raw))<400 and image_area>page.rect.get_area()*.4
        for label,rect in regions:
            z=pymupdf.open();z.insert_pdf(doc,from_page=i,to_page=i);z[0].set_cropbox(rect)
            try:
                pymupdf4llm.use_layout(True)
                lay.append(pymupdf4llm.to_markdown(z,show_progress=False,use_ocr=False))
            except Exception as e:lay.append('');problems.append('layout_error:'+type(e).__name__)
            try:
                pymupdf4llm.use_layout(False)
                legacy.append(pymupdf4llm.to_markdown(z,show_progress=False))
            except Exception as e:legacy.append('');problems.append('legacy_error:'+type(e).__name__)
            if scan:
                img=out/'images'/f'{n:03d}_{label}.png';z[0].get_pixmap(matrix=pymupdf.Matrix(2.5,2.5)).save(img)
                try:
                    r=subprocess.run(['tesseract',str(img),'stdout','-l','rus+eng','--psm','3'],capture_output=True,text=True,timeout=120)
                    if r.returncode:problems.append('ocr_error');ocr.append('')
                    else:ocr.append(r.stdout)
                except (OSError,subprocess.TimeoutExpired):problems.append('ocr_unavailable');ocr.append('')
            # Structured coordinates; detection is a candidate, not source-verified cells.
            try:
                pymupdf4llm.use_layout(False)
                for t in z[0].find_tables().tables:
                    tables.append({'region':label,'bbox_region':list(t.bbox),'region_origin':[rect.x0,rect.y0],'rows':t.extract(),'review_status':'pending'})
            except Exception:problems.append('table_detection_error')
            z.close()
        lm='\n\n'.join(lay);old='\n\n'.join(legacy);om='\n\n'.join(ocr)
        chosen=om if scan and om.strip()else lm or old
        if scan:problems.append('ocr_needs_source_review')
        if len(regions)>1:problems.append('spread_split_check_internal_columns')
        if '|'in lm:problems.append('table_structure_needs_review')
        if page.get_drawings() or image_rects:problems.append('graphics_or_charts_need_review')
        if not chosen.strip()and len(raw.strip())>80:problems.append('missing_text')
        (out/'pages'/f'{n:03d}_layout.md').write_text(lm)
        (out/'pages'/f'{n:03d}_reading_order.md').write_text(old)
        if scan:(out/'pages'/f'{n:03d}_ocr.txt').write_text(om)
        (out/'pages'/f'{n:03d}.md').write_text(chosen)
        (out/'tables'/f'{n:03d}.json').write_text(json.dumps(tables,ensure_ascii=False))
        rec={'pdf_page':n,'printed_pages':None,'raw_text':raw,'spans':spans,'regions':[{'label':label,'bbox':list(rect)}for label,rect in regions],'ocr_used':scan,'selected_candidate':'tesseract'if scan and om.strip()else'layout','markdown':chosen,'problems':problems,'review_status':'pending'}
        records.append(rec);review.append({'pdf_page':n,'raw_chars':len(raw),'md_chars':len(chosen),'split_regions':len(regions),'ocr_used':scan,'detected_tables':len(tables),'review_status':'pending','problems':';'.join(problems)})
        if n%10==0:print('local_only',n,'/',len(doc),flush=True)
    (out/'document.md').write_text('# Локальное извлечение PDF\n\nМашинная версия. Непроверенные места отмечены в page_review.csv.\n\n'+'\n\n'.join(f'<!-- pdf_page: {r["pdf_page"]}; review_status: pending -->\n## PDF-страница {r["pdf_page"]}\n\n'+r['markdown']for r in records))
    with(out/'pages.jsonl').open('w')as f:
        for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    with(out/'page_review.csv').open('w',encoding='utf-8-sig',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(review[0]),delimiter=';');w.writeheader();w.writerows(review)
    manifest={'source_name':src.name,'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'pdf_pages':len(doc),'engine':'pymupdf4llm','version':pymupdf4llm.__version__,'ocr':'local tesseract rus+eng','network':'Python network connections blocked; no API clients or cloud calls','seconds':round(time.time()-start,2),'ocr_pages':[r['pdf_page']for r in records if r['ocr_used']],'split_pages':[r['pdf_page']for r in records if len(r['regions'])>1],'state':'converted; semantic review pending'}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print('DONE',len(doc),'OCR',len(manifest['ocr_pages']),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('pdf',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args();convert(a.pdf,a.output)
