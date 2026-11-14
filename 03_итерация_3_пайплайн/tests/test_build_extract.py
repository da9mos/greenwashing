import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SRC=Path(__file__).resolve().parents[1]/'src'
sys.path.insert(0,str(SRC))
from prepare_extract import read_records
from build_extract import validate,norm

class BuildTests(unittest.TestCase):
 def test_literal_newline_in_upstream_json_string_loses_no_rows(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'input.jsonl';p.write_text('{"id":1,"text":"a\nb"}\n{"id":2,"text":"c"}\n')
   rows=list(read_records(p))
   self.assertEqual([r['id'] for r in rows],[1,2]);self.assertEqual(rows[0]['text'],'a\nb')
 def test_corrupt_json_does_not_silently_skip(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'input.jsonl';p.write_text('{"id":1}\nBROKEN')
   with self.assertRaises(ValueError):list(read_records(p))
 def test_invalid_topic_or_deadline_fails(self):
  p=dict(sentence_id='s',is_claim='да',type='результат',esg_block='E',topic='вода',has_number='нет',has_deadline='',confidence='высокая')
  validate(p)
  with self.assertRaises(ValueError):validate(dict(p,topic='обучение'))
  with self.assertRaises(ValueError):validate(dict(p,has_deadline='нет'))
 def test_quote_normalization_does_not_rewrite_words(self):
  self.assertEqual(norm('Компания\n  снизила выбросы.'),'Компания снизила выбросы.')
  self.assertNotIn(norm('снизила выбросы'),norm('Компания увеличила выбросы.'))

if __name__=='__main__':unittest.main()
