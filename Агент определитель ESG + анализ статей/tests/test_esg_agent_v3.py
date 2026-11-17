import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('v3',Path(__file__).resolve().parents[1]/'scripts/esg_agent_v3.py')
v3=importlib.util.module_from_spec(spec);spec.loader.exec_module(v3)

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.src=self.root/'r.md';self.src.write_text('<!-- pdf_page: 1 -->\nДа.\n\n| Год | т |\n|---|---|\n| 2024 | 0 |\n<!-- pdf_page: 2 -->\nПланируем сократить выбросы.\n')
        self.prompt=self.root/'prompt.md';self.prompt.write_text('Read all')
        self.tax=self.root/'tax.csv';self.tax.write_text('block;topic\nE;климат\nS;персонал\nG;этика\n')
        self.work=self.root/'work';self.man=v3.prepare(self.src,self.work,'TEST-2024',self.prompt,self.tax,1)
    def responses(self):
        result=[]
        for b in self.man['batches']:
            batch=v3.read(self.work/b['file'])
            result.append({'schema_version':v3.VERSION,'source_sha256':self.man['source_sha256'],'batch_id':b['id'],'reviewer':'test model','claims':[],'coverage':[{'block_id':bid,'status':'excluded','reason':'Synthetic test exclusion','claim_ids':[]} for bid in batch['target_block_ids']]})
        return result
    def claim(self,d):
        batch=v3.read(self.work/next(b['file'] for b in self.man['batches'] if b['id']==d['batch_id']))
        b=next(b for b in batch['blocks'] if b['id']==batch['target_block_ids'][0])
        c={'id':'c1','type':'результат','block':'E','topic':'климат','block2':'','statement':b['text'],'source_kind':'text','source_status':'md_only','reason':'Test','evidence':[{'block_id':b['id'],'quote':b['text'],'role':'statement'}],'quantitative':False,'metric':'','value':'','unit':'','period':'','entity_scope':''}
        d['claims']=[c];d['coverage'][0].update(status='extracted',claim_ids=['c1']);return c
    def files(self,ds):
        paths=[]
        for i,d in enumerate(ds):
            p=self.root/f'response{i}.json';v3.write(p,d);paths.append(p)
        return paths
    def test_short_and_table_preserved_exact(self):
        pages,_=v3.load_pages(self.src);blocks=v3.read(self.work/'blocks.json')
        self.assertEqual(blocks[0]['text'],'Да.')
        self.assertIn('| 2024 | 0 |',blocks[1]['text'])
        for b in blocks:self.assertEqual(next(p['text'] for p in pages if p['page']==b['page'])[b['start']:b['end']],b['text'])
    def test_duplicate_md_marker_rejected(self):
        self.src.write_text('<!-- pdf_page: 1 -->X<!-- pdf_page: 1 -->Y')
        with self.assertRaises(ValueError):v3.load_pages(self.src)
    def test_pdf_rejected(self):
        p=self.root/'r.pdf';p.write_bytes(b'%PDF')
        with self.assertRaises(ValueError):v3.load_pages(p)
    def test_txt_has_no_physical_claim(self):
        p=self.root/'r.txt';p.write_text('1\f2');pages,kind=v3.load_pages(p)
        self.assertEqual(len(pages),2);self.assertIn('not_physical',kind)
    def test_no_truncation(self):
        p=self.root/'long.txt';s='а'*10000;p.write_text(s)
        blocks=v3.blocks_for(v3.load_pages(p)[0],'LONG');self.assertEqual(blocks[0]['text'],s)
    def test_missing_block(self):
        d=self.responses()[0];d['coverage'].pop()
        with self.assertRaises(ValueError):v3.check(self.work,d)
    def test_wrong_quote(self):
        d=self.responses()[0];c=self.claim(d);c['evidence'][0]['quote']='Нет.'
        with self.assertRaises(ValueError):v3.check(self.work,d)
    def test_statement_not_rewritten(self):
        d=self.responses()[0];c=self.claim(d);c['statement']='Утверждаем: да.'
        with self.assertRaises(ValueError):v3.check(self.work,d)
    def test_changed_source(self):
        self.src.write_text(self.src.read_text()+' ')
        with self.assertRaises(ValueError):v3.workspace(self.work)
    def test_changed_prompt(self):
        self.prompt.write_text('Changed')
        with self.assertRaises(ValueError):v3.workspace(self.work)
    def test_changed_taxonomy(self):
        self.tax.write_text('Changed')
        with self.assertRaises(ValueError):v3.workspace(self.work)
    def test_changed_manifest(self):
        m=v3.read(self.work/'manifest.json');m['report_id']='OTHER';v3.write(self.work/'manifest.json',m)
        with self.assertRaises(ValueError):v3.workspace(self.work)
    def test_missing_batch(self):
        paths=self.files(self.responses()[:1])
        with self.assertRaises(ValueError):v3.export(self.work,paths,self.root/'out')
    def test_duplicate_batch(self):
        paths=self.files(self.responses())
        with self.assertRaises(ValueError):v3.export(self.work,paths+paths[:1],self.root/'out')
    def test_quant_context_unknown_requires_review(self):
        d=self.responses()[0];c=self.claim(d);c['quantitative']=True
        with self.assertRaises(ValueError):v3.check(self.work,d)
        c['source_status']='needs_pdf_review';_,stats=v3.check(self.work,d);self.assertEqual(stats['pending_claims'],1)
    def test_partial_denied_and_draft_preserved(self):
        ds=self.responses();ds[0]['coverage'][0]['status']='pending';paths=self.files(ds)
        with self.assertRaises(ValueError):v3.export(self.work,paths,self.root/'out')
        out,stats=v3.export(self.work,paths,self.root/'out',True)
        self.assertEqual(out.name,'out_draft');self.assertEqual(stats['status'],'partial')
    def test_neighbor_evidence_allowed_owner_only(self):
        d=self.responses()[0];c=self.claim(d)
        batch=v3.read(self.work/self.man['batches'][0]['file']);neighbor=next(b for b in batch['blocks'] if b['page']==2)
        c['evidence'].append({'block_id':neighbor['id'],'quote':neighbor['text'],'role':'context'})
        v3.check(self.work,d)
        d['coverage'].append({'block_id':neighbor['id'],'status':'excluded','reason':'bad','claim_ids':[]})
        with self.assertRaises(ValueError):v3.check(self.work,d)
    def test_page_gap_rejected(self):
        self.src.write_text('<!-- pdf_page: 1 -->A<!-- pdf_page: 3 -->B')
        with self.assertRaises(ValueError):v3.load_pages(self.src)
    def test_jsonl_page_gap_rejected(self):
        p=self.root/'r.jsonl';p.write_text(json.dumps({'page':1,'text':'A'})+'\n'+json.dumps({'page':3,'text':'B'}))
        with self.assertRaises(ValueError):v3.load_pages(p)
    def test_numeric_must_be_string(self):
        d=self.responses()[0];c=self.claim(d);c.update(quantitative=True,value=0,source_status='needs_pdf_review')
        with self.assertRaises(ValueError):v3.check(self.work,d)
    def test_invented_number_even_pending_rejected(self):
        d=self.responses()[0];c=self.claim(d);c.update(quantitative=True,value='999',source_status='needs_pdf_review')
        c['evidence'].append({**c['evidence'][0],'role':'value'})
        with self.assertRaises(ValueError):v3.check(self.work,d)
    def test_context_only_cannot_own_neighbor_statement(self):
        d=self.responses()[0];c=self.claim(d);c['evidence'][0]['role']='context'
        batch=v3.read(self.work/self.man['batches'][0]['file']);neighbor=next(b for b in batch['blocks'] if b['page']==2)
        c['statement']=neighbor['text'];c['evidence'].append({'block_id':neighbor['id'],'quote':neighbor['text'],'role':'statement'})
        with self.assertRaises(ValueError):v3.check(self.work,d)
    def test_image_cannot_be_excluded(self):
        self.src.write_text('<!-- pdf_page: 1 -->![Chart](chart.png)')
        self.work=self.root/'images';self.man=v3.prepare(self.src,self.work,'TEST-2024',self.prompt,self.tax)
        d=self.responses()[0]
        with self.assertRaises(ValueError):v3.check(self.work,d)
        d['coverage'][0]['status']='pending';_,stats=v3.check(self.work,d);self.assertEqual(stats['pending_blocks'],1)
    def test_quantitative_complete_context(self):
        self.src.write_text('<!-- pdf_page: 1 -->Компания; Выбросы; 100; тонн; 2024')
        self.work=self.root/'quant';self.man=v3.prepare(self.src,self.work,'TEST-2024',self.prompt,self.tax)
        d=self.responses()[0];c=self.claim(d)
        c.update(quantitative=True,metric='Выбросы',value='100',unit='тонн',period='2024',entity_scope='Компания')
        base=c['evidence'][0]
        for role,value in [('metric','Выбросы'),('value','100'),('unit','тонн'),('period','2024'),('subject','Компания')]:
            c['evidence'].append({'block_id':base['block_id'],'quote':value,'role':role})
        _,stats=v3.check(self.work,d);self.assertEqual(stats['pending_claims'],0)
        c['period']='2023'
        with self.assertRaises(ValueError):v3.check(self.work,d)
    def test_service_preamble_saved_exact(self):
        prefix='# Название\r\n\r\n> Служебная информация о переносе. Источник.\r\n>\r\n> Комментарии о страницах.\r\n\r\n'
        body='<!-- pdf_page: 1 -->\nТекст'
        self.src.write_bytes((prefix+body).encode('utf-8'));work=self.root/'preamble'
        m=v3.prepare(self.src,work,'TEST-2024',self.prompt,self.tax)
        self.assertEqual((work/'preamble.txt').read_bytes().decode('utf-8'),prefix)
        self.assertEqual(v3.read(work/'pages.json')[0]['text'],'\nТекст')
        self.assertIn('not_semantically_reviewed',m['preamble_status']);v3.workspace(work)
        (work/'preamble.txt').write_text('changed')
        with self.assertRaises(ValueError):v3.workspace(work)
    def test_arbitrary_preamble_rejected(self):
        self.src.write_text('Мы снизили выбросы.\n<!-- pdf_page: 1 -->Текст')
        with self.assertRaises(ValueError):v3.load_pages(self.src)
    def test_export_csv_roundtrip(self):
        ds=self.responses();self.claim(ds[0]);out,stats=v3.export(self.work,self.files(ds),self.root/'out')
        with (out/'claims.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f,delimiter=';'))
        self.assertEqual(rows[0]['statement'],'Да.');self.assertEqual(stats['claims'],1)
        self.assertEqual(v3.read(out/'claims.json')['claims'][0]['evidence'],ds[0]['claims'][0]['evidence'])

if __name__=='__main__':unittest.main()
