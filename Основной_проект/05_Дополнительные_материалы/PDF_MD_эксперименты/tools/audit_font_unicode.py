"""Read-only source font audit. Writes only its own audit JSON/MD, never repairs MD."""
from __future__ import annotations
from collections import Counter,defaultdict
from pathlib import Path
import hashlib,io,json,re,sys,unicodedata
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf as fitz
from fontTools.ttLib import TTFont
from fontTools.cffLib import CFFFontSet
from fontTools.agl import toUnicode

BASE=Path(__file__).resolve().parent.parent
REPORTS=['ROSN-2025-ИО','TRNF-2024-ИО','MTLR-2023-ОУР','PLZL-2023-ОУР']
FROZEN='e84e269a6ef3840e4ba2b48efa9cb7fb5c56c4046b7fc4e476eb5d47edb351e4'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def unusual(c):return c=='\ufffd' or unicodedata.category(c) in ('Co','Cs') or (unicodedata.category(c)=='Cc' and not c.isspace())
def cp(c):return f'U+{ord(c):04X}'
def canon(s):return re.sub(r'^[A-Z]{6}\+','',s)

def font_data(doc,xref,gids):
    name,ext,kind,data=doc.extract_font(xref)
    item={'xref':xref,'name':name,'extension':ext,'font_file_sha256':hashlib.sha256(data).hexdigest() if data else None,'glyphs':{},'embedded':bool(data)}
    if not data:return item
    try:
        cmap=defaultdict(set)
        if ext in ('ttf','otf'):
            f=TTFont(io.BytesIO(data));order=f.getGlyphOrder()
            if 'cmap' in f:
                for table in f['cmap'].tables:
                    for code,glyph in table.cmap.items():cmap[glyph].add(code)
            item['cmap_present']='cmap' in f
        elif ext=='cff':
            f=CFFFontSet();f.decompile(io.BytesIO(data),None);order=f[f.fontNames[0]].charset
            item['cmap_present']=False
        else:return item
        for gid in gids:
            if not 0<=gid<len(order):continue
            name=order[gid]
            try:agl=toUnicode(name)
            except Exception:agl=''
            item['glyphs'][str(gid)]={'name':name,'cmap_codepoints':[f'U+{x:04X}' for x in sorted(cmap[name])],'agl_text':agl,'agl_codepoints':[cp(c) for c in agl]}
    except Exception as e:item['font_parse_error']=f'{type(e).__name__}: {e}'
    return item

def classify(font,raw,trace,gid):
    # All non-font-map equivalences below require visual confirmation, described separately.
    if raw=='U+FFFD' and trace=='U+0020':return 'recoverable_layout_space',' ', 'safe_only_exact_origin_font_gid_after_source_confirmation'
    if raw in ('U+0003','U+0007','U+0008') and trace=='U+0020':return 'recoverable_layout_space',' ', 'safe_only_exact_origin_font_gid_after_source_confirmation'
    if raw=='U+0008' and trace=='U+002E':return 'recoverable_layout_dot','.', 'safe_only_exact_origin_font_gid_after_source_confirmation'
    if raw=='U+FFFD' and trace=='U+002E':return 'recoverable_layout_dot','.', 'safe_only_exact_origin_font_gid_after_source_confirmation'
    if raw=='U+0008' and trace=='U+0020':return 'recoverable_layout_space',' ', 'safe_only_exact_origin_font_gid_after_source_confirmation'
    if font=='Wingdings-Regular' and raw=='U+F0FC' and trace=='U+2713':return 'checklist_checkmark','✓','safe_font_scoped_trace_confirmed'
    if font=='SymbolMT' and raw=='U+F0D7' and gid==152:return 'meaningful_unit_operator','·','visual_equivalent_font_gid_and_unit_context_only'
    if font=='Inter-Regular' and raw in ('U+E135','U+E136'):return 'navigation_icon',None,'keep_original_or_annotate_direction_with_source_link_not_exact_unicode_recovery'
    if font=='SFPro-Regular' and raw=='U+1006F7' and gid==10097:return 'square_list_marker','■','visual_equivalent_not_original_unicode_proof'
    return 'unresolved_requires_review',None,'do_not_replace'

def audit_report(rid):
    source=BASE/'_источники'/f'{rid}.pdf';draft=BASE/'_проверка/native_candidates'/rid
    receipt=json.loads((draft/'_проверка/source_input.json').read_text())
    md=(draft/'report.md').read_text();md_bad=Counter(cp(c) for c in md if unusual(c))
    registry=json.loads((draft/'_проверка/pages.json').read_text())['pages']
    registry_total=sum(p.get('unresolved_unicode',0) for p in registry)
    warning_pages={p['pdf_page'] for p in registry if p.get('unresolved_unicode',0)}
    groups={};pagecounts=Counter();contexts=[]
    with fitz.open(source) as doc:
        for pno,page in enumerate(doc,1):
            if pno not in warning_pages: continue
            raw=page.get_text('rawdict');bad=[]
            for bi,b in enumerate(raw['blocks']):
                for li,line in enumerate(b.get('lines',[])):
                    context=''.join(c['c'] for s in line['spans'] for c in s['chars'])
                    for sp in line['spans']:
                        for char in sp['chars']:
                            if unusual(char['c']):bad.append((sp['font'],char,context))
            if not bad:continue
            trace=defaultdict(list)
            for t in page.get_texttrace():
                for c in t['chars']:
                    trace[(t['font'],round(c[2][0],3),round(c[2][1],3))].append((c[0],c[1]))
            resources=page.get_fonts();fontcache={}
            for font,char,context in bad:
                origin=char['origin'];tc=sorted(set(trace.get((font,round(origin[0],3),round(origin[1],3)),[])))
                tu=tc[0][0] if len(tc)==1 else None;gid=tc[0][1] if len(tc)==1 else None
                tracecp=f'U+{tu:04X}' if tu is not None and tu>=0 else None
                key=(font,cp(char['c']),tracecp,gid)
                if key not in groups:
                    kind,replacement,safety=classify(font,key[1],tracecp,gid)
                    groups[key]={'font':font,'raw_codepoint':key[1],'raw_category':unicodedata.category(char['c']),'trace_codepoint':tracecp,'trace_glyph_id':gid,'classification':kind,'suggested_visible_equivalent':replacement,'safety':safety,'count':0,'pages':set(),'samples':[],'font_evidence':{},'occurrences':[]}
                g=groups[key];g['count']+=1;g['pages'].add(pno);pagecounts[pno]+=1
                occurrence={'pdf_page':pno,'origin':list(origin),'bbox':list(char['bbox']),'trace_candidates':[{'codepoint':f'U+{u:04X}' if u>=0 else str(u),'glyph_id':i} for u,i in tc]}
                g['occurrences'].append(occurrence)
                if len(g['samples'])<5:g['samples'].append({**occurrence,'line_context':context})
                if gid is not None:
                    for fr in resources:
                        if canon(fr[3])!=font:continue
                        cachekey=(fr[0],gid)
                        if cachekey not in fontcache:fontcache[cachekey]=font_data(doc,fr[0],[gid])
                        g['font_evidence'][str(fr[0])]=fontcache[cachekey]
        sourcepages=len(doc)
    for g in groups.values():g['pages']=sorted(g['pages']);g['font_evidence']=list(g['font_evidence'].values())
    result={'report_id':rid,'source_pdf':str(source.relative_to(BASE)),'source_sha256':sha(source),'source_hash_matches_frozen_receipt':sha(source)==receipt['source_sha256'],'frozen_implementation_sha256':receipt.get('implementation_sha256'),'source_pdf_pages':sourcepages,'registry_page_count':len(registry),'registry_warning_glyphs':registry_total,'source_unusual_glyphs_in_current_runtime':sum(pagecounts.values()),'draft_unusual_counts':dict(md_bad),'draft_md_sha256':sha(draft/'report.md'),'source_unusual_pages':dict(pagecounts),'groups':list(groups.values())}
    print(rid,'source',sum(pagecounts.values()),'draft',sum(md_bad.values()),'registry',registry_total,flush=True)
    return result

def write_audit(reports):
    byclass=Counter()
    for r in reports:
        for g in r['groups']:byclass[g['classification']]+=g['count']
    out={'scope':'Four named source PDFs, all native unusual characters; not whole semantic report review; no mutations to draft/helper/source','runtime':{'python':sys.executable,'python_version':sys.version,'pymupdf_module':fitz.__file__,'pymupdf_version_bind':fitz.VersionBind,'pymupdf_version':str(getattr(fitz,'version',None))},'frozen_batch_implementation_sha256':FROZEN,'classification_counts_current_native':dict(byclass),'reports':reports,'cautions':['Rawdict/trace mappings can differ; replace only source/font/gid/origin-scoped occurrences, preserving the raw character and provenance.','A cmap can intentionally map to PUA; that does not identify a normal Unicode equivalent.','Counts in rendered draft include repeated source-link captions and are not comparable one-to-one with source glyph inventory.','Cc controls such as U+0008 are included in the batch warning, not only FFFD and private-use codepoints.','Sample icon equivalences were visually confirmed on source crops; this is not a claim of every report sentence or numeric cell verified.']}
    (BASE/'_проверка/font_unicode_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    return out

if __name__=='__main__':
    import argparse
    from concurrent.futures import ProcessPoolExecutor, as_completed
    parser=argparse.ArgumentParser();parser.add_argument('--all',action='store_true');args=parser.parse_args()
    reports=REPORTS
    if args.all:
        reports=sorted(p.name for p in (BASE/'_проверка/native_candidates').iterdir() if p.is_dir() and (p/'report.md').is_file() and (p/'_проверка/source_input.json').is_file() and (BASE/'_источники'/(p.name+'.pdf')).is_file())
    results=[];failures=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(audit_report,r):r for r in reports}
        for future in as_completed(jobs):
            try:results.append(future.result())
            except Exception as exc:failures.append({'report_id':jobs[future],'error':f'{type(exc).__name__}: {exc}'})
    result=write_audit(sorted(results,key=lambda r:r['report_id']))
    result['requested_reports']=len(reports);result['audit_failures']=failures
    result['source_read_scope']='Only pages with unresolved_unicode>0 in frozen native pages registry; all warning occurrences on those pages. Not all PDF semantics.'
    (BASE/'_проверка/font_unicode_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

