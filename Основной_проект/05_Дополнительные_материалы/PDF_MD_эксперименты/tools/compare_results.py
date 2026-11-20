"""Read-only structural/content comparison of independent PDF-to-MD runs.

python3 tools/compare_results.py
Only _проверка/comparison* outputs are written. No API, conversion or checked flag.
Text/number differences against the PDF text layer are diagnostics, not accuracy.
"""
from __future__ import annotations
import argparse
import base64
from collections import Counter
import csv
from datetime import datetime, timezone
from difflib import SequenceMatcher
import hashlib
from html import unescape
from html.parser import HTMLParser
import io
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

for local_lib in ('/private/tmp/sber-pdf-libs', '/private/tmp/sber-diff-libs'):
    if Path(local_lib).is_dir():sys.path.insert(0,local_lib)
import pymupdf as fitz
from PIL import Image

BASE=Path(__file__).resolve().parents[1]
REGISTRY=BASE.parents[2]/'11_Проект_Сбер/3_итерация/greenwashing/01_итерация_1_сбор_данных/выборка_30/reports.csv'
MARKER=re.compile(r'<!--\s*pdf_page:\s*(\d+)\s*-->',re.I)
INLINE=re.compile(r'(!?)\[([^\]\n]*)\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+["\'][^\n]*?["\'])?\s*\)')
DECIMAL=re.compile(r'(?<![\w.,])[+−–-]?\d+(?:[ \u00a0\u202f]\d{3})*[.,]\d+(?!\d)',re.UNICODE)
NUMBER=re.compile(r'(?<!\w)[+−–-]?\d+(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?\s*%?(?!\w)',re.UNICODE)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def read_rows(path):
    with Path(path).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f,delimiter=';'))

class HTMLContent(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.parts=[];self.anchors=[];self.links=[];self.images=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('script','style'):self.skip+=1
        if a.get('id'):self.anchors.append(a['id'])
        if tag=='a' and a.get('name'):self.anchors.append(a['name'])
        if tag=='a' and 'href' in a:self.links.append(a['href'])
        if tag=='img' and 'src' in a:self.images.append(a['src'])
        if tag in ('p','div','tr','td','th','br','li','h1','h2','h3'):self.parts.append(' ')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
        self.parts.append(' ')
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)

def cleaned_text(md):
    # Remove only explicitly labelled service/source wrappers, never arbitrary details.
    md=re.sub(r'<details>\s*<summary>Источник:\s*PDF-страница.*?</details>',' ',md,flags=re.S|re.I)
    md=re.sub(r'^\s*>\s*Служебн[^\n]*',' ',md,flags=re.M|re.I)
    md=re.sub(r'<!--.*?-->',' ',md,flags=re.S)
    # Link destinations are metadata; author footnote bodies are source content.
    md=re.sub(r'^\s*\[(?!\^)[^\]]+\]:\s+\S+.*$',' ',md,flags=re.M)
    md=re.sub(r'\[\^[^\]]+\](?::)?',' ',md)
    md=INLINE.sub(lambda m:' ' if m[1] else m[2],md)
    parser=HTMLContent();parser.feed(md);parser.close()
    text=unescape(''.join(parser.parts))
    text=re.sub(r'^[ \t]*[-|: ]+\|[-|: ]*$',' ',text,flags=re.M)
    text=re.sub(r'[`*_#|>~]',' ',text)
    return re.sub(r'\s+',' ',text.replace('\u00ad','')).strip().casefold()

def numeric_tokens(text):
    return Counter(re.sub(r'\s+','',m.group()).replace(',','.').replace('−','-').replace('–','-') for m in NUMBER.finditer(text))


def numeric_text(markdown):
    """Cell/line boundaries cannot be interpreted as thousands separators."""
    text=re.sub(r'<details>\s*<summary>Источник:\s*PDF-страница.*?</details>',' ',markdown,flags=re.S|re.I)
    text=re.sub(r'^\s*>\s*Служебн[^\n]*',' ',text,flags=re.M|re.I)
    text=re.sub(r'</?(?:td|th|tr)\b[^>]*>',' ∥ ',text,flags=re.I)
    text=re.sub(r'(?<!\\)\|',' ∥ ',text)
    text=text.replace('\n',' ∥ \n')
    return cleaned_text(text)

def decimal_key(value):
    return re.sub(r'\s+','',value).replace(',','.').replace('−','-').replace('–','-')


def decimal_span_reference(page_dict):
    """Never concatenate spans: a neighboring footnote is not a decimal digit.

    Raw font/size/flags/bbox are retained. Superscript inference is diagnostic;
    only decimal tokens entirely inside a normal span enter this reference.
    """
    counts=Counter();evidence=[];excluded=[]
    for bi,block in enumerate(page_dict.get('blocks',[])):
        for li,line in enumerate(block.get('lines',[])):
            spans=line.get('spans',[])
            regular=[sp for sp in spans if not int(sp.get('flags',0)) & 1]
            max_size=max((float(sp.get('size',0)) for sp in regular),default=0)
            baseline=max((float(sp.get('origin',[0,sp.get('bbox',[0,0,0,0])[3]])[1])
                          for sp in regular if float(sp.get('size',0))==max_size),default=0)
            neighbors=[{k:sp.get(k) for k in ('text','font','size','flags','bbox','origin')} for sp in spans]
            for si,sp in enumerate(spans):
                text=sp.get('text','');size=float(sp.get('size',0));flags=int(sp.get('flags',0))
                origin_y=float(sp.get('origin',[0,sp.get('bbox',[0,0,0,0])[3]])[1])
                flag_super=bool(flags & 1)
                geometry_super=bool(max_size and size<max_size*.8 and baseline-origin_y>max_size*.15)
                for match in DECIMAL.finditer(text):
                    record={'token':decimal_key(match.group()),'raw_decimal':match.group(),
                            'block_index':bi,'line_index':li,'span_index':si,
                            'span_text':text,'font':sp.get('font'),'font_size':size,
                            'flags':flags,'bbox':sp.get('bbox'),'origin':sp.get('origin'),
                            'superscript_flag':flag_super,'smaller_raised':geometry_super,
                            'line_spans':neighbors}
                    if flag_super or geometry_super:excluded.append(record)
                    else:counts[record['token']]+=1;evidence.append(record)
    return {'counts':counts,'evidence':evidence,'excluded_superscript_decimal_spans':excluded}


def compare_decimals_to_spans(markdown,reference):
    # Explicit HTML footnotes are separate; Unicode superscript digits remain
    # outside DECIMAL's decimal-digit run and are never appended to its value.
    text=numeric_text(re.sub(r'<sup\b[^>]*>.*?</sup>',' ∥ ',markdown,flags=re.S|re.I))
    matches=list(DECIMAL.finditer(text));actual=Counter(decimal_key(m.group()) for m in matches)
    expected=Counter(reference['counts']);missing=expected-actual;extra=actual-expected
    return {'method':'normal_PDF_spans_individually; no_cross_span_number_join',
            'pdf_decimal_tokens':sum(expected.values()),'markdown_decimal_tokens':sum(actual.values()),
            'pdf_only':dict(missing),'markdown_only':dict(extra),
            'pdf_span_evidence':[e for e in reference['evidence'] if e['token'] in missing],
            'markdown_evidence':[{'token':decimal_key(m.group()),'text_context':text[max(0,m.start()-70):m.end()+70]}
                                 for m in matches if decimal_key(m.group()) in extra],
            'excluded_superscript_decimal_spans':reference['excluded_superscript_decimal_spans']}


def compare_text(left,right):
    a,b=cleaned_text(left),cleaned_text(right)
    ta,tb=re.findall(r'\w+|[^\w\s]',a),re.findall(r'\w+|[^\w\s]',b)
    ca,cb=numeric_tokens(numeric_text(left)),numeric_tokens(numeric_text(right))
    return {'left_chars':len(a),'right_chars':len(b),'text_equal':a==b,
            'token_sequence_diff_fraction':round(1-SequenceMatcher(None,ta,tb,autojunk=False).ratio(),6),
            'numeric_left_count':sum(ca.values()),'numeric_right_count':sum(cb.values()),
            'numeric_left_only':dict(ca-cb),'numeric_right_only':dict(cb-ca)}

def split_pages(md,count):
    matches=list(MARKER.finditer(md));nums=[int(m[1]) for m in matches]
    issues=[];expected=list(range(1,count+1))
    if nums!=expected:
        issues.append({'code':'page_markers','missing':sorted(set(expected)-set(nums)),
                       'duplicates':sorted(n for n,c in Counter(nums).items() if c>1),
                       'out_of_range':sorted(set(nums)-set(expected)),'out_of_order':nums!=sorted(nums)})
    if 'pdf_page' in MARKER.sub('',md):issues.append({'code':'malformed_page_marker'})
    pages={}
    for i,m in enumerate(matches):
        n=int(m[1]);body=md[m.end():matches[i+1].start() if i+1<len(matches) else len(md)]
        if n not in pages:pages[n]=body
        if not body.strip():issues.append({'code':'empty_page_body','page':n})
    return pages,issues,nums

def refs(md):
    parser=HTMLContent();parser.feed(md);parser.close()
    anchors=parser.anchors[:];links=parser.links[:];images=parser.images[:]
    for m in INLINE.finditer(md):(images if m[1] else links).append(m[3].strip('<>'))
    definitions={m[1].casefold():m[2].strip('<>') for m in re.finditer(r'^\s*\[([^\]]+)\]:\s*(<[^>]+>|\S+)',md,re.M)}
    for m in re.finditer(r'(!?)\[([^\]]+)\]\[([^\]]*)\]',md):
        key=(m[3] or m[2]).casefold();dest=definitions.get(key)
        if dest:(images if m[1] else links).append(dest)
        else:links.append('missing-reference-definition:'+key)
    slugs=Counter()
    for m in re.finditer(r'^\s{0,3}#{1,6}\s+(.+?)\s*#*$',md,re.M):
        slug=re.sub(r'[^\w\s-]','',cleaned_text(m[1]));slug=re.sub(r'\s','-',slug)
        k=slugs[slug];slugs[slug]+=1;anchors.append(slug+('-'+str(k) if k else ''))
    return anchors,links,images

def decode_image(path):
    try:
        raw=Path(path).read_bytes()
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image.load();size=list(image.size)
        return {'ok':True,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'size':size}
    except Exception as e:return {'ok':False,'error':type(e).__name__+': '+str(e)[:180]}

def safe_local(base,url):
    parsed=urlsplit(unquote(url))
    if parsed.scheme or parsed.netloc:return None,parsed
    path=(base/parsed.path).resolve()
    if not path.is_relative_to(base.resolve()):raise ValueError('Local link escapes package')
    return path,parsed

def inspect_markdown(path,count):
    if not path.exists():return {'state':'pending','reason':'report.md absent','issues':[],'pages':{},'report_sha256':'','image_count':0}
    before=path.stat();raw=path.read_bytes();md=raw.decode('utf-8-sig');pages,issues,markers=split_pages(md,count)
    anchors,links,images=refs(md);aset=set(anchors);external=[]
    for a,c in Counter(anchors).items():
        if c>1:issues.append({'code':'duplicate_anchor','anchor':a})
    for link in links:
        try:
            if link.startswith('missing-reference-definition:'):raise ValueError(link)
            target,parsed=safe_local(path.parent,link)
            if target is None:external.append(link);continue
            if not parsed.path:
                if not parsed.fragment or unquote(parsed.fragment) not in aset:issues.append({'code':'broken_anchor','target':link})
            elif not target.exists():issues.append({'code':'missing_local_link','target':link})
            elif parsed.fragment and target.suffix.lower() in ('.md','.html','.htm'):
                ids,_,_=refs(target.read_text(encoding='utf-8-sig'))
                if parsed.fragment not in ids:issues.append({'code':'broken_crossfile_anchor','target':link})
        except Exception as e:issues.append({'code':'invalid_link','target':link,'error':str(e)[:150]})
    decoded=[]
    for link in sorted(set(images)):
        try:
            target,parsed=safe_local(path.parent,link)
            if target is None:
                issues.append({'code':'remote_image_not_verified','target':link[:150]});continue
            r=decode_image(target);decoded.append(dict(target=link,**r))
            if not r['ok']:issues.append({'code':'undecodable_image','target':link,'error':r['error']})
        except Exception as e:issues.append({'code':'invalid_image_link','target':link,'error':str(e)[:150]})
    after=path.stat();changed=(before.st_mtime_ns,before.st_size)!=(after.st_mtime_ns,after.st_size)
    if changed:issues.append({'code':'report_changed_during_read'})
    return {'state':'pending' if changed else ('structural_issues' if issues else 'structurally_valid_unreviewed'),
            'issues':issues,'pages':pages,'markers':markers,'report_sha256':hashlib.sha256(raw).hexdigest(),
            'image_count':len(set(images)),'images':decoded,'external_links_not_fetched':len(external)}

def inspect_packets(base,rid,count,source_hash):
    folder=base/'_проверка/входы'/rid;index=folder/'pages.json'
    if not index.exists():return {'state':'pending','reason':'pages.json absent','issues':[],'pages_seen':0}
    d=json.loads(index.read_text());issues=[]
    if d.get('report_id')!=rid:issues.append({'code':'packet_report_id_mismatch'})
    if d.get('source_sha256')!=source_hash:issues.append({'code':'packet_source_hash_mismatch'})
    items=d.get('pages',[]);nums=[i.get('pdf_page') for i in items]
    if nums!=list(range(1,count+1)):issues.append({'code':'packet_page_sequence_mismatch'})
    for item in items:
        n=item.get('pdf_page')
        for field in ('packet','image'):
            rel=item.get(field,'');p=(base/rel).resolve()
            if not rel or not p.is_relative_to(base.resolve()) or not p.is_file():
                issues.append({'code':'missing_packet_'+field,'page':n});continue
            if field=='packet':
                packet=json.loads(p.read_text())
                if packet.get('pdf_page')!=n:issues.append({'code':'packet_wrong_page','page':n})
                if packet.get('image')!=item.get('image') or packet.get('image_sha256')!=item.get('image_sha256'):
                    issues.append({'code':'packet_image_metadata_mismatch','page':n})
                blocks=packet.get('text_blocks')
                if not isinstance(blocks,list):issues.append({'code':'packet_invalid_text_blocks','page':n})
                else:
                    for block in blocks:
                        bbox=block.get('bbox') if isinstance(block,dict) else None
                        if (not isinstance(bbox,list) or len(bbox)!=4 or
                            any(type(x) not in (int,float) or not math.isfinite(x) for x in bbox) or
                            not isinstance(block.get('text'),str)):
                            issues.append({'code':'packet_invalid_text_block','page':n});break
            else:
                r=decode_image(p)
                if not r['ok']:issues.append({'code':'packet_undecodable_image','page':n})
                elif item.get('image_sha256')!=r['sha256']:issues.append({'code':'packet_image_hash_mismatch','page':n})
    return {'state':'structural_issues' if issues else 'packets_valid_unreviewed','issues':issues,'pages_seen':len(items),'index_sha256':sha(index)}

def audit_report(base,row,ledger):
    rid=row['report_id'];cid=row.get('company_id') or rid.split('-')[0]
    source=base/'_источники'/f'{rid}.pdf';errors=[];detail={'report_id':rid,'company_id':cid,'issues':errors}
    flat={'report_id':rid,'company_id':cid,'source_state':'pending','source_sha256':'','source_pages':'','source_sha_matches_ledger':'',
          'packets_state':'pending','DeepSeek_state':'pending','Codex_state':'pending','pair_pages_compared':0,'pages_text_different':0,'pages_numeric_different':0,'DeepSeek_decimal_diff_pages':0,'Codex_decimal_diff_pages':0,'state':'pending','issues_count':0}
    if not source.exists():detail['reason']='source PDF absent';return flat,detail,[]
    try:
        actual_hash=sha(source)
        with fitz.open(source) as doc:
            count=len(doc);flat.update(source_state='readable',source_sha256=actual_hash,source_pages=count)
            expected=ledger.get(rid,{}).get('sha256')
            if expected:
                flat['source_sha_matches_ledger']=expected==actual_hash
                if expected!=actual_hash:errors.append({'code':'source_hash_mismatch'})
            expected_pages=ledger.get(rid,{}).get('pages')
            if expected_pages and int(expected_pages)!=count:errors.append({'code':'source_page_count_mismatch'})
            packets=inspect_packets(base,rid,count,actual_hash);detail['packets']=packets;flat['packets_state']=packets['state']
            models={}
            for engine in ('DeepSeek','Codex'):
                path=base/engine/cid/rid/'report.md'
                try:models[engine]=inspect_markdown(path,count)
                except Exception as e:models[engine]={'state':'structural_issues','issues':[{'code':'report_read_error','error':str(e)[:200]}],'pages':{},'report_sha256':''}
                flat[engine+'_state']=models[engine]['state']
            page_rows=[]
            for n in range(1,count+1):
                available={e:m['pages'][n] for e,m in models.items() if n in m['pages']}
                if not available:continue
                reference=doc[n-1].get_text(sort=False)
                rec={'report_id':rid,'pdf_page':n,'pdf_text_chars':len(reference),'pdf_text_layer_empty':not reference.strip()}
                span_reference=decimal_span_reference(doc[n-1].get_text('dict'))
                for engine,body in available.items():
                    rec[engine+'_vs_PDF']=compare_text(body,reference)
                    decimal=compare_decimals_to_spans(body,span_reference)
                    rec[engine+'_decimal_vs_PDF_spans']=decimal
                    if decimal['pdf_only'] or decimal['markdown_only']:flat[engine+'_decimal_diff_pages']+=1
                if len(available)==2:
                    pair=compare_text(available['DeepSeek'],available['Codex']);rec['DeepSeek_vs_Codex']=pair
                    flat['pair_pages_compared']+=1
                    flat['pages_text_different']+=not pair['text_equal']
                    flat['pages_numeric_different']+=bool(pair['numeric_left_only'] or pair['numeric_right_only'])
                page_rows.append(rec)
            for e,m in models.items():
                detail[e]={k:v for k,v in m.items() if k!='pages'}
            flat['issues_count']=len(errors)+len(packets['issues'])+sum(len(m['issues']) for m in models.values())
            pending=packets['state']=='pending' or any(m['state']=='pending' for m in models.values())
            flat['state']='structural_issues' if flat['issues_count'] else ('pending' if pending else 'compared_unreviewed')
            detail['state']=flat['state'];detail['source_sha256']=actual_hash;detail['source_pages']=count
            return flat,detail,page_rows
    except Exception as e:
        errors.append({'code':'source_or_packet_read_error','error':type(e).__name__+': '+str(e)[:250]})
        flat.update(state='structural_issues',issues_count=len(errors));return flat,detail,[]

def write_atomic(path,text):
    temp=path.with_suffix(path.suffix+'.part');temp.write_text(text,encoding='utf-8');temp.replace(path)

def run(base=BASE,registry=REGISTRY):
    base=Path(base);rows=read_rows(registry)
    if len({r['report_id'] for r in rows})!=len(rows):raise ValueError('Duplicate report_id in registry')
    ledgerpath=base/'_проверка/sources.csv';ledger={r['report_id']:r for r in read_rows(ledgerpath)} if ledgerpath.exists() else {}
    flats=[];details=[];pages=[]
    for row in rows:
        f,d,p=audit_report(base,row,ledger);flats.append(f);details.append(d);pages.extend(p)
    out=base/'_проверка';out.mkdir(exist_ok=True)
    summary={'generated_at':datetime.now(timezone.utc).isoformat(),'registry':str(registry),'registry_sha256':sha(registry),
             'checker_sha256':sha(Path(__file__)), 'sources_ledger_sha256':sha(ledgerpath) if ledgerpath.exists() else None,
             'reports_expected':len(rows),'companies_expected':len({r.get('company_id') or r['report_id'].split('-')[0] for r in rows}),
             'report_states':dict(Counter(f['state'] for f in flats)),
             'engine_states':{e:dict(Counter(f[e+'_state'] for f in flats)) for e in ('DeepSeek','Codex')},
             'source_PDFs_readable':sum(f['source_state']=='readable' for f in flats),'source_pages_total':sum(int(f['source_pages'] or 0) for f in flats),
             'decimal_diff_pages':{e:sum(f[e+'_decimal_diff_pages'] for f in flats) for e in ('DeepSeek','Codex')},
             'pair_pages_compared':sum(f['pair_pages_compared'] for f in flats),'structural_issue_count':sum(f['issues_count'] for f in flats),
             'checked_authorized':False,'note':'Snapshot during live runs. Differences are not model accuracy; no visual/semantic acceptance is granted.'}
    buffer=io.StringIO();writer=csv.DictWriter(buffer,list(flats[0]) if flats else ['report_id'],delimiter=';');writer.writeheader();writer.writerows(flats)
    write_atomic(out/'comparison.csv','\ufeff'+buffer.getvalue())
    write_atomic(out/'comparison_summary.json',json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    write_atomic(out/'comparison_details.json',json.dumps(details,ensure_ascii=False,indent=2)+'\n')
    write_atomic(out/'comparison_pages.jsonl',''.join(json.dumps(p,ensure_ascii=False)+'\n' for p in pages))
    decimal_rows=[]
    for page in pages:
        for engine in ('DeepSeek','Codex'):
            d=page.get(engine+'_decimal_vs_PDF_spans')
            if d and (d['pdf_only'] or d['markdown_only']):
                decimal_rows.append({'report_id':page['report_id'],'pdf_page':page['pdf_page'],'engine':engine,
                    'pdf_only':json.dumps(d['pdf_only'],ensure_ascii=False),
                    'markdown_only':json.dumps(d['markdown_only'],ensure_ascii=False),
                    'span_evidence':'comparison_pages.jsonl: '+page['report_id']+' page '+str(page['pdf_page'])})
    b=io.StringIO();w=csv.DictWriter(b,['report_id','pdf_page','engine','pdf_only','markdown_only','span_evidence'],delimiter=';');w.writeheader();w.writerows(decimal_rows)
    write_atomic(out/'comparison_decimal_differences.csv','\ufeff'+b.getvalue())
    lines=['# Сравнение PDF → Markdown: текущий снимок','',f"Реестр: **{len(rows)} отчётов**, **{summary['companies_expected']} компаний**. PDF прочитано: {summary['source_PDFs_readable']}; физических страниц: {summary['source_pages_total']}.",'',
           '## Покрытие и ошибки','',f"Состояния документов: {summary['report_states']}",f"DeepSeek: {summary['engine_states']['DeepSeek']}",f"Codex: {summary['engine_states']['Codex']}",f"Структурных замечаний: **{summary['structural_issue_count']}**. Парных страниц для сравнения: **{summary['pair_pages_compared']}**.",'',
           'Отсутствующий report.md или пакет — pending. Существующий файл с нарушениями маркеров, ссылок либо изображений отражён как structural_issues. Это автоматическая диагностика, которая не присваивает checked. Прогон моделей может ещё выполняться.','',
           '## Десятичные числа по PDF-span','',f"Страниц с диагностическими расхождениями: {summary['decimal_diff_pages']}. См. comparison_decimal_differences.csv; координаты, шрифт, размер и flags каждого исходного span сохранены в comparison_pages.jsonl.",'Десятичные токены извлекаются из отдельных PDF-span, без склейки с соседним надстрочным номером сноски. Сравнение сплошного текста сохранено отдельно. Это не автоматический вердикт об ошибке модели: контекст таблиц и OCR требуют проверки.','','## Детали','', '| Отчёт | PDF стр. | Пакеты | DeepSeek | Codex | Замечаний |','|---|---:|---|---|---|---:|']
    lines.extend(f"| {f['report_id']} | {f['source_pages']} | {f['packets_state']} | {f['DeepSeek_state']} | {f['Codex_state']} | {f['issues_count']} |" for f in flats)
    lines+=['','## Как читать сравнение','',
            '`comparison.csv` — одна строка на каждый RID. `comparison_details.json` — конкретные нарушения; `comparison_pages.jsonl` — отдельные результаты каждого сравнения по физической странице. Все файлы обновляются только этим инструментом, модельные результаты не исправляются.',
            'Текст очищается от HTML-разметки, Markdown-оформления и явно служебных обёрток. Для каждой доступной страницы сопоставляется очищенная последовательность токенов и мультимножество числовых токенов: обе ветки друг с другом и каждая с исходным PDF-текстовым слоем. Ничего не подменяется старым результатом.',
            '**Доля различий не является точностью модели.** PDF-слой может иметь неверный порядок колонок, дефектное извлечение, числа колонтитулов или отсутствовать на скане. OCR, содержание изображений, верность таблиц и отображение требуют самостоятельной визуальной сверки. Декодирование PNG/JPEG не проверяет содержание картинки. Внешние URL не открываются. Автоматические заголовочные якоря проверяются по правилам, близким GitHub; особенности другого рендера нужно проверять отдельно.',
            'Повторить: `python3 tools/compare_results.py`. Снимок отражает только файлы, доступные во время чтения; результаты запущенных моделей появятся после очередного прогона проверки.','']
    write_atomic(out/'comparison.md','\n'.join(lines))
    print(json.dumps(summary,ensure_ascii=False,indent=2));return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,default=BASE);p.add_argument('--registry',type=Path,default=REGISTRY)
    a=p.parse_args();run(a.base,a.registry)
