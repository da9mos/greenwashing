"""Year grouping and literal quote guards; no live research is represented by these fixtures."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('annual_export',Path(__file__).with_name('prepare_company_export.py'))
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)

class AnnualExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.source=self.root/'unit.md';self.source.write_text('<!-- pdf_page: 1 -->\nВ ре-\nзультате проверки нарушений нет.\n\n**Форма собственности**\nСуммарная доля превышает 50 %.\n')
        self.report={'report_id':'UNIT','company_id':'GAZP','company':'Газпром','year':'2023','report_type':'ОУР','physical_pages':1,'repository_path':str(self.source),'packaged_md_sha256':hashlib.sha256(self.source.read_bytes()).hexdigest(),'pdf_source_url':'https://example.org/UNIT-FIXTURE'}
        self.record={'id':'C000001','quote':'аналитическая склейка','original':{'statement':'аналитическая склейка','type':'результат','block':'G','pdf_page':1},'research_status':'complete','assessment':{'verdict':'insufficient_evidence','short_reason':'Синтетический источник: данных о проверке нет.','sources':[]},'presentation':{'exact_quote':'В ре-\nзультате проверки нарушений нет.','pages':[1],'source_md_sha256':self.report['packaged_md_sha256'],'verified':True}}
        fixture=Path(__file__).resolve().parents[1]/'03_Фактчекинг/Агент/examples/synthetic_response.json'
        assessment=json.loads(fixture.read_text())
        assessment.update(quote=self.record['quote'],claim_id=self.record['id'],verdict='insufficient_evidence',short_reason='Синтетический источник: данных о проверке нет.')
        assessment['aspects'][0]['status']='unresolved'
        self.record['assessment']=assessment


    def test_display_uses_whole_literal_quote_instead_of_analytical_statement(self):
        e.verify_presentation(self.record,self.report)
        row=e.display(self.record,self.report,1,require_presentation=True)
        self.assertEqual(row[1],self.record['presentation']['exact_quote']);self.assertEqual(row[4],'Не установлено')
        self.assertNotIn('Исследовано:',row[4]);self.assertNotIn('журнал',row[5])

    def test_fragment_beginning_inside_wrapped_word_is_rejected(self):
        self.record['presentation']['exact_quote']='зультате проверки нарушений нет.'
        with self.assertRaises(ValueError):e.verify_presentation(self.record,self.report)

    def test_disjoint_fragments_are_not_accepted_as_a_citation(self):
        self.record['presentation']['exact_quote']='В ре-\nзультате проверки доля превышает 50 %.'
        with self.assertRaises(ValueError):e.verify_presentation(self.record,self.report)

    def test_only_documented_markdown_formatting_can_be_removed(self):
        p=self.record['presentation'];p.update(raw_md_quote='**Форма собственности**\nСуммарная доля превышает 50 %.',exact_quote='Форма собственности\nСуммарная доля превышает 50 %.',formatting_only_transform=['remove_markdown_bold'])
        e.verify_presentation(self.record,self.report)
        p['exact_quote']=p['exact_quote'].replace('50 %','51 %')
        with self.assertRaises(ValueError):e.verify_presentation(self.record,self.report)

    def test_old_atomized_statement_is_not_silently_promoted_to_display(self):
        self.record.pop('presentation')
        with self.assertRaises(ValueError):e.display(self.record,self.report,1,require_presentation=True)

    def test_true_on_one_atom_cannot_label_a_larger_unchecked_context(self):
        self.record['assessment']['verdict']='true'
        self.record['assessment']['aspects'][0]['status']='supported'
        with self.assertRaisesRegex(ValueError,'every material assertion'):
            e.display(self.record,self.report,1,require_presentation=True)
        self.record['presentation']['assessed_quote_complete']=True
        self.assertEqual(e.display(self.record,self.report,1,require_presentation=True)[4],'Правда')

    def test_old_completed_research_without_regulatory_checks_cannot_be_final(self):
        self.record['assessment'].pop('risk_checks')
        with self.assertRaisesRegex(ValueError,'risk_checks required'):
            e.display(self.record,self.report,1,require_presentation=True)

    def test_process_boilerplate_is_rejected(self):
        self.record['assessment']['short_reason']='Оба направления поиска сохранены в журнале.'
        with self.assertRaises(ValueError):e.display(self.record,self.report,1,require_presentation=True)

    def test_two_reports_of_one_year_share_one_tab_with_continuous_numbering(self):
        reports=[dict(self.report,report_id='UNIT-2023-ОУР'),dict(self.report,report_id='UNIT-2023-ЭО',report_type='ЭО'),dict(self.report,report_id='UNIT-2024-ОУР',year='2024'),dict(self.report,report_id='UNIT-2025-ОУР',year='2025')]
        exports=self.root/'exports';exports.mkdir()
        for r in reports:
            d=exports/r['report_id'];d.mkdir();(d/'claims.json').write_text(json.dumps({'claims':[self.record]}));(d/'summary.json').write_text(json.dumps({'total':1,'status':'research_complete','report_id':r['report_id'],'md_sha256':r['packaged_md_sha256'],'extraction_coverage_complete':True}))
        original_read=e.read
        with patch.object(e,'read',side_effect=lambda path:reports if path.name=='manifest.json' else original_read(path)):
            data=e.prepare('GAZP',exports,False)
        self.assertEqual([s['title'] for s in data['sheets']],['2023','2024','2025'])
        self.assertEqual([row[0] for row in data['sheets'][0]['rows']],[1,2])
        self.assertEqual([len(s['rows']) for s in data['sheets']],[2,1,1]);self.assertEqual(data['layout'],'annual')
