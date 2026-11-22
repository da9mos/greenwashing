import copy
import csv
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
import esg_agent_v3_1 as agent


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.src = self.root/'source.md'; self.src.write_text('<!-- pdf_page: 1 -->Мы снизили выбросы.\n\nОглавление')
        self.prompt = self.root/'prompt.md'; self.prompt.write_text('Read all')
        self.taxonomy = self.root/'taxonomy.csv'; self.taxonomy.write_text('block;topic\nE;климат\nS;персонал\n')
        self.rules = self.root/'rules.json'
        agent.base.write(self.rules, {'version':'3.1', 'sources':{'ESRS':{'url':'https://example.test/esrs'}, 'GRI':{'url':'https://example.test/gri'}}, 'inclusion_rules':{'I1':{'description':'Assertion'}}, 'classification_rules':{'E1':{'block':'E','description':'Climate','source_refs':['ESRS']}, 'S1':{'block':'S','description':'People','source_refs':['GRI']}}, 'exclusion_rules':{'X1':{'description':'Navigation'}}})
        self.work = self.root/'work'
        self.manifest = agent.prepare(self.src,self.work,'TEST-2024',self.prompt,self.taxonomy,self.rules)
        batch = agent.base.read(self.work/self.manifest['batches'][0]['file'])
        blocks = batch['blocks']
        self.data = {'schema_version':agent.base.VERSION,'source_sha256':self.manifest['source_sha256'],'batch_id':batch['batch_id'],'reviewer':'Test model', 'claims':[{'id':'c1','type':'результат','block':'E','topic':'климат','block2':'','statement':'Мы снизили выбросы.','source_kind':'text','source_status':'md_only','reason':'Action','quantitative':False,'evidence':[{'block_id':blocks[0]['id'],'quote':'Мы снизили выбросы.','role':'statement'}], 'decision':{'inclusion_rule':'I1','classification_rule':'E1','subject':'Мы','proposition':'Снизили выбросы','esg_object':'Выбросы','source_refs':['ESRS'],'classification_status':'resolved','secondary_blocks':[],'ambiguity_note':''}}], 'coverage':[{'block_id':blocks[0]['id'],'status':'extracted','reason':'Claim','claim_ids':['c1']},{'block_id':blocks[1]['id'],'status':'excluded','reason':'Navigation','claim_ids':[],'exclusion_rule':'X1'}]}
    def response(self):
        path=self.root/'response.json';agent.base.write(path,self.data);return path
    def decision(self):return self.data['claims'][0]['decision']
    def test_valid_trace(self):
        _,stats=agent.check(self.work,self.data);self.assertEqual(stats['pending_classifications'],0)
    def test_missing_decision(self):
        del self.data['claims'][0]['decision']
        with self.assertRaises(ValueError):agent.check(self.work,self.data)
    def test_invalid_inclusion(self):
        self.decision()['inclusion_rule']='NO'
        with self.assertRaises(ValueError):agent.check(self.work,self.data)
    def test_wrong_block_rule(self):
        self.decision().update(classification_rule='S1',source_refs=['GRI'])
        with self.assertRaises(ValueError):agent.check(self.work,self.data)
    def test_unknown_source(self):
        self.decision()['source_refs']=['ESRS','FAKE']
        with self.assertRaises(ValueError):agent.check(self.work,self.data)
    def test_rule_source_required(self):
        self.decision()['source_refs']=['GRI']
        with self.assertRaises(ValueError):agent.check(self.work,self.data)
    def test_empty_subject(self):
        self.decision()['subject']=' '
        with self.assertRaises(ValueError):agent.check(self.work,self.data)
    def test_policy_change(self):
        policy=agent.base.read(self.rules);policy['sources']['ESRS']['url']='changed';agent.base.write(self.rules,policy)
        with self.assertRaises(ValueError):agent.check(self.work,self.data)
    def test_exclusion_rule_required(self):
        del self.data['coverage'][1]['exclusion_rule']
        with self.assertRaises(ValueError):agent.check(self.work,self.data)
    def test_pending_needs_ambiguity_note(self):
        self.decision()['classification_status']='pending'
        with self.assertRaises(ValueError):agent.check(self.work,self.data)
    def test_pending_export_blocked_without_flag(self):
        self.decision().update(classification_status='pending',ambiguity_note='Two plausible topics')
        with self.assertRaises(ValueError):agent.export(self.work,[self.response()],self.root/'out')
        self.assertFalse((self.root/'out').exists())
    def test_model_inputs_omit_bibliography_and_export_restores_rule_refs(self):
        policy = agent.load_policy(self.rules)
        model_files = agent.write_model_inputs(self.root / 'model', self.manifest, policy)
        rules = agent.base.read(model_files['decision_rules'])
        self.assertNotIn('sources', rules)
        self.assertEqual(rules['classification_rules']['E1'], {'block': 'E', 'description': 'Climate'})
        self.assertNotIn('https://', Path(model_files['decision_rules']).read_text(encoding='utf-8'))
        self.decision().pop('source_refs')
        response = self.response()
        data, _ = agent.check(self.work, response)
        self.assertNotIn('source_refs', data['claims'][0]['decision'])
        out, _ = agent.export(self.work, [response], self.root / 'out')
        self.assertEqual(agent.base.read(out / 'claims.json')['claims'][0]['decision']['source_refs'], ['ESRS'])
        self.assertNotIn('source_refs', agent.base.read(response)['claims'][0]['decision'])
    def test_pending_preserved_in_draft_and_csv(self):
        self.decision().update(classification_status='pending',ambiguity_note='Two plausible topics')
        out,summary=agent.export(self.work,[self.response()],self.root/'out',True)
        self.assertEqual(out.name,'out_draft');self.assertEqual(summary['status'],'partial');self.assertEqual(summary['pending_classifications'],1)
        for filename in ('claims.csv','E.csv'):
            with (out/filename).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f,delimiter=';'))
            self.assertEqual(rows[0]['classification_status'],'pending');self.assertEqual(rows[0]['source_refs'],'ESRS');self.assertEqual(rows[0]['statement'],'Мы снизили выбросы.')
            self.assertEqual(rows[0]['report_id'], self.manifest['report_id'])
            self.assertEqual(agent.base.json.loads(rows[0]['evidence_json']), self.data['claims'][0]['evidence'])
        self.assertEqual(agent.base.read(out/'claims.json')['claims'][0]['decision'],self.decision())
    def test_all_three_topics_preserved(self):
        self.data['claims'][0]['block2']='S';self.decision()['secondary_blocks']=['S','G']
        out,summary=agent.export(self.work,[self.response()],self.root/'out')
        self.assertEqual(summary['secondary_counts'],{'E':0,'S':1,'G':1})
        self.assertEqual(summary['legacy_block2_counts'],{'E':0,'S':1,'G':0})
        with (out/'claims.csv').open(encoding='utf-8-sig',newline='') as f:row=next(csv.DictReader(f,delimiter=';'))
        self.assertEqual(row['secondary_blocks'],'S,G')
    def test_repeated_or_primary_secondary_rejected(self):
        for secondary in (['E'], ['S','S']):
            self.decision()['secondary_blocks']=secondary
            with self.assertRaises(ValueError):agent.check(self.work,self.data)
    def test_block2_must_match_first_secondary(self):
        self.decision()['secondary_blocks']=['G','S'];self.data['claims'][0]['block2']='S'
        with self.assertRaises(ValueError):agent.check(self.work,self.data)
    def test_no_mutation_of_responses(self):
        path=self.response();before=path.read_bytes();agent.export(self.work,[path],self.root/'out');self.assertEqual(path.read_bytes(),before)
    def test_old_workspace_not_accepted(self):
        work=self.root/'old';agent.base.prepare(self.src,work,'TEST-2024',self.prompt,self.taxonomy)
        with self.assertRaises(ValueError):agent.check(work,self.data)
    def test_unknown_policy_reference_before_prepare(self):
        policy=agent.base.read(self.rules);policy['classification_rules']['E1']['source_refs']=['BAD'];agent.base.write(self.rules,policy)
        out=self.root/'bad'
        with self.assertRaises(ValueError):agent.prepare(self.src,out,'TEST',self.prompt,self.taxonomy,self.rules)
        self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
