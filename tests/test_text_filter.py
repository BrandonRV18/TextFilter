from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from src.text_filter import application_root, extract_matches, main


NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def run(text, props='<w:highlight w:val="yellow"/>'):
    return f'<w:r><w:rPr>{props}</w:rPr><w:t xml:space="preserve">{text}</w:t></w:r>'


def document(path, body, styles=None, header=None):
    with ZipFile(path, 'w') as archive:
        archive.writestr('word/document.xml', f'<w:document xmlns:w="{NS}"><w:body>{body}</w:body></w:document>')
        if styles:
            archive.writestr('word/styles.xml', f'<w:styles xmlns:w="{NS}">{styles}</w:styles>')
        if header:
            archive.writestr('word/header1.xml', f'<w:hdr xmlns:w="{NS}">{header}</w:hdr>')


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'example.docx'

    def texts(self, code='ABC123'):
        return [match[2] for match in extract_matches(self.path, code)]

    def test_packaged_data_locations(self):
        with patch('src.text_filter.sys.frozen', True, create=True), \
                patch('src.text_filter.sys.platform', 'darwin'), \
                patch('src.text_filter.Path.home', return_value=Path('/Users/test')):
            self.assertEqual(application_root(), Path('/Users/test/Documents/TextFilter'))

    def test_adjacent_formats_and_exact_suffix(self):
        document(self.path, '<w:p>' + run('Texto ') + run('ABC123  ', '<w:highlight w:val="yellow"/><w:b/>') + '</w:p>'
                 + '<w:p>' + run('ABC123 extra') + '</w:p>'
                 + '<w:p>' + run('abc123') + '</w:p>'
                 + '<w:p>' + run('No resaltado ABC123', '') + '</w:p>')
        self.assertEqual(self.texts(), ['Texto ABC123'])

    def test_plain_text_and_breaks_split_fragments(self):
        document(self.path, '<w:p>' + run('Anterior') + run(' separación ', '') + run('Texto ABC123')
                 + '<w:r><w:br/></w:r>' + run('Otro ABC123') + '</w:p>')
        self.assertEqual(self.texts(), ['Texto ABC123', 'Otro ABC123'])

    def test_inheritance_and_explicit_disable(self):
        styles = '<w:style w:type="paragraph" w:styleId="Base"><w:rPr><w:highlight w:val="yellow"/></w:rPr></w:style>'
        styles += '<w:style w:type="paragraph" w:styleId="Child"><w:basedOn w:val="Base"/></w:style>'
        styles += '<w:style w:type="character" w:styleId="Marked"><w:rPr><w:highlight w:val="yellow"/></w:rPr></w:style>'
        document(self.path, '<w:p><w:pPr><w:pStyle w:val="Child"/></w:pPr>'
                 + run('Heredado ABC123', '') + run(' excluido ABC123', '<w:highlight w:val="none"/>') + '</w:p>'
                 + '<w:p>' + run('Carácter ABC123', '<w:rStyle w:val="Marked"/>') + '</w:p>', styles=styles)
        self.assertEqual(self.texts(), ['Heredado ABC123', 'Carácter ABC123'])

    def test_tables_headers_and_hyperlinks(self):
        document(self.path, '<w:tbl><w:tr><w:tc><w:p><w:hyperlink>' + run('Tabla ABC123')
                 + '</w:hyperlink></w:p></w:tc></w:tr></w:tbl>', header='<w:p>' + run('Encabezado ABC123') + '</w:p>')
        self.assertEqual(self.texts(), ['Tabla ABC123', 'Encabezado ABC123'])

    def test_shading_and_code_outside_color(self):
        shade = '<w:shd w:val="clear" w:fill="c9daf8"/>'
        document(self.path, '<w:p>' + run('Texto marcado', shade) + run('. ', '')
                 + run('ABC123 y continúa la entrevista', '') + '</w:p>')
        self.assertEqual(self.texts(), ['Texto marcado. ABC123'])

    def test_color_changes_separate_fragments_and_allow_final_punctuation(self):
        document(self.path, '<w:p>' + run('Primero ABC123,')
                 + run('Segundo ABC123', '<w:shd w:fill="a4c2f4"/>') + '</w:p>')
        self.assertEqual(self.texts(), ['Primero ABC123,', 'Segundo ABC123'])

    def test_parentheses_are_optional_in_document_and_search(self):
        document(self.path, '<w:p>' + run('Dentro (ABC123).') + '</w:p>'
                 + '<w:p>' + run('Sin paréntesis ABC123') + '</w:p>'
                 + '<w:p>' + run('Código afuera') + run(' (ABC123), continúa', '') + '</w:p>')
        self.assertEqual(self.texts('ABC123'),
                         ['Dentro (ABC123).', 'Sin paréntesis ABC123', 'Código afuera (ABC123),'])
        self.assertEqual(self.texts('(ABC123)'),
                         ['Dentro (ABC123).', 'Sin paréntesis ABC123', 'Código afuera (ABC123),'])

    def test_parentheses_do_not_allow_partial_codes(self):
        document(self.path, '<w:p>' + run('Marcado') + run(' (ABC1234)', '') + '</w:p>'
                 + '<w:p>' + run('Marcado') + run(' ABC123)', '') + '</w:p>')
        self.assertEqual(self.texts('ABC123'), [])

    def test_unrelated_codes_and_underline_do_not_match(self):
        document(self.path, '<w:p>' + run('Solo subrayado ABC123', '<w:u/>') + '</w:p>'
                 + '<w:p>' + run('Marcado') + run(' ABC1234', '') + '</w:p>'
                 + '<w:p>' + run('Otro') + run(' otras palabras ABC123', '') + '</w:p>'
                 + '<w:p>' + run('Separado') + '<w:r><w:br/></w:r>' + run('ABC123', '') + '</w:p>')
        self.assertEqual(self.texts(), [])

    def test_shading_inheritance_and_cancellation(self):
        styles = '<w:style w:type="paragraph" w:default="1" w:styleId="Base"><w:rPr><w:shd w:fill="c9daf8"/></w:rPr></w:style>'
        document(self.path, '<w:p>' + run('Heredado ABC123', '')
                 + run('Sin fondo ABC123', '<w:shd w:val="nil"/>') + '</w:p>', styles=styles)
        self.assertEqual(self.texts(), ['Heredado ABC123'])

    def test_cli_continues_on_corrupt_file_and_searches_subfolders(self):
        nested = self.root / 'nested'
        nested.mkdir()
        document(nested / 'valid.DOCX', '<w:p>' + run('Válido ABC123') + '</w:p>')
        (self.root / 'broken.docx').write_text('invalid')
        (self.root / '~$temporary.docx').write_text('ignored')
        output = self.root / 'results.txt'
        with redirect_stdout(io.StringIO()):
            status = main(['ABC123', '--input', str(self.root), '--output', str(output)])
        self.assertEqual(status, 1)
        result = output.read_text(encoding='utf-8')
        self.assertIn('Válido ABC123', result)
        self.assertIn('Total de coincidencias: 1', result)
        self.assertIn('broken.docx', result)
        self.assertNotIn('~$temporary.docx', result)


if __name__ == '__main__':
    unittest.main()
