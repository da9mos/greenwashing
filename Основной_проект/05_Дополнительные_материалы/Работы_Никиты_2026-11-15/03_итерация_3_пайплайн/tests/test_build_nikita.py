import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC=Path(__file__).resolve().parents[1]/'src'
sys.path.insert(0,str(SRC))
from build_nikita import EvidenceStore,allocate_quotas,assign_claim_id,build,csv_bytes,derive_status,has_number,verify_calculation,write_outputs

class NikitaTests(unittest.TestCase):
    def test_quote_must_be_on_exact_page_and_same_company(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'AAAA-2023-ОУР.jsonl').write_text(json.dumps({'report_id':'AAAA-2023-ОУР','page':1,'text':'Цель: снизить выбросы до 10 тонн к 2025 году.'},ensure_ascii=False)+'\n')
            store=EvidenceStore(p,[{'report_id':'AAAA-2023-ОУР','company_id':'AAAA','year':'2023','drive_id':'abc'}])
            e={'report_id':'AAAA-2023-ОУР','page':1,'quote':'снизить  выбросы\nдо 10 тонн'}
            self.assertEqual(store.verify(e,'AAAA')['page'],1)
            with self.assertRaisesRegex(ValueError,'stated page'):store.verify(dict(e,page=2),'AAAA')
            with self.assertRaisesRegex(ValueError,'mismatch'):store.verify(e,'BBBB')
            with self.assertRaisesRegex(ValueError,'stated page'):store.verify(dict(e,quote='снизить выбросы до 99 тонн'),'AAAA')

    def test_unknown_future_and_noncomparable_are_not_failures(self):
        t={'target_year':2025,'target_value':10,'direction':'down'}
        self.assertEqual(derive_status(t,[]),'нет данных')
        self.assertEqual(derive_status(t,[{'year':2024,'value':20}]),'нет данных')
        self.assertEqual(derive_status(dict(t,target_year=2030),[]),'срок не наступил')
        self.assertEqual(derive_status(dict(t,comparison_valid=False),[{'year':2025,'value':0}]),'нет данных')
        self.assertEqual(derive_status(t,[{'year':2025,'value':None,'reported_value':0}]),'нет данных')
        self.assertEqual(derive_status(t,[{'year':2025,'value':9}]),'выполнена')
        self.assertEqual(derive_status(t,[{'year':2025,'value':11}]),'не выполнена')
        self.assertEqual(derive_status(dict(t,direction='>'),[{'year':2025,'value':10}]),'не выполнена')
        self.assertEqual(derive_status(dict(t,direction='<'),[{'year':2025,'value':10}]),'не выполнена')
        self.assertEqual(derive_status(dict(t,direction='>'),[{'year':2025,'value':11}]),'выполнена')

    def test_claim_ids_are_deterministic_and_do_not_reuse_existing_ids(self):
        a={'AAAA-2023-001','AAAA-2023-010','BBBB-2023-900'}
        b=set(a)
        self.assertEqual(assign_claim_id('AAAA',2023,a),'AAAA-2023-011')
        self.assertEqual(assign_claim_id('AAAA',2023,b),'AAAA-2023-011')
        self.assertEqual(assign_claim_id('AAAA',2023,a),'AAAA-2023-012')

    def test_exact_500_capacity_and_weights(self):
        caps={f'C{i:03d}':30 for i in range(30)};caps['C000']=16
        qualities={k:'обычная' for k in caps};qualities['C001']='слабая';qualities['C002']='неопределена'
        a=allocate_quotas(caps,qualities)
        self.assertEqual(sum(a.values()),500)
        self.assertTrue(all(0<a[k]<=caps[k]for k in a))
        self.assertLess(a['C001'],a['C003'])
        self.assertEqual(a,allocate_quotas(dict(reversed(list(caps.items()))),qualities))
        with self.assertRaises(ValueError):allocate_quotas({'A':2}, {}, 500)

    def test_locale_numbers_and_csv_contract(self):
        self.assertTrue(has_number('1250.5','Показатель 1 250,5 тонн.'))
        self.assertTrue(has_number(0,'Цель НУЛЕВОГО смертельного травматизма'))
        self.assertFalse(has_number(50,'Показатель 150 тонн.'))
        raw=csv_bytes([{'name':'цель; измерение','value':'10,5'}],['name','value'])
        self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
        rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),delimiter=';'))
        self.assertEqual(rows[0]['name'],'цель; измерение')

    def fixture(self,path,bad_quote=False):
        repo=path/'repo';pipeline=repo/'03_итерация_3_пайплайн'
        for d in [repo/'01_итерация_1_сбор_данных/выборка_30',pipeline/'data/out',pipeline/'data/pages',pipeline/'llm/nikita_dynamics/v1']:d.mkdir(parents=True,exist_ok=True)
        registry=repo/'01_итерация_1_сбор_данных/выборка_30'
        companies=[{'company_id':c,'company':c}for c in ['AAAA','BBBB']]
        (registry/'companies.csv').write_bytes(csv_bytes(companies,['company_id','company']))
        reports=[]
        for c in ['AAAA','BBBB']:
            for y in [2023,2025]:
                rid=f'{c}-{y}-ОУР';reports.append({'report_id':rid,'company_id':c,'year':y,'drive_id':f'{c}{y}'})
                text='Цель: снизить выбросы до 10 тонн к 2025 году.' if y==2023 else 'В 2025 году выбросы составили 9 тонн.'
                (pipeline/f'data/pages/{rid}.jsonl').write_text(json.dumps({'report_id':rid,'page':1,'text':text},ensure_ascii=False)+'\n')
        (registry/'reports.csv').write_bytes(csv_bytes(reports,['report_id','company_id','year','drive_id']))
        fields=['claim_id','company_id','year','report_id','page','text','type','esg_block','topic','metric','value','unit','base_year','target_year','has_number','has_deadline','prompt_version','model','source_url','quote_check','review_status']
        claims=[{'claim_id':f'{c}-2023-{i:03d}','company_id':c,'year':2023,'report_id':f'{c}-2023-ОУР','page':1,'text':'Другая подтверждённая цитата','type':'результат'}for c in ['AAAA','BBBB']for i in range(1,301)]
        (pipeline/'data/out/claims.csv').write_bytes(csv_bytes(claims,fields))
        reviews=[]
        for c in ['AAAA','BBBB']:
            reviews.append({'company_id':c,'report_ids_checked':[f'{c}-2023-ОУР',f'{c}-2025-ОУР'],'reporting_quality':{'classification':'неопределена'},'targets':[]})
        reviews[0]['targets']=[{'target_id':'T-AAAA-001','metric':'выбросы','unit':'тонн','esg_block':'E','target_year':2025,'target_value':10,'direction':'down','target_evidence':{'report_id':'AAAA-2023-ОУР','page':2 if bad_quote else 1,'quote':'снизить выбросы до 10 тонн к 2025 году'},'observations':[{'year':2025,'value':9,'report_id':'AAAA-2025-ОУР','page':1,'quote':'В 2025 году выбросы составили 9 тонн.'}]}]
        input_path=pipeline/'llm/nikita_dynamics/v1/group_A.json';input_path.write_text(json.dumps({'company_reviews':reviews},ensure_ascii=False))
        return pipeline,repo,input_path

    def test_builder_links_actual_companion_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as d:
            pipeline,repo,inp=self.fixture(Path(d));before=(pipeline/'data/out/claims.csv').read_bytes()
            tables,fields,validation=build(pipeline,repo,[inp]);self.assertEqual(validation['errors'],[])
            self.assertEqual(tables['targets.csv'][0]['claim_id_commitment'],'AAAA-2023-301')
            self.assertEqual(tables['claims_dynamics_additions.csv'][0]['claim_id'],'AAAA-2023-301')
            self.assertEqual(tables['metrics_dynamics.csv'][0]['status'],'выполнена')
            dest=Path(d)/'rebuilt';write_outputs(dest,tables,fields,validation)
            self.assertEqual((pipeline/'data/out/claims.csv').read_bytes(),before)
            self.assertEqual(sum(x['quota']for x in tables['sampling_quotas.csv']),500)
            write_outputs(dest,tables,fields,validation)
            bad=list(tables['targets.csv']);bad[0]=dict(bad[0],metric='changed');tables['targets.csv']=bad
            with self.assertRaises(FileExistsError):write_outputs(dest,tables,fields,validation)

    def test_primary_year_and_observation_unit_are_validated(self):
        with tempfile.TemporaryDirectory() as d:
            pipeline,repo,inp=self.fixture(Path(d))
            payload=json.loads(inp.read_text());target=payload['company_reviews'][0]['targets'][0]
            target['target_evidence']={'report_id':'AAAA-2025-ОУР','page':1,'quote':'В 2025 году выбросы составили 9 тонн.'}
            inp.write_text(json.dumps(payload,ensure_ascii=False))
            _,_,validation=build(pipeline,repo,[inp])
            self.assertTrue(any('2023' in x['error']for x in validation['errors']))
        with tempfile.TemporaryDirectory() as d:
            pipeline,repo,inp=self.fixture(Path(d))
            payload=json.loads(inp.read_text());payload['company_reviews'][0]['targets'][0]['observations'][0]['unit']='проценты'
            inp.write_text(json.dumps(payload,ensure_ascii=False))
            _,_,validation=build(pipeline,repo,[inp])
            self.assertTrue(any('unit differs' in x['error']for x in validation['errors']))

    def test_arithmetic_requires_proven_operands_and_cannot_execute_code(self):
        quotes='База 14 970 дней; снижение на 25% к 2025 году.'
        self.assertTrue(verify_calculation('14970*(1-0.25)=11227.5','11227.5',quotes))
        self.assertTrue(verify_calculation('14970*0.75=11227.5','11227.5','База 14970; целевая доля 75%'))
        self.assertFalse(verify_calculation('18700*(1-0.25)=14025','14025',quotes))
        self.assertFalse(verify_calculation('__import__(1)',1,quotes))
        self.assertFalse(verify_calculation('14970**2',224100900,quotes))
        self.assertTrue(has_number(5000000,'высадить5 млн деревьев'))
        self.assertFalse(has_number(5000000,'увеличить в5 раз'))
        self.assertEqual(derive_status({'target_year':2025,'target_value':50,'direction':'increase','operator':'>'},[{'year':2025,'value':50}]),'не выполнена')

    def test_retained_qa_override_prevents_false_fulfilment(self):
        with tempfile.TemporaryDirectory() as d:
            pipeline,repo,inp=self.fixture(Path(d))
            folder=pipeline/'data/nikita';folder.mkdir(parents=True)
            (folder/'overrides_v2.json').write_text(json.dumps({'targets':{'T-AAAA-001':{'set':{'comparison_valid':False},'reason':'different perimeter'}}}))
            tables,_,validation=build(pipeline,repo,[inp])
            self.assertFalse(validation['errors'])
            self.assertEqual(tables['metrics_dynamics.csv'][0]['status'],'нет данных')
            self.assertIn('different perimeter',tables['metrics_dynamics.csv'][0]['comment'])
            self.assertFalse('comparison_valid' in json.loads(inp.read_text())['company_reviews'][0]['targets'][0])

    def test_invalid_evidence_is_reported_and_blocks_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            pipeline,repo,inp=self.fixture(Path(d),bad_quote=True)
            tables,fields,validation=build(pipeline,repo,[inp]);self.assertTrue(validation['errors'])
            dest=Path(d)/'invalid'
            with self.assertRaises(ValueError):write_outputs(dest,tables,fields,validation)
            self.assertFalse((dest/'data/out/targets.csv').exists())
            self.assertTrue((dest/'data/nikita/validation.json').exists())

if __name__=='__main__':unittest.main()
