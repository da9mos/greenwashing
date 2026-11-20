"""Build the reviewed selection through the project's annual company exporter, without process banners."""
from pathlib import Path
import hashlib,importlib.util,json,subprocess,tempfile,shutil
HERE=Path(__file__).resolve().parent;PROJECT=HERE.parent
spec=importlib.util.spec_from_file_location('company_adapter',PROJECT/'04_Итоги_проверки/prepare_company_export.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
facts=HERE/'02_Проверка_фактов'
review=json.loads((HERE/'01_Сверка_цитат/citation_review.json').read_text())
annual=json.loads((HERE/'01_Сверка_цитат/annual_citation_review.json').read_text())
current=HERE/'04_Повторная_проверка/presentation.json'
if current.exists():
    facts=current.parent
    present=json.loads(current.read_text())['rows']
    more=[]
else:
    present=json.loads((facts/'presentation.json').read_text())['rows']
    more=json.loads((facts/'annual_presentation.json').read_text())['rows']
bindings={b['atomic_source_id']:b for b in review['atomic_bindings']}
annual_by_id={q['claim_id']:q for q in annual['quotes']}
parent_by_id={q['quote_id']:q for q in review['quotes']}
registry=e.read(PROJECT/'00_Отчёты/manifest.json');by_id={r['report_id']:r for r in registry}
records={};provenance=[]
for row in present+more:
    packet_path=facts/row.get('assessment_path',row['record_path'])
    packet=e.read(packet_path)
    identity=row.get('quote_id') or row.get('atom_id') or row.get('source_id') or row.get('claim_id')
    binding=bindings.get(identity)
    if binding:
        rid=binding['report_id'];q={'exact_quote':binding['exact_quote'],'verified':binding['verified'],'source_md_sha256':binding['source_md_sha256'],'pages':[binding['page']]}
    elif identity in parent_by_id:
        citation=parent_by_id[identity];rid=citation['report_id']
        q={'exact_quote':citation['exact_quote'],'verified':citation['verified'],'source_md_sha256':citation['source_md_sha256'],'pages':[citation['page']]}
    else:
        citation=annual_by_id.get(identity)
        if citation is None:
            citation=next(c for c in annual['quotes'] if c['report_id']==row['report_id'])
        rid=citation['report_id']
        q={'exact_quote':citation.get('assessed_exact_quote',citation['exact_quote']),
           'raw_md_quote':citation.get('assessed_raw_md_quote',citation.get('raw_md_quote',citation['exact_quote'])),
           'formatting_only_transform':citation.get('formatting_only_transform',[]),
           'source_md_sha256':citation['source_md_sha256'],'pages':[citation['page']],'verified':citation['verified']}
    report=by_id[rid]
    q.update(short_reason=row['short_reason'],sources=row['sources'])
    if packet['verdict'] in {'true','false','partial'}:
        # The assessed input itself must cover the entire displayed quotation, including every numeric claim.
        assert packet['quote']==q['exact_quote'], 'Categorical assessment covers a different display span'
        q['assessed_quote_complete']=True
    record={'id':packet['claim_id'],'source_id':identity,'quote':packet['quote'],
            'original':{'id':identity,'statement':packet['quote'],'type':row['type'],'block':row['block'],'pdf_page':q['pages'][0],'source_url':report['pdf_source_url']},
            'assessment':packet,'research_status':packet['research_status'],'presentation':q}
    e.verify_presentation(record,report)
    e.display(record,report,1,require_presentation=True)
    records.setdefault(rid,[]).append(record)
    provenance.append({'report_id':rid,'source_id':identity,'assessment_path':str(packet_path.relative_to(HERE)),
                       'assessment_sha256':hashlib.sha256(packet_path.read_bytes()).hexdigest(),'revision':packet['revision'],
                       'display_quote_sha256':hashlib.sha256(q['exact_quote'].encode()).hexdigest(),
                       'risk_categories':[c['category'] for c in packet['risk_checks']],
                       'legacy_atomic_source_ids':row.get('legacy_atomic_source_ids',[])})
staging=HERE/'company_exports';staging.mkdir(exist_ok=True)
for rid,rows in records.items():
    target=staging/rid;target.mkdir(exist_ok=True)
    (target/'claims.json').write_text(json.dumps({'claims':rows},ensure_ascii=False,indent=2)+'\n')
    (target/'summary.json').write_text(json.dumps({'status':'research_complete' if all(r['research_status']=='complete' for r in rows) else 'partial',
            'total':len(rows),'report_id':rid,'md_sha256':by_id[rid]['packaged_md_sha256'],
            'extraction_coverage_complete':False,'scope':'Reviewed selection only; the full reports are not complete.'},ensure_ascii=False,indent=2)+'\n')
data=e.prepare('GAZP',staging,True)
assert [s['title'] for s in data['sheets']]==['2023','2024','2025']
input_path=HERE/'company.json';input_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
(HERE/'provenance.json').write_text(json.dumps({'scope':f'{len(provenance)} complete selected quotes, not the complete company corpus','records':provenance},ensure_ascii=False,indent=2)+'\n')
dependencies=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
if not (HERE/'node_modules').exists():(HERE/'node_modules').symlink_to(dependencies,target_is_directory=True)
output=Path(tempfile.mkdtemp(prefix='sber-annual-export-'))/'export'
builder=PROJECT/'04_Итоги_проверки/build_company_excel.mjs'
if not (builder.parent/'node_modules').exists():(builder.parent/'node_modules').symlink_to(dependencies,target_is_directory=True)
subprocess.run(['node',str(builder),str(input_path),str(output)],text=True,cwd=HERE,check=True)
destination=PROJECT/'04_Итоги_проверки/Газпром/Годовая_книга';destination.mkdir(exist_ok=True)
shutil.copy2(output/'Газпром.xlsx',destination/'Газпром.xlsx')
(destination/'CSV').mkdir(exist_ok=True)
for csv in (output/'CSV').glob('*.csv'):shutil.copy2(csv,destination/'CSV'/csv.name)
print(json.dumps({'filename':str(destination/'Газпром.xlsx'),'sheets':[s['title'] for s in data['sheets']],'rows':[len(s['rows']) for s in data['sheets']],'full_corpus_complete':False},ensure_ascii=False))
