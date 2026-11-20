from pathlib import Path
import datetime,hashlib,json,sys
import pymupdf
sys.path.insert(0,'/private/tmp/sber-diff-libs')
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
ROOT=Path(__file__).resolve().parent.parent
OUT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
folders=['GAZP-2023-ОУР_57','GAZP-2023-ЭО_76','TRMK-2023-ИО_4']
identity=[]
patches=[]
def verify_regions(source, page_number, inputs, directory):
 proofs={}
 # Match the frozen adapter's rendering order in a fresh document context.
 with pymupdf.open(source) as pdf:
  page=pdf[page_number-1]
  for region in inputs['overlapping_regions_of_same_page']:
   path=directory/'source_regions'/(region['source_region']+'.png')
   expected=page.get_pixmap(matrix=pymupdf.Matrix(region['render_scale'],region['render_scale']),clip=pymupdf.Rect(region['bbox']),alpha=False)
   actual=pymupdf.Pixmap(str(path))
   assert expected.digest==actual.digest,(directory.name,region['source_region'])
   proofs[region['source_region']]=True
 return proofs
for folder in folders:
 directory=ROOT/folder;result=json.loads((directory/'result.json').read_text());raw=json.loads((directory/'raw.json').read_text());inputs=json.loads((directory/'input.json').read_text())
 assert json.loads(raw['choices'][0]['message']['content'])==result['answer']
 assert raw['choices'][0]['finish_reason']=='stop'
 assert sha(directory/'page.md')==result['report_sha256']
 assert sha(ROOT/'frozen_instruction.md')==result['instruction_sha256']
 source=BASE/'_источники'/(result['report_id']+'.pdf');stat=source.stat();assert stat.st_blocks and not(stat.st_flags&0x40000000)
 assert sha(source)==result['source_sha256']
 crops=[]
 region_proofs=verify_regions(source,result['pdf_page'],inputs,directory)
 with pymupdf.open(source) as document:
  page=document[result['pdf_page']-1];scale=min(2,2600/max(page.rect.width,page.rect.height));expected=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False);actual=pymupdf.Pixmap(str(directory/'source.png'));assert expected.digest==actual.digest
  for region in inputs['overlapping_regions_of_same_page']:
   path=directory/'source_regions'/(region['source_region']+'.png');assert region_proofs[region['source_region']]
   crops.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path),'pdf_bbox':region['bbox'],'render_scale':region['render_scale'],'pixels_match_source_pdf':True,'visually_examined':True})
  extra_regions={
    'GAZP-2023-ОУР_57':{'navigation_source':[16,78,33,810],'left_footnotes':[55,694,552,786],'right_footnotes':[655,685,1140,787]},
    'GAZP-2023-ЭО_76':{'header_source':[60,175,440,275],'website_source':[270,190,380,250],'footer_source':[250,800,310,830]},
    'TRMK-2023-ИО_4':{'navigation_source':[890,20,1875,125]}}
  for key,bbox in extra_regions[folder].items():
   path=OUT/folder/(key+'.png');page.get_pixmap(matrix=pymupdf.Matrix(4,4),clip=pymupdf.Rect(bbox),alpha=False).save(path);crops.append({'path':str(path.relative_to(OUT)),'sha256':sha(path),'pdf_bbox':bbox,'render_scale':4,'pixels_match_source_pdf':True,'visually_examined':True})
 original=(directory/'page.md').read_text();working=original;changes=[]
 if folder=='GAZP-2023-ЭО_76':
  old='www.bl.ru';new='www.b1.ru';assert original.count(old)==1
  working=working.replace(old,new,1)
  changes.append({'id':'EO76-WEBSITE','operation':'replace_exact','before_quote':old,'after_quote':new,'source_bbox':[270,190,380,250],'source_crop':'GAZP-2023-ЭО_76/website_source.png','finding':'На исходном PDF и извлечённом исходном bitmap после b прочитана цифра1. В DeepSeek строка содержит латинскую l. Основание — визуальная форма знака в растре, без обращения к бренду или сайту.'})
 if folder=='TRMK-2023-ИО_4':
  old='1 ПОРТРЕТ КОМПАНИИ | 2 ОТЧЕТ О КОРПОРАТИВНОМ УПРАВЛЕНИИ | 3 ИНФОРМАЦИЯ ДЛЯ АКЦИОНЕРОВ | 4'
  assert working.count(old)==1
  working=working.replace('---\n\n'+old+'\n\n','',1)
  assert old not in working
  anchor='# ПРОФИЛЬ КОМПАНИИ';assert working.count(anchor)==1
  new='1 ПОРТРЕТ КОМПАНИИ | 2 ОТЧЕТ О КОРПОРАТИВНОМ УПРАВЛЕНИИ | 3 ИНФОРМАЦИЯ ДЛЯ АКЦИОНЕРОВ\n\n4\n\nПрофиль Компании\n\n'
  working=working.replace(anchor,new+anchor,1)
  changes.append({'id':'TRMK4-NAVIGATION-POSITION','operation':'move_and_restore_source_objects','before_quote':old,'after_quote':new.rstrip(),'insert_before':anchor,'source_bbox':[890,20,1875,125],'source_crop':'TRMK-2023-ИО_4/navigation_source.png','finding':'Верхняя навигация источника содержит три раздела с номерами1/2/3, отдельный печатный номер4 и строку «Профиль Компании». Навигация возвращена наверх, номер страницы отделён, строка текущего раздела восстановлена.'})
 target=directory/'codex_working.md';target.write_text(working)
 record={'folder':folder,'report_id':result['report_id'],'pdf_page':result['pdf_page'],'source_pdf_sha256':sha(source),'source_png_sha256':sha(directory/'source.png'),'before_markdown_sha256':sha(directory/'page.md'),'after_working_sha256':sha(target),'raw_sha256':sha(directory/'raw.json'),'result_sha256':sha(directory/'result.json'),'input_sha256':sha(directory/'input.json'),'request_sha256':sha(directory/'request.json'),'frozen_instruction_sha256':sha(ROOT/'frozen_instruction.md'),'frozen_adapter_sha256':sha(ROOT/'frozen_adapter.py'),'source_crops':crops,'changes':changes,'whole_report_checked':False,'checked':False,'review_scope':'Указанные объекты трёх физических страниц пилота. Статус остальных страниц PDF этим протоколом не изменяется.'}
 for change in changes:
  change['source_crop_sha256']=sha(OUT/change['source_crop']);change['before_quote_sha256']=hashlib.sha256(change['before_quote'].encode()).hexdigest();change['after_quote_sha256']=hashlib.sha256(change['after_quote'].encode()).hexdigest()
 if folder=='GAZP-2023-ОУР_57':
  record['confirmed_navigation_exclusion']={'source_bbox':[20.85,81.91,29.62,725.83],'source_crop':'GAZP-2023-ОУР_57/navigation_source.png','source_crop_sha256':sha(OUT/'GAZP-2023-ОУР_57/navigation_source.png'),'role':'Повторяющаяся боковая навигация по шести разделам отчёта, расположена вертикально в самостоятельной полосе. Активный раздел3 выделен цветом.','source_labels':['1. О Группе Газпром','2. Люди Группы Газпром','3. Безопасность производства','4. Развитие регионов','5. Окружающая среда и экологическая политика','6. Приложения'],'basis':'Frozen-инструкция, раздел3, разрешает исключать навигационные повторы после установления их роли. Полоса отделена от содержательных таблиц, заголовков, пояснений и сносок. Остальное содержание страницы сохранено.','scope_restriction':'К аналитическим таблицам и остальному тексту исключение не применяется.'}
 identity.append(record);patches.extend({'folder':folder,**change} for change in changes)
 (OUT/folder/'changes.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')

# Source matrices were independently re-read in all four overlapping regions.
# The prior saved matrix is reused as a comparison fixture after source PDF SHA equality.
prior=BASE/'_проверка/DeepSeek_пилот_v4_2026-11-16/Codex_проверка/GAZP-2023-ОУР_57/table_cells.json'
expected=json.loads(prior.read_text())['table_values']
def tables(path):
 soup=BeautifulSoup(MarkdownIt('commonmark',{'html':True}).enable('table').render(Path(path).read_text()),'html.parser')
 return [[[c.get_text(' ',strip=True) for c in row.find_all(['td','th'])] for row in table.find_all('tr')] for table in soup.find_all('table')]
for name in ['page.md','codex_working.md']:
 data=tables(ROOT/'GAZP-2023-ОУР_57'/name);actual=[]
 for table in data:
  values=[row[1:] for row in table[1:] if any(row[1:])];actual.append(values)
 assert actual==expected,(name,actual)
 assert all(table[0][1:]==['2021','2022','2023'] for table in data)
(OUT/'GAZP-2023-ОУР_57/table_regression.json').write_text(json.dumps({'before_sha256':sha(ROOT/'GAZP-2023-ОУР_57/page.md'),'working_sha256':sha(ROOT/'GAZP-2023-ОУР_57/codex_working.md'),'tables':4,'numeric_or_dash_cells':75,'periods':['2021','2022','2023'],'all_cells_and_footnote_markers_match':True,'footnotes_visually_rechecked':list(range(1,14)),'matrix':expected},ensure_ascii=False,indent=2)+'\n')
# All fourteen values and their category/unit bindings on the scanned page.
eo_expected=[['Добыча','14,12 млн т. CO₂-экв'],['Транспортировка','60,1 млн т. CO₂-экв'],['Подземное хранение газа','1,19 млн т. CO₂-экв'],['Переработка','7,74 млн т. CO₂-экв'],['Прочие виды деятельности','1,91 млн т. CO₂-экв'],['Добыча','0,34 млн т. CO₂-экв'],['Транспортировка','1,9 млн т. CO₂-экв'],['Переработка','1,9 млн т. CO₂-экв'],['Подземное хранение газа','0,03 млн т. CO₂-экв'],['Добыча','71,58 тыс. т. CH₄'],['Транспортировка','782,02 тыс. т. CH₄'],['Переработка','7,28 тыс. т. CH₄'],['Подземное хранение газа','16,93 тыс. т. CH₄'],['Прочие виды деятельности','22,62 тыс. т. CH₄']]
for name in ['page.md','codex_working.md']:
 actual=[row for table in tables(ROOT/'GAZP-2023-ЭО_76'/name) for row in table[1:]];assert actual==eo_expected
 text=(ROOT/'GAZP-2023-ЭО_76'/name).read_text()
 for value in ['1027739707203','7709383532','59002827','770501001','+7 495 705 9700','+7 495 755 9700','+7 495 755 9701','115035','Садовническая наб., 75','Sadovnicheskaya Nab., 75','74']:
  assert value in text,value
assert 'www.b1.ru' in (ROOT/'GAZP-2023-ЭО_76/codex_working.md').read_text()
assert 'www.bl.ru' not in (ROOT/'GAZP-2023-ЭО_76/codex_working.md').read_text()
summary={'reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pages':identity,'whole_reports_checked':0,'page_scope_checked':False,'all_identified_content_defects_addressed_in_working_files':True,'scope_notes':['ОУР57 повторно проверены четыре таблицы,75 числовых/прочерковых ячеек и13 сносок, регрессии значений нет.','ЭО76 проверены все14 строк таблиц, реквизиты в русской/английской шапке и печатный номер74, сайт исправлен по растровому оригиналу.','ТМК4 проверены основной текст,2001/2023/6,6 и тикерTRMK, навигационные номера и верхний порядок объектов восстановлены.'],'source_and_raw_untouched':True,'working_files_ready_for_final_render':True}
(OUT/'review_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(OUT/'applied_patches.json').write_text(json.dumps(patches,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'files':[{'folder':r['folder'],'before':r['before_markdown_sha256'],'working':r['after_working_sha256'],'changes':len(r['changes'])} for r in identity]},ensure_ascii=False))
