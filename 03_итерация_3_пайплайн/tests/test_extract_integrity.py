import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import extract_integrity

class IntegrityTests(unittest.TestCase):
 def test_changed_answer_and_missing_source_fail(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'runs').mkdir();source=root/'answer.jsonl';source.write_text('original')
   freeze={'files':{'answer.jsonl':hashlib.sha256(source.read_bytes()).hexdigest()}}
   (root/'runs/extract_v1_freeze.json').write_text(json.dumps(freeze))
   with patch.object(extract_integrity,'ROOT',root):
    self.assertEqual(extract_integrity.verify(),freeze)
    source.write_text('altered')
    with self.assertRaisesRegex(ValueError,'changed or missing'):extract_integrity.verify()
    source.unlink()
    with self.assertRaisesRegex(ValueError,'changed or missing'):extract_integrity.verify()

if __name__=='__main__':unittest.main()
