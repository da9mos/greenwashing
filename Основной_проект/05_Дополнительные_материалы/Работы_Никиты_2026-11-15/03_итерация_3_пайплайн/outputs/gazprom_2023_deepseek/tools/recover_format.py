import sys,base64,json,hashlib,time
import run_deepseek as b
from deepseek_client import Client
n=85;client=Client();client.config['timeout_seconds']=240
content=[{'type':'text','text':'PDF-страница85. Перенеси всё содержимое изображений в Markdown. Сначала левая, потом правая печатная страница. Никакого JSON, только документ.'}];hashes=[]
for i in [0,1]:
 data=(b.O/'images'/f'social_085_{i}.png').read_bytes();hashes.append(hashlib.sha256(data).hexdigest());content.append({'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(data).decode(),'detail':'original'}})
system=b.SYSTEM.split('Ответ JSON object:')[0]+'Ответ только Markdown, без JSON и без ограждающего блока кода. Не выводи рассуждения.'
t=time.monotonic();r=client.complete([{'role':'system','content':system},{'role':'user','content':content}],max_tokens=14000)
(b.O/'errors/social_085_format_recovery_response.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
m=r['choices'][0]['message']['content'];assert r['choices'][0]['finish_reason']=='stop';assert len(m)>100;assert '\n'in m;assert not m.strip().startswith('{')
result={'report':'social','pdf_page':85,'version':'v1','response':{'pdf_page':85,'printed_pages':None,'markdown':m,'problems':['Structured-output failures recovered with plain Markdown; no automatic JSON repair'],'review_status':'converted'},'model':r.get('model'),'usage':r.get('usage'),'finish_reason':'stop','seconds':round(time.monotonic()-t,2),'image_sha256':hashes,'system_sha256':hashlib.sha256(system.encode()).hexdigest(),'format_recovery':True,'system_prompt':system,'extra_instruction':'Plain Markdown fallback after two invalid JSON responses; original errors retained'}
(b.O/'v1/social_085.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print('RECOVERED_085',len(m))
