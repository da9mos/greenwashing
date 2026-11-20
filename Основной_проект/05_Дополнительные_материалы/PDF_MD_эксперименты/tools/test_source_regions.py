import unittest
from source_regions import region_boxes,block_coverage,duplicate_paragraphs
class CoverageTests(unittest.TestCase):
    def test_regions_cover_edges_corners_and_center(self):
        boxes=region_boxes(600,900);self.assertEqual(len(boxes),4)
        for x in range(0,601,10):
            for y in range(0,901,10):self.assertTrue(any(a<=x<=c and b<=y<=d for _,(a,b,c,d) in boxes),(x,y))
    def test_absent_body_is_flagged_despite_nonempty_markdown(self):
        source=[{'source_id':'right','bbox':[300,0,600,900],'text':'Водозабор за 2022 2023 2024 составил 3716,01 4432,21 4545,37 миллионов кубических метров'}]
        self.assertEqual(block_coverage(source,'Короткий заголовок')[0]['state'],'possible_omission')
    def test_source_font_uncertainty_not_called_model_error(self):
        self.assertEqual(block_coverage([{'text':'\ue012 Контроль'}],'Контроль')[0]['state'],'source_text_uncertain')
    def test_verbatim_content_with_reordered_words_is_not_semantically_certified(self):
        r=block_coverage([{'text':'Значения за 2022 2023 составили 12,5 14,6 миллионов тонн'}],'14,6 12,5 тонн миллионов составили 2023 2022 за Значения')[0]
        self.assertEqual(r['state'],'no_large_omission_detected');self.assertIn('not proof',r['scope'])
    def test_duplicate_paragraph_not_declared_legitimate_from_repeated_title(self):
        text='Исходный большой абзац с количеством воды и подтверждённым периодом измерения. Он должен присутствовать в выдаче один раз вместе с единицами и примечанием.'
        self.assertEqual(len(duplicate_paragraphs([{'text':text}],text+'\n\n'+text)),1)
if __name__=='__main__':unittest.main()
