import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from extract_claims import validate,display_quote,merge_parts


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.report = Path(self.tmp.name) / 'report.md'
        self.report.write_text('<!-- pdf_page: 1 --><!-- source_text_begin -->Мы установили\nочистные сооружения. Планируем снизить выбросы.<!-- source_text_end --><!-- pdf_page: 2 --><!-- source_text_begin -->Забота о природе — наш приоритет.<!-- source_text_end -->')
        self.data = {'source_sha256':hashlib.sha256(self.report.read_bytes()).hexdigest(),'pages_reviewed':[1,2],'claims':[{'page':1,'type':'результат','quote':'Мы установили очистные сооружения.','reason':'Завершённое действие'}]}

    def test_whitespace_only_normalization(self):
        self.assertEqual(len(validate(self.report,self.data)[2]),1)

    def test_wrong_quote_rejected(self):
        self.data['claims'][0]['quote']='Мы установили три очистных сооружения.'
        with self.assertRaises(ValueError):validate(self.report,self.data)

    def test_wrong_page_rejected(self):
        self.data['claims'][0]['page']=2
        with self.assertRaises(ValueError):validate(self.report,self.data)

    def test_missing_page_rejected(self):
        self.data['pages_reviewed']=[1]
        with self.assertRaises(ValueError):validate(self.report,self.data)

    def test_changed_source_rejected(self):
        self.data['source_sha256']='wrong'
        with self.assertRaises(ValueError):validate(self.report,self.data)

    def test_duplicate_rejected(self):
        self.data['claims'].append(copy.deepcopy(self.data['claims'][0]))
        with self.assertRaises(ValueError):validate(self.report,self.data)

    def test_verdict_not_allowed_as_type(self):
        self.data['claims'][0]['type']='подтверждено'
        with self.assertRaises(ValueError):validate(self.report,self.data)

    def test_page_boundary_checks_each_segment(self):
        c=self.data['claims'][0]
        c['segments']=[{'page':1,'quote':'Планируем снизить выбросы.'},{'page':2,'quote':'Забота о природе — наш приоритет.'}]
        c['quote']=' '.join(s['quote'] for s in c['segments'])
        self.assertEqual(len(validate(self.report,self.data)[2]),1)
        c['segments'][1]['quote']='Придуманное продолжение.'
        with self.assertRaises(ValueError):validate(self.report,self.data)

    def test_unresolved_review_rejected(self):
        self.data['claims'][0]['needs_source_review']=True
        with self.assertRaises(ValueError):validate(self.report,self.data)

    def test_context_checked_against_its_source_page(self):
        c=self.data['claims'][0]
        c['display_context']='Забота о природе — наш приоритет.'
        c['context_page']=2
        validate(self.report,self.data)
        c['context_page']=1
        with self.assertRaises(ValueError):validate(self.report,self.data)

    def test_units_preserved_when_removing_markup(self):
        self.assertEqual(display_quote('**1 млн м<sup>3</sup> CO<sub>2</sub>**',''),'1 млн м³ CO₂')

    def parts(self):
        first = copy.deepcopy(self.data)
        first['pages_reviewed'] = [1]
        second = copy.deepcopy(self.data)
        second.update(pages_reviewed=[2], claims=[], excluded_notes=['Нет новых заявлений'])
        paths = []
        for i, part in enumerate((first, second)):
            path = Path(self.tmp.name) / f'part{i}.json'
            path.write_text(json.dumps(part))
            paths.append(path)
        return paths

    def test_merge_allows_empty_page_batch_and_sorts(self):
        merged = merge_parts(self.report, self.parts()[::-1])
        self.assertEqual(merged['pages_reviewed'], [1, 2])
        self.assertEqual(merged['claims'], self.data['claims'])
        self.assertEqual(merged['excluded_notes'], ['Нет новых заявлений'])

    def test_merge_rejects_missing_batch(self):
        with self.assertRaisesRegex(ValueError, 'Не обработаны'):
            merge_parts(self.report, self.parts()[:1])

    def test_merge_rejects_overlap(self):
        paths = self.parts()
        with self.assertRaisesRegex(ValueError, 'повторно'):
            merge_parts(self.report, paths + paths[:1])

    def test_merge_rejects_stale_hash(self):
        paths = self.parts()
        data = json.loads(paths[1].read_text())
        data['source_sha256'] = 'stale'
        paths[1].write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'хеш'):
            merge_parts(self.report, paths)

    def test_merge_rejects_claim_outside_batch(self):
        paths = self.parts()
        data = json.loads(paths[0].read_text())
        data['claims'][0]['page'] = 2
        paths[0].write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'вне просмотренных'):
            merge_parts(self.report, paths)

    def test_merge_validates_quotes(self):
        paths = self.parts()
        data = json.loads(paths[0].read_text())
        data['claims'][0]['quote'] = 'Выдуманная цитата'
        paths[0].write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'цитата отсутствует'):
            merge_parts(self.report, paths)


if __name__=='__main__':unittest.main()
