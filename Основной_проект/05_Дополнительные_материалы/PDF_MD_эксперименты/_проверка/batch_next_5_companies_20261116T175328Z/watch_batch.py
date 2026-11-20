from pathlib import Path
import subprocess,sys,json,time,datetime
AUDIT=Path(__file__).resolve().parent
BASE=AUDIT.parents[1]
seen=-1
while True:
 subprocess.run([sys.executable,str(AUDIT/'update_batch.py')],check=True)
 summary=json.loads((AUDIT/'batch_status.json').read_text())
 if summary['assembled']!=seen:
  subprocess.run([sys.executable,str(AUDIT/'render_batch.py')],check=True)
  subprocess.run([sys.executable,str(AUDIT/'verify_batch.py')],check=True)
  subprocess.run([sys.executable,str(BASE/'tools/update_corpus_index.py')],check=True)
  seen=summary['assembled']
 control=json.loads((BASE/'_проверка/codex_controller.json').read_text())
 state=subprocess.run(['ps','-p',str(control['pid']),'-o','stat='],capture_output=True,text=True).stdout.strip()
 if control['overall_status']!='running' or not state or state.startswith('Z'):
  subprocess.run([sys.executable,str(BASE/'tools/update_status.py')],check=True)
  (AUDIT/'watch_finished.json').write_text(json.dumps({'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'controller_status':control['overall_status'],'controller_alive':bool(state and not state.startswith('Z')),'assembled':summary['assembled'],'scope':'Assembly/render status, not checked PDF fidelity'},ensure_ascii=False,indent=2)+'\n')
  break
 time.sleep(45)
