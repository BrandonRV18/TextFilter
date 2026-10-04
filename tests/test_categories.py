import unittest

from src.categories import catalog_options, resolve_query


class CategoryTests(unittest.TestCase):
    def test_every_category_has_unique_valid_codes(self):
        options = catalog_options()
        self.assertEqual(len(options), 23)
        values = [option['value'] for option in options]
        self.assertEqual(len(values), len(set(values)))
        self.assertEqual([option['value'] for option in options if option['type'] == 'category'],
                         ['CCP', 'DCP', 'RCP', 'FCP', 'LCP', 'FPCP'])

    def test_category_code_returns_all_subcategories(self):
        result = resolve_query(' c c p ')
        self.assertEqual(result['query'], 'CCP')
        self.assertEqual(result['codes'], ['CCP1', 'CCP2', 'CCP3'])

    def test_subcategory_and_parentheses_return_one_code(self):
        self.assertEqual(resolve_query('(rcp3)')['codes'], ['RCP3'])
        self.assertEqual(resolve_query('FPCP 2')['codes'], ['FPCP2'])

    def test_names_ignore_case_accents_and_punctuation(self):
        category = resolve_query('CONCEPCION DOCENTE DE LA CULTURA DE PAZ')
        self.assertEqual(category['query'], 'CCP')
        subcategory = resolve_query('comunicacion docente familias')
        self.assertEqual(subcategory['query'], 'FCP1')

    def test_unknown_or_empty_queries_are_rejected(self):
        for value in ('', 'ABC', 'CCP4', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_query(value)


if __name__ == '__main__':
    unittest.main()
