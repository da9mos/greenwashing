import pathlib,json,re,hashlib
root=pathlib.Path('result');check=root/'_проверка'
s=(root/'report.md').read_text()
for n in [2,123]:
 start=s.index(f'<!-- pdf_page: {n} -->');end=s.find('<!-- pdf_page:',start+20);end=len(s) if end<0 else end
 block=s[start:end]; marker='> Служебная информация: ссылки исходного PDF'
 text='> Служебная пометка: часть внутренних назначений PDF некорректна или не установлена однозначно. Видимые номера сохранены; переходы не восстановлены по догадке. Ссылки ниже воспроизводят назначения исходного PDF и не подтверждены содержательно.\n\n'
 block=block.replace(marker,text+marker,1);s=s[:start]+block+s[end:]
(root/'report.md').write_text(s)
cov=json.load(open(check/'native_coverage.json'))
if not (check/'native_coverage.baseline.json').exists():(check/'native_coverage.baseline.json').write_text(json.dumps(cov,ensure_ascii=False,indent=2)+'\n')
cov['applies_to']='Исходный механический кандидат _проверка/report.native.md; посимвольный инвентарь итоговой исправленной версии этим файлом не удостоверяется.'
cov['final_report_sha256']=hashlib.sha256(s.encode()).hexdigest();cov['final_review_registry']='pages.json';cov['final_semantic_source_review_completed']=False
(check/'native_coverage.json').write_text(json.dumps(cov,ensure_ascii=False,indent=2)+'\n')
(check/'render_validation.json').write_text(json.dumps({'markdown_to_html':'completed','html_structure_and_links':'parsed_and_validated','browser_visual_review':'blocked','reason':'Установленный Chromium не запускается в sandbox: bootstrap_check_in / MachPortRendezvousServer Permission denied (1100). Ничего не скачивалось.','visual_display_checked':False,'preview_file':'report.preview.html','scope':'HTML собран и разобран парсером; фактическое браузерное отображение не проверено.'},ensure_ascii=False,indent=2)+'\n')
