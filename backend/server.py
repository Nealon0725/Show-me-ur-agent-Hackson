import argparse
import json
import mimetypes
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote
from agents.workflow import Workflow
from agents.llm_client import LLMClientError
from agents.model_provider import parser_from_environment
from backend.documents import Documents
from backend.catalog import CATALOG, get_job, agent_job

ROOT = Path(__file__).resolve().parents[1]


def handler(workflow):
    documents = Documents(workflow.store.path)
    ui_root = ROOT / 'frontend/clearhire'

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, data, content_type='application/json'):
            body = json.dumps(data).encode() if content_type == 'application/json' else data
            self.send_response(status)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.path = unquote(urlsplit(self.path).path)
            if self.path == '/api/health':
                self.reply(200, {'status': 'ok'})
            elif self.path == '/':
                self.reply(200, (ui_root / 'index.html').read_bytes(), 'text/html')
            elif self.path == '/legacy':
                self.reply(200, (ROOT / 'frontend/index.html').read_bytes(), 'text/html')
            elif self.path == '/api/workspace':
                with closing(sqlite3.connect(workflow.store.path)) as db:
                    runs = [json.loads(r[0]) for r in db.execute('SELECT state FROM runs ORDER BY rowid')]
                parser = workflow.resume_parser
                self.reply(200, {'uploads': documents.list(), 'runs': [r for r in runs if r.get('job_id')],
                                 'mode': 'model' if parser else 'rules',
                                 'model': getattr(parser, 'model', None)})
            elif self.path.startswith('/api/uploads/'):
                try:
                    name, content = documents.get(self.path.split('/')[-1], binary=True)
                    self.reply(200, content, mimetypes.guess_type(name)[0] or 'application/octet-stream')
                except KeyError:
                    self.reply(404, {'error': 'File not found.'})
            elif self.path == '/api/demo':
                self.reply(200, json.loads((ROOT / 'data/demo.json').read_text(encoding='utf-8')))
            elif self.path == '/api/dataset':
                dataset = ROOT / 'data/agent_b_dataset/inputs'
                if not dataset.exists():
                    self.reply(404, {'error': 'Agent B dataset is not installed.'})
                    return
                resumes = [json.loads(line) for line in (dataset / 'resumes.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
                jobs = json.loads((dataset / 'jobs/jobs.json').read_text(encoding='utf-8'))
                self.reply(200, {'jobs': jobs, 'resumes': resumes, 'count': len(resumes)})
            elif self.path.startswith('/api/runs/'):
                try:
                    self.reply(200, workflow.get(self.path.split('/')[-1]))
                except KeyError:
                    self.reply(404, {'error': 'Run not found.'})
            else:
                target = (ui_root / self.path.lstrip('/')).resolve()
                if target.is_relative_to(ui_root.resolve()) and target.is_file() and target.suffix in ('.js', '.css', '.pdf', '.png', '.webmanifest'):
                    self.reply(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                else:
                    self.reply(404, {'error': 'Not found.'})

        def do_POST(self):
            # Same-origin local demo; reject cross-origin browser writes.
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc != self.headers.get('Host', ''):
                self.reply(403, {'error': 'Cross-origin requests are disabled.'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= (15000000 if self.path == '/api/uploads' else 4000000):
                    raise ValueError('Invalid request size.')
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError('Expected a JSON object.')
                if self.path == '/api/uploads':
                    get_job(payload.get('job_id'))
                    result = documents.add(payload)
                elif self.path == '/api/runs':
                    if 'job_id' in payload:
                        job_id = payload['job_id']
                        confirmed_job = agent_job(job_id)
                        ids = payload.get('candidate_ids')
                        if not isinstance(ids, list) or not 1 <= len(ids) <= 60 or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
                            raise ValueError('Select 1–60 distinct candidates.')
                        inputs = []
                        for candidate_id in ids:
                            candidate = next((c for c in CATALOG['candidates'] if c['id'] == candidate_id), None)
                            if candidate is None:
                                candidate = documents.get(candidate_id)
                            if candidate['jobId'] != job_id:
                                raise ValueError('Candidates must belong to the selected role.')
                            inputs.append(candidate)
                        result = workflow.create(None, [c['text'] for c in inputs], job=confirmed_job)
                        result['job_id'] = job_id
                        for candidate, source in zip(result['candidates'], inputs):
                            candidate['source_id'] = source['id']
                        workflow.store.save(result['id'], result)
                    else:
                        result = workflow.create(payload.get('jd'), payload.get('resumes'))
                else:
                    parts = self.path.strip('/').split('/')
                    if len(parts) != 4 or parts[:2] != ['api', 'runs']:
                        self.reply(404, {'error': 'Not found.'})
                        return
                    result = workflow.update(parts[2], parts[3], payload)
                self.reply(200, result)
            except KeyError:
                self.reply(404, {'error': 'Run not found.'})
            except LLMClientError as exc:
                self.reply(502, {'error': str(exc)})
            except (ValueError, TypeError, UnicodeDecodeError) as exc:
                self.reply(400, {'error': str(exc)})

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--db', default=str(ROOT / 'data/recruitment.sqlite3'))
    args = parser.parse_args()
    server = HTTPServer((args.host, args.port), handler(Workflow(args.db, parser_from_environment())))
    print(f'Recruitment demo: http://{args.host}:{args.port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
