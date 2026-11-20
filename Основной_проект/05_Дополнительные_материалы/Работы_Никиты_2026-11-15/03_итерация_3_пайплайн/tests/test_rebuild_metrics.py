import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from run_extract import metrics_equal

class MetricComparisonTests(unittest.TestCase):
 def test_float_roundoff_only(self):
  self.assertTrue(metrics_equal({'f1':0.8301741835767701,'n':305},{'f1':0.8301741835767699,'n':305}))
  self.assertFalse(metrics_equal({'f1':0.831,'n':305},{'f1':0.830,'n':305}))
  self.assertFalse(metrics_equal({'f1':0.830,'n':304},{'f1':0.830,'n':305}))
  self.assertFalse(metrics_equal({'f1':float('nan')},{'f1':0.830}))
 def test_structure_and_types_remain_exact(self):
  self.assertFalse(metrics_equal({'n':305.0},{'n':305}))
  self.assertFalse(metrics_equal({'n':305,'extra':1},{'n':305}))
  self.assertFalse(metrics_equal([0.8],[0.8,0.9]))
