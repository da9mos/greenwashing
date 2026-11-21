import unittest

from convert_pdf import assess, display_page, fix_markup, reflow, verify_document


class ConverterTests(unittest.TestCase):
    def line(self, text, y, x=30):
        return text, x, y, 12, (1, 0)

    def test_wrap_only_in_one_unambiguous_block(self):
        first = 'Компания продолжила программу'
        second = 'повышения энергоэффективности.'
        text = f'<p>{first}</p>\n\n<p>{second}</p>\n'
        a = self.line(first, 30)
        b = self.line(second, 43)
        self.assertEqual(reflow(text, [[a, b]]), (f'<p>{first} {second}</p>\n', 1))
        self.assertEqual(reflow(text, [[a], [b]]), (text, 0))
        self.assertEqual(reflow(text, [[a, self.line(second, 43, x=220)]]), (text, 0))
        self.assertEqual(reflow(text, [[a, b], [b]]), (text, 0))
        table = f'<table><tr><td>\n{text}</td></tr></table>'
        self.assertEqual(reflow(table, [[a, b]]), (table, 0))

    def test_preserve_ambiguous_hyphen(self):
        first = 'Версия показателя социально-'
        second = 'экономического развития.'
        text = f'<p>{first}</p>\n\n<p>{second}</p>\n'
        self.assertEqual(reflow(text, [[self.line(first, 30), self.line(second, 43)]]), (text, 0))

    def test_literal_plus_row_keeps_following_page_visible(self):
        pluses = ' '.join('+' for _ in range(11))
        tail = display_page(2, 'Содержание второй страницы')
        raw = display_page(1, f'Данные таблицы\n{pluses}\n\nПродолжение') + '\n' + tail
        with self.assertRaisesRegex(ValueError, 'маркеры'):
            verify_document(raw, 2)
        fixed = display_page(1, fix_markup(f'Данные таблицы\n{pluses}\n\nПродолжение')) + '\n' + tail
        self.assertEqual(verify_document(fixed, 2), [])
        self.assertIn(' '.join(r'\+' for _ in range(11)), fixed)

    def test_report_broken_fragment(self):
        body = '[Внутри PDF](#pdf-page-2) · [Отсутствует](#lost)'
        text = display_page(1, body) + '\n' + display_page(2, 'Текст')
        self.assertEqual(verify_document(text, 2), ['lost'])

    def test_control_symbol_survives_quality_check(self):
        flags, _ = assess('Данные\x0bотчёта', '<p>Данные отчёта</p>')
        self.assertIn('проверить повреждённые символы по растру', flags)


if __name__ == '__main__':
    unittest.main()
