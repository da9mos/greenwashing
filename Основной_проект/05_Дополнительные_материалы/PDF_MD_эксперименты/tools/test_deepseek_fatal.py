"""No provider/keychain/native-PDF calls: dependency modules are stubbed at import."""
import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

TOOLS=Path(__file__).resolve().parent


def load_module(name,path,stubs=None):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,stubs or {}):spec.loader.exec_module(module)
    return module


class FatalDependencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);(self.base/'_проверка').mkdir()
        self.rm=types.ModuleType('run_models');self.rm.BASE=self.base
        self.rm.ROWS=[{'report_id':'A'},{'report_id':'B'}];self.rm.INSTRUCTION_SHA='frozen'
        def put_json(path,data):
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(data))
        self.rm.put_json=put_json;self.rm.log=Mock();self.rm.assemble_deepseek=Mock(return_value=True)
        v3=types.ModuleType('run_deepseek_v3');v3.VERSION='v3'
        v3.transcribe=Mock(side_effect=AssertionError('No provider calls allowed'))
        prep=types.ModuleType('prepare_geometry');prep.prepare_report=Mock()
        self.runtime=load_module('fatal_runtime',TOOLS/'run_deepseek_corpus.py',
                                 {'run_models':self.rm,'run_deepseek_v3':v3,'prepare_geometry':prep})
        self.monitor=load_module('fatal_monitor',TOOLS/'monitor_run.py')

    def write(self,path,data):self.rm.put_json(self.base/path,data)

    def test_provider_status_and_balance_classification_not_page_numbers(self):
        for code,kind in ((401,'auth'),(402,'balance'),(403,'access')):
            with self.subTest(code=code):
                text=self.runtime.dependency_error(RuntimeError(f'DeepSeek HTTP {code}: provider rejected'))
                self.assertEqual(text['kind'],kind)
                exc=RuntimeError('rejected');exc.response=types.SimpleNamespace(status_code=code)
                self.assertEqual(self.runtime.dependency_error(exc)['http_status'],code)
        self.assertEqual(self.runtime.dependency_error(RuntimeError('insufficient_balance_error'))['kind'],'balance')
        self.assertEqual(self.runtime.dependency_error(RuntimeError('DeepSeek credential unavailable in macOS Keychain'))['kind'],'auth')
        self.assertIsNone(self.runtime.dependency_error(RuntimeError('page 402 has malformed markdown')))
        self.assertIsNone(self.runtime.dependency_error(RuntimeError('DeepSeek HTTP 429: rate limit')))

    def test_fatal_latches_whole_14731_page_queue_without_retry(self):
        for code in (401,402,403):
            with self.subTest(code=code):
                stop=self.runtime.FatalStop()
                with patch.object(self.runtime,'transcribe',side_effect=RuntimeError(f'DeepSeek HTTP {code}: rejected')) as call:
                    for page in range(1,14732):
                        result=self.runtime.attempt_page({'report_id':'A'},{'pdf_page':page},2,stop)
                        self.assertEqual(result['state'],'deferred_external_dependency')
                    self.assertEqual(call.call_count,1)
                self.assertFalse(list(self.base.rglob('errors/page_*.json')))

    def test_already_inflight_success_is_kept_after_global_stop(self):
        stop=self.runtime.FatalStop();folder=self.base/'_проверка/DeepSeek/A/v3'
        raw=folder/'raw/page_0001.json';saved=folder/'page_0001.json'
        self.rm.put_json(raw,{'existing':'raw'});self.rm.put_json(saved,{'existing':'answer'})
        old_raw=raw.read_bytes();old_saved=saved.read_bytes()
        def success(*args):
            stop.trip(self.runtime.dependency_error(RuntimeError('HTTP 402: blocked')))
            return {'review_status':'converted','model':'mock','usage':{}}
        with patch.object(self.runtime,'transcribe',side_effect=success):
            result=self.runtime.attempt_page({'report_id':'A'},{'pdf_page':1},2,stop)
        self.assertTrue(result['success'])
        self.assertEqual(raw.read_bytes(),old_raw);self.assertEqual(saved.read_bytes(),old_saved)

    def test_persisted_block_prevents_pools_and_provider_calls(self):
        self.write('_проверка/job.json',{'pid':os.getpid(),'status':'blocked_deepseek_balance'})
        self.write('_проверка/sources_manifest.json',{'reports':[{'report_id':'A','pages':10},{'report_id':'B','pages':20}]})
        with patch.object(self.runtime.futures,'ProcessPoolExecutor') as prep,patch.object(self.runtime.futures,'ThreadPoolExecutor') as api,patch.object(self.runtime,'transcribe') as request:
            with self.assertRaises(SystemExit) as end:self.runtime.main(['--workers','64'])
        self.assertEqual(end.exception.code,3);prep.assert_not_called();api.assert_not_called();request.assert_not_called()
        control=json.loads((self.base/'_проверка/deepseek_controller.json').read_text())
        self.assertEqual(control['counts']['page_failures'],0)
        self.assertEqual(control['counts']['reports_deferred_external_dependency'],2)
        self.assertEqual(control['counts']['pages_deferred_external_dependency'],30)
        self.assertTrue(all(s['stage']=='deferred_external_dependency' for s in control['reports'].values()))

    def test_direct_page_entry_cannot_bypass_persisted_block(self):
        self.write('_проверка/job.json',{'status':'blocked_deepseek_balance'})
        with patch.object(self.runtime,'transcribe') as request:
            result=self.runtime.attempt_page({'report_id':'A'},{'pdf_page':1},2)
        request.assert_not_called()
        self.assertEqual(result['state'],'deferred_external_dependency')
        self.assertEqual(result['attempts'],0)

    def test_blocked_snapshot_keeps_saved_responses_out_of_deferred_page_list(self):
        self.write('_проверка/job.json',{'pid':os.getpid(),'status':'blocked_deepseek_balance'})
        self.write('_проверка/sources_manifest.json',{'reports':[{'report_id':'A','pages':3}]})
        self.write('_проверка/DeepSeek/A/v3/page_0001.json',{
            'instruction_sha256':'frozen','response':{'pdf_page':1,'markdown':'saved answer'}})
        saved=self.base/'_проверка/DeepSeek/A/v3/page_0001.json';before=saved.read_bytes()
        with patch.object(self.runtime,'transcribe') as request:
            with self.assertRaises(SystemExit):self.runtime.main(['--reports','A'])
        request.assert_not_called();self.assertEqual(saved.read_bytes(),before)
        state=json.loads((self.base/'_проверка/deepseek_controller.json').read_text())['reports']['A']
        self.assertEqual(state['responses_already_saved'],[1])
        self.assertEqual(state['pages_deferred_external_dependency'],[2,3])

    def test_real_event_queue_cancels_pending_work_and_preserves_saved_raw(self):
        self.write('_проверка/job.json',{'pid':os.getpid(),'status':'running'})
        self.write('_проверка/sources_manifest.json',{'reports':[{'report_id':'A','pages':240},{'report_id':'B','pages':240}]})
        self.write('_проверка/DeepSeek/A/v3/raw/page_0001.json',{'preserved':'raw'})
        self.write('_проверка/DeepSeek/A/v3/page_0001.json',{'preserved':'answer'})
        cached=self.base/'_проверка/DeepSeek/A/v3/page_0001.json';before=cached.read_bytes()
        def prepare(row):return {'pages':[{'pdf_page':n} for n in range(1,241)]}
        def request(row,page):
            if row['report_id']=='A' and page['pdf_page']==1:return {'review_status':'converted','model':'mock','usage':{}}
            raise RuntimeError('DeepSeek HTTP 402: insufficient_balance_error')
        real_thread_pool=concurrent.futures.ThreadPoolExecutor
        def process_stub(**kwargs):return real_thread_pool(max_workers=kwargs['max_workers'])
        with patch.object(self.runtime,'prepare_report',side_effect=prepare),patch.object(self.runtime,'transcribe',side_effect=request) as call,patch.object(self.runtime.futures,'ProcessPoolExecutor',side_effect=process_stub):
            with self.assertRaises(SystemExit) as end:self.runtime.main(['--workers','1','--prepare-workers','1','--attempts','2'])
        self.assertEqual(end.exception.code,3);self.assertEqual(call.call_count,2)
        self.assertEqual(cached.read_bytes(),before)
        self.assertTrue((cached.parent/'raw/page_0001.json').exists())
        control=json.loads((self.base/'_проверка/deepseek_controller.json').read_text())
        self.assertEqual(control['counts']['page_failures'],0)
        self.assertEqual(control['counts']['reports_deferred_external_dependency'],2)
        self.assertFalse(any(s['stage']=='source_error' for s in control['reports'].values()))
        self.assertEqual(json.loads((self.base/'_проверка/job.json').read_text())['status'],'blocked_deepseek_balance')

    def test_normal_controller_null_dependency_does_not_block_resume(self):
        self.write('_проверка/deepseek_controller.json',{'dependency':None})
        self.assertIsNone(self.runtime.persisted_dependency(self.base))

    def test_monitor_cannot_replace_blocked_balance_even_if_codex_complete(self):
        current={'pid':7,'status':'blocked_deepseek_balance','failure':'HTTP402','Codex_version':'v2'}
        result=self.monitor.final_job_state(current,7,{'overall_complete':True},123)
        self.assertEqual(result['status'],'blocked_deepseek_balance')
        self.assertEqual(result['failure'],'HTTP402');self.assertEqual(result['monitor_ended_at'],123)
        self.assertNotIn('ended_at',result)
        self.assertEqual(current['status'],'blocked_deepseek_balance')

    def test_monitor_does_not_overwrite_replaced_controller(self):
        self.assertIsNone(self.monitor.final_job_state({'pid':9,'status':'running'},7,{'overall_complete':True}))
        result=self.monitor.final_job_state({'pid':7,'status':'running'},7,{'overall_complete':True},123)
        self.assertEqual(result['status'],'ended')


if __name__=='__main__':unittest.main()
