import base64
import io
import json
import tempfile
import threading
import unittest
import zipfile
from http.server import HTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from agents.workflow import Workflow
from backend.server import handler


class APITests(unittest.TestCase):
    def test_demo_http_flow(self):
        with tempfile.TemporaryDirectory() as temp:
            server = HTTPServer(('127.0.0.1', 0), handler(Workflow(Path(temp) / 'test.db')))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = 'http://127.0.0.1:' + str(server.server_port)
            def post(path, body):
                req = Request(base + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
                with urlopen(req) as response:
                    return json.load(response)
            try:
                with urlopen(base + '/') as response:
                    self.assertIn('Recruitment Assistant', response.read().decode())
                with urlopen(base + '/api/demo') as response:
                    demo = json.load(response)
                xml = ('<?xml version="1.0"?><w:document '
                       'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                       '<w:body><w:p><w:r><w:t>Candidate upload with Excel and Xero experience</w:t>'
                       '</w:r></w:p></w:body></w:document>')
                document = io.BytesIO()
                with zipfile.ZipFile(document, 'w') as archive:
                    archive.writestr('word/document.xml', xml)
                imported = post('/api/resume-files', {'files': [{
                    'name': 'candidate.docx',
                    'content_base64': base64.b64encode(document.getvalue()).decode(),
                }]})
                self.assertIn('Excel and Xero', imported['resumes'][0]['text'])
                with self.assertRaises(HTTPError) as too_many:
                    post('/api/resume-files', {'files': [{}] * 51})
                self.assertEqual(too_many.exception.code, 400)
                evaluated = post('/api/evaluate', demo)
                self.assertTrue(evaluated['criteria_confirmed'])
                self.assertIn('evaluation', evaluated['candidates'][0])
                run = post('/api/runs', demo)
                path = '/api/runs/' + run['id']
                run = post(path + '/confirm', {})
                self.assertEqual(run['candidates'][0]['action'], 'HUMAN_REVIEW')
                self.assertEqual(run['candidates'][1]['action'], 'REQUEST_INFORMATION')
                run = post(path + '/followup', {'candidate_id': 'C002', 'answers': {'xero': {'status': 'evidenced', 'evidence': 'I used Xero for invoice reconciliation.'}}})
                self.assertEqual(run['candidates'][1]['evaluation']['score'], 100)
                run = post(path + '/review', {'candidate_id': 'C002', 'decision': 'shortlist', 'reason': 'Reviewed all job requirements.'})
                self.assertEqual(run['candidates'][1]['action'], 'COMPLETE')
                with self.assertRaises(HTTPError) as error:
                    post('/api/runs', {'jd': '', 'resumes': []})
                self.assertEqual(error.exception.code, 400)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
