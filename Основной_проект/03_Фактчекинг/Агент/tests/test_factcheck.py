import copy
import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import factcheck as f


def response(plan):
    content = 'Synthetic independent measurement: emissions were 10 tonnes in 2023.'
    return {'schema_version': f.SCHEMA, 'source_sha256': plan['source_sha256'],
            'claim_id':'C000001', 'quote':plan['claims'][0]['quote'], 'revision':1,
            'reviewer':'synthetic-test-reviewer','checked_at':'2026-11-19T09:00:00+05:00',
            'research_status':'complete','verdict':'true','reason':'Synthetic fixture only',
            'target':{'proposition':'Emissions 10 tonnes','entity':'Test Co','period':'2023',
                      'boundary':'one plant','assessment_object':'reported_fact'},
            'source_review':{'status':'verified','method':'synthetic fixture','locator':'fixture:1'},
            'aspect_coverage_confirmed':True,'aspect_coverage_reason':'One numerical claim in fixture',
            'searches':[{'id':'q1','query':'synthetic supporting query','direction':'support','tool':'fixture',
                         'tool_ref':'fixture:q1','searched_at':'2026-11-19T08:00:00+05:00','status':'completed','source_ids':['s1'],'outcome_note':'synthetic hit'},
                        {'id':'q2','query':'synthetic opposing query','direction':'contradiction','tool':'fixture',
                         'tool_ref':'fixture:q2','searched_at':'2026-11-19T08:01:00+05:00','status':'completed','source_ids':[],'outcome_note':'synthetic zero hits'}],
            'sources':[{'id':'s1','url':'https://example.org/synthetic','publisher':'synthetic','origin_group':'independent lab',
                        'origin_basis':'synthetic independent measurement fixture','publication_date':'2024-01-01',
                        'event_period':'2023','locator':'fixture paragraph1','content':content,
                        'content_sha256':f.digest(content.encode()),'tool_ref':'fixture:open1',
                        'retrieved_at':'2026-11-19T08:02:00+05:00','access':'excerpt','independence':'independent'}],
            'evidence':[{'id':'e1','source_id':'s1','quote':'emissions were 10 tonnes in 2023.',
                         'relation':'supports','reason':'fixture measurement',
                         'alignment':{k:{'status':'matched','reason':'synthetic exact match'} for k in f.AXES}}],
            'aspects':[{'id':'a1','proposition':'10 tonnes','status':'supported','evidence_ids':['e1'],'reason':'fixture'}]}


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.run=self.root/'run'
        src=self.root/'input.json';src.write_text(json.dumps({'claims':[{'id':'original','page':1,'quote':'Emissions 10 tonnes','block':'E'}, {'quote':'Pending second claim','block':''}]}))
        f.prepare(src,self.run);self.plan=f.load(self.run);self.p=response(self.plan)
    def tearDown(self): self.tmp.cleanup()
    def ingest(self,p=None):
        path=self.root/'response.json';path.write_text(json.dumps(p or self.p));return f.ingest(self.run,path)
    def bad(self,mutator):
        mutator(self.p)
        with self.assertRaises((ValueError,TypeError)): f.validate(self.p,self.plan)
    def test_resume_and_csv_readback(self):
        self.ingest();self.assertEqual(len(f.queue(self.run)),1)
        with self.assertRaises(ValueError):f.export(self.run,self.root/'out')
        r=f.export(self.run,self.root/'out',True);self.assertEqual(r['unfinished'],1)
        import csv
        with (Path(r['output'])/'claims.csv').open(encoding='utf-8-sig') as file:
            rows=list(csv.DictReader(file,delimiter=';'))
        self.assertEqual(rows[1]['verdict'],'not_researched');self.assertEqual(rows[0]['quote'],'Emissions 10 tonnes')
    def test_revisions(self):
        self.ingest()
        with self.assertRaises(ValueError):self.ingest()
        self.p['revision']=2;self.ingest();self.assertEqual(len(list((self.run/'results').glob('*.json'))),2)
    def test_mixed_aspects_partial_and_complete_export(self):
        e=copy.deepcopy(self.p['evidence'][0]);e.update(id='e2',relation='contradicts')
        self.p['evidence'].append(e)
        self.p['aspects'].append({'id':'a2','proposition':'Second aspect','status':'contradicted','evidence_ids':['e2'],'reason':'fixture'})
        self.p['verdict']='partial';self.ingest()
        p2=copy.deepcopy(self.p);p2.update(claim_id='C000002',quote='Pending second claim',verdict='not_verifiable')
        p2['target']['assessment_object']='principle'
        p2['aspects']=[{'id':'a1','proposition':'not operationalized','status':'unresolved','evidence_ids':['e1','e2'],'reason':'fixture'}]
        self.ingest(p2)
        result=f.export(self.run,self.root/'complete')
        self.assertEqual(result['status'],'research_complete')
        self.assertEqual(result['verdict_counts']['partial'],1)
    def test_false_with_contradicting_evidence(self):
        self.p['evidence'][0]['relation']='contradicts'
        self.p['aspects'][0]['status']='contradicted';self.p['verdict']='false'
        f.validate(self.p,self.plan)
    def test_blocked_opposing_query_is_not_completed(self):
        self.bad(lambda p:p['searches'][1].update(status='blocked'))
    def test_forged_quote(self):self.bad(lambda p:p['evidence'][0].update(quote='9 tonnes'))
    def test_wrong_entity(self):self.bad(lambda p:p['evidence'][0]['alignment']['entity'].update(status='mismatch'))
    def test_issuer_republication(self):self.bad(lambda p:p['sources'][0].update(independence='issuer_republication'))
    def test_snippet(self):self.bad(lambda p:p['sources'][0].update(access='snippet'))
    def test_missing_search_direction(self):self.bad(lambda p:p['searches'].pop())
    def test_unknown_evidence(self):self.bad(lambda p:p['aspects'][0]['evidence_ids'].append('missing'))
    def test_unresolved_cannot_partial(self):
        self.p['aspects'].append({'id':'a2','proposition':'Other part','status':'unresolved','evidence_ids':[],'reason':'not found'})
        self.bad(lambda p:p.update(verdict='partial'))
    def test_insufficient_requires_search(self):
        self.p['aspects'][0]['status']='unresolved';self.p['verdict']='insufficient_evidence'
        f.validate(self.p,self.plan)
        self.bad(lambda p:p.update(research_status='blocked'))
    def test_blocked_not_insufficient(self):
        self.p.update(sources=[],evidence=[],searches=[],research_status='blocked',verdict='not_verifiable')
        self.p['aspects'][0].update(status='unresolved',evidence_ids=[])
        self.ingest();self.assertEqual(len(f.queue(self.run)),2)
    def test_future_promise(self):
        self.p['target'].update(assessment_object='promise_fulfillment',due_date='2030-01-01',deadline_basis='fixture')
        self.bad(lambda p:None)
        self.p['verdict']='not_due';f.validate(self.p,self.plan)
    def test_source_review(self):self.bad(lambda p:p.pop('source_review'))
    def test_changed_input(self):
        (self.run/'input.json').write_text('{}')
        with self.assertRaises(ValueError):f.load(self.run)
    def test_changed_prompt(self):
        (self.run/'prompt.md').write_text('changed')
        with self.assertRaises(ValueError):f.load(self.run)
    def test_checkpoint_tampering(self):
        self.ingest();path=next((self.run/'results').glob('*.json'));path.write_text('{}')
        with self.assertRaises(ValueError):f.queue(self.run)
    def test_conflict_requires_resolution(self):
        e=copy.deepcopy(self.p['evidence'][0]);e.update(id='e2',relation='contradicts');self.p['evidence'].append(e)
        self.p['aspects'][0]['evidence_ids'].append('e2');self.bad(lambda p:None)
    def test_missing_publication_metadata(self):self.bad(lambda p:p['sources'][0].pop('publication_date'))
    def test_unknown_claim(self):self.bad(lambda p:p.update(claim_id='C999999'))
    def test_false_must_have_contradiction(self):self.bad(lambda p:p.update(verdict='false'))

if __name__=='__main__':unittest.main()
