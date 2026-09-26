import json
import tempfile
import threading
import unittest
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
                    self.assertIn('Clearhire', response.read().decode())
                with urlopen(base + '/api/demo') as response:
                    demo = json.load(response)
                with urlopen(base + '/api/dataset') as response:
                    dataset = json.load(response)
                self.assertEqual(dataset['count'], 60)
                self.assertEqual(len(dataset['resumes']), 60)
                run = post('/api/runs', demo)
                path = '/api/runs/' + run['id']
                run = post(path + '/confirm', {})
                self.assertEqual(run['candidates'][0]['action'], 'SHORTLIST')
                self.assertEqual(run['candidates'][1]['action'], 'REQUEST_INFO')
                run = post(path + '/followup', {'candidate_id': 'C002', 'answers': {'xero': {'status': 'evidenced', 'evidence': 'I used Xero for invoice reconciliation.'}}})
                self.assertEqual(run['candidates'][1]['evaluation']['score'], 100)
                run = post(path + '/review', {'candidate_id': 'C002', 'decision': 'shortlist', 'reason': 'Reviewed all job requirements.'})
                self.assertEqual(run['candidates'][1]['action'], 'COMPLETE')
                with self.assertRaises(HTTPError) as error:
                    post('/api/runs', {'jd': '', 'resumes': []})
                self.assertEqual(error.exception.code, 400)
                error.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
