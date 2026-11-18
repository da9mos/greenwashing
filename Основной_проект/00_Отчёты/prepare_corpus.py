from pathlib import Path
import re, json, csv, io, hashlib, subprocess, urllib.parse, collections
import pymupdf
VAULT=Path.cwd()
BASE=Path(__file__).resolve().parent
IDX=VAULT/'11_Проект_Сбер/Итоговый проект/Корпус_92_отчёта.md'
REPO=VAULT/'11_Проект_Сбер/3_итерация/greenwashing_esg_v3'
REG='01_итерация_1_сбор_данных/выборка_30/reports.csv'
raw=subprocess.check_output(['git','-C',str(REPO),'show','5597472:'+REG])
blob=subprocess.check_output(['git','-C',str(REPO),'rev-parse','5597472:'+REG],text=True).strip()
assert blob=='35326eb7d811bcc3b5a270bdb5dcc2131149eaa8',blob
registry=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),delimiter=';'))
reg={r['report_id']:r for r in registry}
rows=re.findall(r'^\| ([^|]+) \| \[([^]]+)\]\(([^)]+)\) \| (\d+) \| ([^|]+) \|',IDX.read_text(),re.M)
assert len(rows)==len(reg)==92 and len({r['company_id'] for r in registry})==30
assert {r[1] for r in rows}==set(reg)
manifest=[];errors=[]
for company,rid,link,pc,version in rows:
    original=(IDX.parent/urllib.parse.unquote(link)).resolve();source=original
    if rid=='GAZP-2023-ЭО':
        source=VAULT/'11_Проект_Сбер/Итоговый проект/1 шаг - перевод PDF в MD/Результаты работы/Газпром 2023 - экологический отчёт/report.md'
        version='Codex: рабочая версия с адресными исправлениями пилота; явная замена пути исходного индекса'
    row=reg[rid]; assert company==row['company'],(company,row['company'])
    text=source.read_text(); original_text=text
    pages=[int(n) for n in re.findall(r'<!--\s*pdf_page:\s*(\d+)\s*-->',text)]
    assert pages==list(range(1,int(pc)+1)),rid
    pdf=VAULT/'11_Проект_Сбер/2_итерация/Тесты_PDF_в_MD_DeepSeek_Codex/_источники'/f'{rid}.pdf'
    with pymupdf.open(pdf) as d: actual_pages=len(d)
    assert actual_pages==int(pc),(rid,actual_pages,pc)
    first=text.split('<!-- pdf_page:',1)[0]
    urls=re.findall(r'\[(?:Исходный PDF|Исходная ссылка|Архив источника)\]\(<?(https?://[^>\s)]+)>?\)',first)
    url=urls[0] if urls else f"https://drive.google.com/file/d/{row['drive_id']}/view"
    source_kind='archive' if ('[Архив источника]' in first or row['status']=='архив — распаковать') else 'pdf_or_source_file'
    replaced=[]
    parts=re.split(r'(<!--\s*pdf_page:\s*\d+\s*-->)',text)
    current=0
    for i,part in enumerate(parts):
        mm=re.fullmatch(r'<!--\s*pdf_page:\s*(\d+)\s*-->',part)
        if mm:current=int(mm[1]);continue
        def replace_image(m):
            alt,target=m.group(1),m.group(2).strip('<>')
            if not target.startswith(('assets/','./assets/','../','/')):return m.group(0)
            replaced.append({'pdf_page':current,'original_target':target,'alt':alt})
            label=f'Визуальный материал: {alt}. Физическая PDF-страница {current}'
            return f'> {label}. Изображение не включено в эту Markdown-версию; [открыть источник]({url}). Визуальная сверка не подтверждается этой ссылкой.'
        part=re.sub(r'!\[([^\]]*)\]\(([^)]+)\)',replace_image,part)
        def replace_html(m):
            replaced.append({'pdf_page':current,'original_target':m.group(0),'alt':'локальное HTML-изображение'})
            return f' (визуальный элемент оригинала, PDF-страница {current}; изображение не включено) '
        part=re.sub(r'<img\b[^>]*src=["\'](?:\./)?assets/[^"\']+["\'][^>]*>',replace_html,part)
        parts[i]=part
    text=''.join(parts)
    # Adjust only packaging statements that otherwise promise absent local files.
    text=text.replace('`_проверка/pages.json`','локальном журнале исходной конвертации (не включён; статус этой копии: неполная сверка)')
    text=text.replace('После текста каждой страницы доступно её исходное изображение; оно сохраняет графику, подписи и возможность проверить спорные места.','После текста каждой страницы указан источник визуальной сверки; локальные изображения в эту копию не включены.')
    text=text.replace('Изображения страниц сохраняют исходную графику и служат визуальной опорой.','Исходную графику следует проверять в PDF: локальные изображения в эту копию не включены.')
    status='Полная визуальная и смысловая сверка не завершена. Структурная проверка страниц и идентификатора выполнена; это не подтверждает точность OCR, чисел, таблиц или полноту заявлений.'
    header=f'''# {rid} — {company}\n\n- Идентификатор: `{rid}`. Компания: `{row['company_id']}` — {company}.\n- Год реестра: {row['year']}; тип: {row['report_type']}. Год сохранён из reports.csv, не переинтерпретирован по названию PDF.\n- Версия Markdown: {version}.\n- Физических PDF-страниц: {pc}; проверено открытием локального PDF и последовательностью маркеров.\n- [PDF / исходный файл]({url}). Вид источника: {source_kind}. Доступность внешнего URL заново не проверялась; для архива нужен PDF внутри.\n- Проверка: {status}\n- Реестр: `da9mos/greenwashing`, commit `5597472`, blob `{blob}`.\n- Визуальный статус: изображения в Markdown не встроены. Их указатели сохранены у соответствующих физических страниц; графику и OCR сверять по исходному PDF.\n\n---\n\n'''
    dest=BASE/company/f'{rid}.md';dest.parent.mkdir(exist_ok=True)
    dest.write_text(header+text)
    out=dest.read_text()
    assert re.findall(r'<!--\s*pdf_page:\s*(\d+)\s*-->',out)==[str(n) for n in pages],rid
    anchors=re.findall(r'<a\s+id="([^"]+)"',out)
    assert len(anchors)==len(set(anchors)),rid
    assert set(f'pdf-page-{n}' for n in pages)<=set(anchors),rid
    local_links=[];bad_anchors=[]
    for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',out):
        target=target.strip('<>')
        if target.startswith('#'):
            if target[1:] not in anchors:bad_anchors.append(target)
        elif not re.match(r'^(?:https?://|mailto:|tel:)',target):local_links.append(target)
    assert not local_links,(rid,local_links[:3])
    if bad_anchors:errors.append({'report_id':rid,'kind':'preexisting_broken_fragment_links','targets':sorted(set(bad_anchors))})
    assert not re.search(r'(?:src|href)=["\'](?:\./)?assets/',out),rid
    manifest.append({**row,'repository_path':str(dest.relative_to(BASE.parent)),'physical_pages':actual_pages,'version':version,'source_md':str(source.relative_to(VAULT)),'index_source_md':str(original.relative_to(VAULT)),'source_override':source!=original,'source_md_sha256':hashlib.sha256(original_text.encode()).hexdigest(),'packaged_md_sha256':hashlib.sha256(out.encode()).hexdigest(),'pdf_source_url':url,'pdf_source_kind':source_kind,'external_url_reverified':False,'verification_status':status,'visual_reference_count':len(replaced),'visual_references':replaced,'page_markers_verified':True,'pdf_page_count_verified':True,'preexisting_broken_fragment_links':sorted(set(bad_anchors))})
validation={'report_count':len(manifest),'company_count':len({r['company_id'] for r in manifest}),'physical_pages':sum(r['physical_pages'] for r in manifest),'registry_commit':'5597472','registry_blob':blob,'registry_verified_via':'GitHub fetch_file and identical local git blob','all_ids_match_registry':True,'all_local_pdfs_opened':True,'all_page_markers_in_order':True,'all_page_anchors_present_and_unique':True,'local_asset_links_remaining':0,'visual_references_replaced':sum(r['visual_reference_count'] for r in manifest),'full_content_verified':False,'exceptions':errors}
(BASE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
(BASE/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2))
print(json.dumps(validation,ensure_ascii=False,indent=2))
