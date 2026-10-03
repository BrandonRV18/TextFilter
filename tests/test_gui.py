import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import urlencode
from zipfile import ZipFile

from src.gui import Handler, search_documents, save_document


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def make_document(self):
        nested = self.folder / 'entrevistas'
        nested.mkdir()
        with ZipFile(nested / 'ejemplo.docx', 'w') as archive:
            archive.writestr('word/document.xml', '''
                <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                  <w:body><w:p>
                    <w:r><w:rPr><w:shd w:fill="a4c2f4"/></w:rPr><w:t>Texto de prueba</w:t></w:r>
                    <w:r><w:t> RCP3</w:t></w:r>
                  </w:p></w:body>
                </w:document>''')

    def test_empty_folder_and_invalid_code(self):
        self.assertEqual(search_documents('RCP3', self.folder)['documents'], 0)
        for code in (' ', None, 3, 'x' * 201):
            with self.subTest(code=code), self.assertRaises(ValueError):
                search_documents(code, self.folder)

    def test_partial_results_and_no_matches(self):
        self.make_document()
        (self.folder / 'dañado.docx').write_text('archivo inválido')
        result = search_documents(' RCP3 ', self.folder)
        self.assertEqual(result['results'], [{'file': 'entrevistas/ejemplo.docx', 'text': 'Texto de prueba RCP3'}])
        self.assertEqual(len(result['errors']), 1)
        self.assertEqual(search_documents('NO_EXISTE', self.folder)['results'], [])
        self.assertEqual(search_documents('(RCP3)', self.folder)['code'], 'RCP3')

    def test_upload_preserves_duplicates_and_makes_files_searchable(self):
        self.make_document()
        content = (self.folder / 'entrevistas/ejemplo.docx').read_bytes()
        target = self.folder / 'input'
        self.assertEqual(save_document('Entrevista á.DOCX', content, target), 'Entrevista á.DOCX')
        self.assertEqual(save_document('Entrevista á.DOCX', content, target), 'Entrevista á (1).docx')
        self.assertEqual((target / 'Entrevista á.DOCX').read_bytes(), content)
        self.assertEqual(len(search_documents('RCP3', target)['results']), 2)
        self.assertEqual(len(list(target.iterdir())), 2)

    def test_upload_rejects_invalid_files_and_paths(self):
        self.make_document()
        content = (self.folder / 'entrevistas/ejemplo.docx').read_bytes()
        target = self.folder / 'input'
        for name, body in [('bad.docx', b'not a zip'), ('empty.docx', b''),
                           ('../outside.docx', content), ('C:\\outside.docx', content),
                           ('file.txt', content), ('~$temp.docx', content)]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                save_document(name, body, target)
        self.assertFalse(target.exists())

    def test_http_page_search_validation_and_origin(self):
        self.make_document()
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch('src.gui.search_documents', side_effect=lambda code: search_documents(code, self.folder)):
                connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                self.addCleanup(connection.close)
                connection.request('GET', '/')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn('Encuentra tus textos', response.read().decode())
                for payload, expected in [({'code': 'RCP3'}, 200), ({'code': ''}, 400), ([], 400)]:
                    connection.request('POST', '/api/search', json.dumps(payload), {'Content-Type': 'application/json'})
                    response = connection.getresponse()
                    self.assertEqual(response.status, expected)
                    body = json.loads(response.read())
                    if expected == 200:
                        self.assertEqual(body['results'][0]['text'], 'Texto de prueba RCP3')
                connection.request('POST', '/api/search', '{"code":"RCP3"}', {'Origin': 'https://example.com'})
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                connection.request('GET', '/input/ejemplo.docx')
                response = connection.getresponse()
                self.assertEqual(response.status, 404)
                response.read()
                content = (self.folder / 'entrevistas/ejemplo.docx').read_bytes()
                with patch('src.gui.save_document', side_effect=lambda name, body: save_document(name, body, self.folder)):
                    endpoint = '/api/upload?' + urlencode({'name': 'Nuevo á.docx'})
                    connection.request('POST', endpoint, content, {'Content-Type': 'application/octet-stream'})
                    response = connection.getresponse()
                    self.assertEqual(response.status, 201)
                    self.assertEqual(json.loads(response.read())['file'], 'Nuevo á.docx')
                    self.assertEqual((self.folder / 'Nuevo á.docx').read_bytes(), content)
                    connection.request('POST', endpoint, b'invalid', {'Content-Type': 'application/octet-stream'})
                    response = connection.getresponse()
                    self.assertEqual(response.status, 400)
                    response.read()
                    connection.request('POST', endpoint, content, {'Content-Type': 'application/octet-stream', 'Origin': 'https://example.com'})
                    response = connection.getresponse()
                    self.assertEqual(response.status, 403)
                    response.read()
                connection.request('POST', '/api/shutdown', b'')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())['message'], 'TextFilter cerrado.')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
