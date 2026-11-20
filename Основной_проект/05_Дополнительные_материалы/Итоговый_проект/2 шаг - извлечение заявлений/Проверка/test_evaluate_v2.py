import unittest
from evaluate_v2 import evaluate

class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.data={'human_gold_complete':True,'gold':[{'id':'g1','type':'результат','primary_topic':'E'},{'id':'g2','type':'декларация','primary_topic':'S'}],'predicted':[{'id':'p1','type':'результат','primary_topic':'E'}],'adjudicated_matches':[['g1','p1']]}
    def test_missed_claim_counts_against_recall(self):
        r=evaluate(self.data)
        self.assertEqual(r['recall'],.5)
        self.assertEqual(r['precision'],1)
        self.assertEqual(r['end_to_end_recall'],.5)
    def test_model_only_gold_rejected(self):
        self.data['human_gold_complete']=False
        with self.assertRaises(ValueError):evaluate(self.data)
    def test_duplicate_match_rejected(self):
        self.data['adjudicated_matches'].append(['g2','p1'])
        with self.assertRaises(ValueError):evaluate(self.data)
    def test_wrong_topic_reduces_end_to_end(self):
        self.data['predicted'][0]['primary_topic']='G'
        r=evaluate(self.data)
        self.assertEqual(r['recall'],.5)
        self.assertEqual(r['end_to_end_recall'],0)

if __name__=='__main__':unittest.main()
