"""Required enforcement/court/incident searches; explicit synthetic fixtures, no network."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import factcheck as f
from test_factcheck import response


class RiskCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name); source = root/'input.json'
        source.write_text(json.dumps({'claims':[{'quote':'Emissions 10 tonnes','block':'E'}]}))
        f.prepare(source,root/'run'); self.plan=f.load(root/'run'); self.packet=response(self.plan)

    def test_new_plan_requires_all_four_categories(self):
        self.assertEqual(set(self.plan['required_risk_categories']),set(f.RISK_CATEGORIES))
        f.validate(self.packet,self.plan)

    def test_missing_category_cannot_complete(self):
        self.packet['risk_checks'].pop()
        with self.assertRaisesRegex(ValueError,'each required risk category'): f.validate(self.packet,self.plan)

    def test_direction_searches_alone_cannot_claim_risk_checks(self):
        self.packet.pop('risk_checks')
        with self.assertRaisesRegex(ValueError,'risk_checks required'): f.validate(self.packet,self.plan)

    def test_invented_search_index_rejected(self):
        self.packet['risk_checks'][0]['search_indexes']=[99]
        with self.assertRaisesRegex(ValueError,'real search indexes'): f.validate(self.packet,self.plan)

    def test_one_untyped_search_cannot_cover_all_categories(self):
        self.packet['risk_checks'][0]['search_indexes']=[1]
        with self.assertRaisesRegex(ValueError,'category mismatch'): f.validate(self.packet,self.plan)

    def test_blocked_category_prevents_complete(self):
        self.packet['searches'][2]['status']='blocked'
        with self.assertRaisesRegex(ValueError,'completed search for each'): f.validate(self.packet,self.plan)

    def test_blocked_tool_is_saved_as_unfinished_without_fake_searches(self):
        self.packet.update(research_status='blocked',verdict='not_verifiable',sources=[],searches=[],evidence=[])
        self.packet['aspects'][0].update(status='unresolved',evidence_ids=[])
        for check in self.packet['risk_checks']:
            check.update(search_indexes=[],finding='Synthetic search-tool unavailable fixture')
        f.validate(self.packet,self.plan)

    def test_legacy_snapshot_stays_valid_without_new_policy(self):
        self.plan.pop('required_risk_categories');self.packet.pop('risk_checks')
        f.validate(self.packet,self.plan)
        self.packet['risk_checks']=[{'category':'court_cases','search_indexes':[999]}]
        with self.assertRaises(ValueError):f.validate(self.packet,self.plan)
