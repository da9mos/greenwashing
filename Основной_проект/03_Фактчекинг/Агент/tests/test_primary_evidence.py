"""Synthetic structural cases for competent primary evidence; no actual facts or searches."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import factcheck as f
from test_factcheck import response

class PrimaryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);src=root/'input.json'
        src.write_text(json.dumps({'claims':[{'quote':'Synthetic claim: State controls a majority.','source_url':'https://example.org/original-claim'}]}))
        f.prepare(src,root/'run');self.plan=f.load(root/'run');self.p=response(self.plan)
        self.p['target'].update(proposition='Synthetic majority control',assessment_object='reported_fact')
        self.s=self.p['sources'][0];self.s.update(independence='issuer',content='Synthetic shareholder register: State 60%, other owners 40%.',locator='synthetic registry row1')
        self.s['content_sha256']=f.digest(self.s['content'].encode())
        self.e=self.p['evidence'][0];self.e['quote']='State 60%, other owners 40%.'
        self.b={'kind':'authoritative_primary','claim_kind':'ownership','record_type':'ownership_disclosure',
                'competence':'Synthetic issuer records its registered shareholders',
                'why_sufficient':'Synthetic record explicitly lists the majority',
                'source_locator':self.s['locator'],'statement_scope':'Synthetic ownership only',
                'record_id':'SYNTHETIC REGISTER','source_url':self.s['url'],
                'reviewed_record':True,'not_circular':True}
        self.e['evidence_basis']=self.b

    def test_competent_issuer_ownership_record_does_not_require_a_news_duplicate(self):
        f.validate(self.p,self.plan);self.assertEqual(self.s['independence'],'issuer')

    def test_bare_issuer_assertion_is_not_automatically_authoritative(self):
        self.e.pop('evidence_basis')
        with self.assertRaisesRegex(ValueError,'competent primary'):f.validate(self.p,self.plan)

    def test_record_kind_must_fit_the_claim(self):
        self.b['record_type']='official_announcement'
        with self.assertRaisesRegex(ValueError,'record type'):f.validate(self.p,self.plan)

    def test_basis_requires_competence_and_specific_record(self):
        for key in ('competence','why_sufficient','source_locator','record_id'):
            with self.subTest(key=key):
                value=self.b.pop(key)
                with self.assertRaises(ValueError):f.validate(self.p,self.plan)
                self.b[key]=value

    def test_primary_snippet_still_cannot_decide_truth(self):
        self.s['access']='snippet'
        with self.assertRaisesRegex(ValueError,'non-snippet'):f.validate(self.p,self.plan)

    def test_basis_cannot_point_to_another_unread_source(self):
        self.b['source_url']='https://example.org/different'
        with self.assertRaisesRegex(ValueError,'another source'):f.validate(self.p,self.plan)

    def test_announcement_can_verify_promise_but_not_fulfillment(self):
        self.b.update(claim_kind='announced_commitment',record_type='official_announcement')
        self.p['target']['assessment_object']='promise_made';f.validate(self.p,self.plan)
        self.p['target']['assessment_object']='promise_fulfillment'
        with self.assertRaisesRegex(ValueError,'not its fulfillment'):f.validate(self.p,self.plan)

    def test_underlying_quantity_cannot_repeat_the_original_quote_or_document(self):
        self.b.update(claim_kind='disclosed_quantity',record_type='accounting_record')
        f.validate(self.p,self.plan)
        self.e['quote']=self.p['quote'];self.s['content']=self.e['quote'];self.s['content_sha256']=f.digest(self.s['content'].encode())
        with self.assertRaisesRegex(ValueError,'repeating the original'):f.validate(self.p,self.plan)
        self.e['quote']='Synthetic different table: 60';self.s['content']=self.e['quote'];self.s['content_sha256']=f.digest(self.s['content'].encode())
        self.s['url']='https://example.org/original-claim';self.b['source_url']=self.s['url']
        with self.assertRaisesRegex(ValueError,'distinct underlying'):f.validate(self.p,self.plan)

    def test_a_policy_verifies_only_a_documented_principle(self):
        self.b.update(claim_kind='declared_policy',record_type='approved_policy')
        self.p['target'].update(assessment_object='principle',principle_test='documented_policy')
        f.validate(self.p,self.plan)
        self.p['target']['principle_test']='all_operations_are_harmless'
        with self.assertRaisesRegex(ValueError,'not its universal'):f.validate(self.p,self.plan)

    def test_primary_positive_record_does_not_hide_independent_contradiction(self):
        source=copy.deepcopy(self.s);source.update(id='s2',url='https://example.org/synthetic-contradiction',independence='independent',content='Synthetic contradictory register: State 40%.')
        source['content_sha256']=f.digest(source['content'].encode());self.p['sources'].append(source)
        other=copy.deepcopy(self.e);other.pop('evidence_basis');other.update(id='e2',source_id='s2',quote='State 40%.',relation='contradicts')
        self.p['evidence'].append(other);self.p['searches'][1]['source_ids']=['s2'];self.p['aspects'][0]['evidence_ids'].append('e2')
        with self.assertRaisesRegex(ValueError,'conflicting evidence'):f.validate(self.p,self.plan)
