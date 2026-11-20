from pathlib import Path
import sys,json,re,hashlib,base64,time
sys.path.insert(0,'/private/tmp/sber-pdf-libs')
import pymupdf as fitz
BASE=Path(__file__).resolve().parent.parent
ROOT=BASE.parents[2]
sys.path.insert(0,str(ROOT/'05_Инструменты/15_DeepSeek_API'))
from deepseek_client import Client

def source_details(rid,n):
    folder=BASE/'_проверка/геометрия'/rid;folder.mkdir(parents=True,exist_ok=True)
    with fitz.open(BASE/'_источники'/f'{rid}.pdf')as doc:
        page=doc[n-1];runs=[]
        for block in page.get_text('dict',flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)['blocks']:
            for line in block.get('lines',[]):
                if any(re.search(r'\d',s['text'])for s in line['spans']):
                    runs.append([{'text':s['text'],'size':round(s['size'],3),'flags':s['flags'],'bbox':[round(v,2)for v in s['bbox']]}for s in line['spans']])
        full=folder/f'page_{n:04d}_full.png'
        if not full.exists():page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).save(full)
        images=[full]
        if page.rect.width/page.rect.height>1.2:
            w,h=page.rect.width,page.rect.height
            for i,rect in enumerate([fitz.Rect(0,0,w*.56,h),fitz.Rect(w*.44,0,w,h)]):
                p=folder/f'page_{n:04d}_zoom_{i}.png'
                if not p.exists():page.get_pixmap(matrix=fitz.Matrix(2.2,2.2),clip=rect,alpha=False).save(p)
                images.append(p)
        return {'numeric_source_lines':runs,'image_meaning':'First is the complete PDF page, remaining images are overlapping magnifications of the same page, not separate pages. Do not duplicate their content.'},images

def main():
    rid='GAZP-2023-ОУР';n=57
    packet=json.loads((BASE/'_проверка/входы'/rid/f'page_{n:04d}.json').read_text())
    rich,images=source_details(rid,n)
    system=(BASE/'_проверка/Инструкция_на_старте.md').read_text()+'''
Сейчас транскрибируй только заданную физическую страницу в JSON {"pdf_page":integer,"markdown":string,"issues":[string]}.
К исходному изображению приложены его увеличенные области и числовые строки исходного PDF с размером шрифта, flags и координатами. Это не ответы другой модели.
При отделении сносок используй изображение и исходные spans совместно: не делай обычную последнюю цифру числа надстрочной; не присоединяй реальный надстрочный знак к числу. Не заменяй точное значение догадкой. Все ряды и столбцы сохраняй на своих местах.
Файлы изображений добавит сборщик, не создавай ссылки на несуществующие файлы. Не добавляй служебные маркеры страницы. В issues только конкретные нерешённые места чтения, а не описания успешно сохранённой вёрстки или картинок.
'''
    text=json.dumps({'page':packet,'source_geometry':rich},ensure_ascii=False)
    content=[{'type':'text','text':text}]+[{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode(),'detail':'original'}}for p in images]
    client=Client();client.config['timeout_seconds']=300;t=time.time();response=client.complete([{'role':'system','content':system},{'role':'user','content':content}],max_tokens=18000,json_mode=True)
    out=BASE/'_проверка/pilot_geometry';out.mkdir(exist_ok=True)
    (out/'raw.json').write_text(json.dumps(response,ensure_ascii=False,indent=2))
    answer=json.loads(response['choices'][0]['message']['content']);(out/'answer.json').write_text(json.dumps(answer,ensure_ascii=False,indent=2))
    (out/'input.json').write_text(json.dumps({'report_id':rid,'pdf_page':n,'system_sha256':hashlib.sha256(system.encode()).hexdigest(),'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'image_sha256':[hashlib.sha256(p.read_bytes()).hexdigest()for p in images]},indent=2))
    print('seconds',round(time.time()-t,1),'issues',answer['issues']);s=answer['markdown']
    for val in ['0,173','76,6','1,963']:
        i=s.find(val);print(val,s[max(0,i-55):i+100])
if __name__=='__main__':main()
