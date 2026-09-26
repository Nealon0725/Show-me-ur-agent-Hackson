import base64
import io
import json
import tempfile
import threading
import unittest
import zipfile
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from agents.workflow import Workflow
from agents.parsers import parse_resume
from backend.catalog import agent_job
from backend.documents import extract_text
from backend.server import ROOT, handler


class ConnectedUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workflow = Workflow(Path(self.temp.name) / 'test.sqlite3')
        self.server = HTTPServer(('127.0.0.1', 0), handler(self.workflow))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def call(self, path, body=None):
        request = Request(self.base + path, data=None if body is None else json.dumps(body).encode(),
                          headers={'Content-Type': 'application/json'})
        with urlopen(request) as response:
            return json.load(response)

    def upload(self, name, content, job_id='JD-001'):
        return self.call('/api/uploads', {'job_id': job_id, 'name': name, 'content': base64.b64encode(content).decode()})

    def test_own_resume_complete_lifecycle_and_restore(self):
        resume = 'My resume\nBuilt Python HTTP APIs.\nDeveloped SQL database migrations.\nUsed Git collaboration and automated software tests.'
        doc = self.upload('my-resume.txt', resume.encode())
        self.assertEqual(doc['text'], resume)
        run = self.call('/api/runs', {'job_id': 'JD-001', 'candidate_ids': [doc['id']]})
        self.assertEqual(len(run['job']['criteria']), 4)
        self.assertEqual(run['candidates'][0]['source_id'], doc['id'])
        path = '/api/runs/' + run['id']
        run = self.call(path + '/confirm', {})
        candidate = run['candidates'][0]
        self.assertEqual(candidate['action'], 'REQUEST_INFO')
        self.assertEqual(candidate['evaluation']['documented_score'], 100)
        self.assertEqual([q['criterion_id'] for q in candidate['evaluation']['questions']], ['C1'])
        run = self.call(path + '/followup', {'candidate_id': candidate['id'], 'answers': {
            'C1': {'status': 'evidenced', 'evidence': '36 non-overlapping months of paid backend development.'}}})
        self.assertEqual(run['candidates'][0]['action'], 'SHORTLIST')
        run = self.call(path + '/review', {'candidate_id': candidate['id'], 'decision': 'shortlist', 'reason': 'Reviewed the evidence.'})
        restored = self.call('/api/workspace')
        self.assertEqual(restored['uploads'][0]['id'], doc['id'])
        self.assertEqual(restored['runs'][0], run)
        self.assertEqual(restored['mode'], 'rules')
        with urlopen(self.base + doc['download']) as response:
            self.assertEqual(response.read(), resume.encode())

    def test_pdf_docx_and_invalid_files(self):
        content = (ROOT / 'frontend/clearhire/resumes/CV-001.pdf').read_bytes()
        doc = self.upload('resume.pdf', content)
        self.assertGreater(len(doc['text']), 100)
        self.assertTrue(doc['pdf'].startswith('/api/uploads/UP-'))
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as z:
            z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Built Python APIs and SQL databases.</w:t></w:r></w:p></w:body></w:document>')
        self.assertIn('Python', self.upload('resume.docx', output.getvalue())['text'])
        for name, content in [('bad.pdf', b'not a pdf'), ('empty.txt', b''), ('file.exe', b'hello')]:
            with self.assertRaises(HTTPError) as error:
                self.upload(name, content)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        from pypdf import PdfWriter
        writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
        blank = io.BytesIO(); writer.write(blank)
        with self.assertRaisesRegex(ValueError, '扫描件'):
            extract_text('scan.pdf', blank.getvalue())

    def test_cross_role_and_path_validation(self):
        with self.assertRaises(HTTPError) as error:
            self.call('/api/runs', {'job_id': 'JD-001', 'candidate_ids': ['CV-002']})
        self.assertEqual(error.exception.code, 400); error.exception.close()
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base + '/%2e%2e/%2e%2e/backend/server.py')
        self.assertEqual(error.exception.code, 404); error.exception.close()
        request = Request(self.base + '/api/uploads', data=b'{}', headers={'Origin': 'http://external.example'})
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 403); error.exception.close()

    def test_pwa_assets_health_and_https_same_origin(self):
        self.assertEqual(self.call('/api/health'), {'status': 'ok'})
        for path, content_type in [
            ('/manifest.webmanifest', 'application/manifest+json'),
            ('/service-worker.js', 'text/javascript'),
            ('/app-icon.png', 'image/png'),
        ]:
            with urlopen(self.base + path) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(content_type, response.headers['Content-Type'])
                self.assertGreater(len(response.read()), 10)
        body = json.dumps({'job_id': 'JD-001', 'name': 'ios.txt',
                           'content': base64.b64encode(b'Built Python APIs.').decode()}).encode()
        request = Request(self.base + '/api/uploads', data=body, headers={
            'Content-Type': 'application/json',
            'Origin': 'https://127.0.0.1:' + str(self.server.server_port),
        })
        with urlopen(request) as response:
            self.assertEqual(response.status, 200)

    def test_compound_rules_do_not_accept_a_skill_list(self):
        criteria = agent_job('JD-001')['criteria']
        result = parse_resume('Python; SQL; Git; Jest; APIs', criteria)
        self.assertTrue(all(f['status'] == 'unknown' for f in result['facts'].values()))
        result = parse_resume('Built JavaScript HTTP APIs.\nUsed Git collaboration.', criteria)
        self.assertEqual(result['facts']['C2']['status'], 'evidenced')
        self.assertEqual(result['facts']['C4']['status'], 'unknown')
