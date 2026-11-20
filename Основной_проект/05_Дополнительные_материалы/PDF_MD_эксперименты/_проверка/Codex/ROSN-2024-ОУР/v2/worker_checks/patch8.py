from pathlib import Path
r=Path('result');f=r/'_проверка/pages/0008.md';old=f.read_text();new=old.replace('- В 2024 году мероприя\nтия программы','### 13. Борьба с изменением климата\n\n- В 2024 году мероприятия программы').replace('- Главный исполни\nтельный директор','### 17. Партнерство в интересах устойчивого развития\n\n- Главный исполнительный директор').replace('Cuba\nPetróleo Union (CUPET)\n\n\n- Соглашение о сотрудни\nчестве','Cuba\nPetróleo Union (CUPET)\nсоглашение о сотрудничестве')
for a,b in [('напра\nвила','направила'),('выполне\nния','выполнения')]:new=new.replace(a,b)
f.write_text(new);report=(r/'report.md').read_text();assert old.strip() in report;report=report.replace(old.strip(),new.strip(),1);(r/'report.md').write_text(report)
