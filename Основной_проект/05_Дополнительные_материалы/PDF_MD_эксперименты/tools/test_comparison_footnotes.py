import unittest
from compare_results import cleaned_text,compare_decimals_to_spans

class AuthorFootnoteTests(unittest.TestCase):
    def test_author_decimal_and_date_in_footnote_are_preserved(self):
        md='Показатель[^2]\n\n[^2]: Значение 22,14; приказ от 26.04.2023'
        text=cleaned_text(md)
        self.assertIn('22,14',text)
        self.assertIn('26.04.2023',text)
        self.assertNotIn('[^2]',text)
        result=compare_decimals_to_spans(md,{'counts':{'22.14':1,'26.04':1},'evidence':[],'excluded_superscript_decimal_spans':[]})
        self.assertNotIn('22.14',result['pdf_only'])
    def test_reference_destination_is_not_author_numeric_value(self):
        text=cleaned_text('Текст\n\n[report]: https://example.org/22.14.pdf')
        self.assertNotIn('22.14',text)
    def test_multiline_footnote_body_is_not_lost(self):
        text=cleaned_text('[^a]: Первый показатель 1,25\n    Продолжение 3,75')
        self.assertIn('1,25',text);self.assertIn('3,75',text)

if __name__=='__main__':unittest.main()
