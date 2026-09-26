import argparse
import base64
import binascii
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from agents.workflow import Workflow
from agents.llm_client import LLMClientError
from agents.model_provider import parser_from_environment
from agents.ui_adapter import evaluate_ui_resumes
from tools.resume_reader import ResumeReadError, read_resume

ROOT = Path(__file__).resolve().parents[1]


def handler(workflow):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, data, content_type='application/json'):
            body = json.dumps(data).encode() if content_type == 'application/json' else data
            self.send_response(status)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            request_path = unquote(urlparse(self.path).path)
            if request_path == '/':
                self.reply(200, (ROOT / 'index.html').read_bytes(), 'text/html')
            elif request_path in ('/bundle.js', '/styles.css', '/accessibility.css'):
                path = ROOT / request_path.lstrip('/')
                content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
                self.reply(200, path.read_bytes(), content_type)
            elif request_path == '/api/demo':
                self.reply(200, json.loads((ROOT / 'data/demo.json').read_text(encoding='utf-8')))
            elif request_path.startswith('/api/runs/'):
                try:
                    self.reply(200, workflow.store.get(request_path.split('/')[-1]))
                except KeyError:
                    self.reply(404, {'error': 'Run not found.'})
            else:
                self.reply(404, {'error': 'Not found.'})

        def do_POST(self):
            # Same-origin local demo; reject cross-origin browser writes.
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                self.reply(403, {'error': 'Cross-origin requests are disabled.'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8 * 1024 * 1024:
                    raise ValueError('Invalid request size.')
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError('Expected a JSON object.')
                if self.path == '/api/resume-files':
                    files = payload.get('files')
                    if not isinstance(files, list) or not 1 <= len(files) <= 50:
                        raise ValueError('Select between 1 and 50 resume files.')
                    resumes = []
                    for item in files:
                        if not isinstance(item, dict):
                            raise ValueError('Each uploaded file must be an object.')
                        name = item.get('name')
                        encoded = item.get('content_base64')
                        if not isinstance(encoded, str):
                            raise ValueError(f'{name or "Resume"}: file content is missing.')
                        try:
                            content = base64.b64decode(encoded, validate=True)
                        except (binascii.Error, ValueError) as exc:
                            raise ValueError(f'{name or "Resume"}: invalid file content.') from exc
                        resumes.append({'name': name, 'text': read_resume(name, content)})
                    result = {'resumes': resumes}
                elif self.path == '/api/evaluate':
                    result = workflow.create(payload.get('jd'), payload.get('resumes'))
                    result = workflow.update(result['id'], 'confirm', {})
                elif self.path == '/api/ui/evaluate':
                    result = evaluate_ui_resumes(payload.get('job_id'), payload.get('resumes'),
                                                 workflow.resume_parser)
                elif self.path == '/api/runs':
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
            except (ResumeReadError, ValueError, TypeError, UnicodeDecodeError) as exc:
                self.reply(400, {'error': str(exc)})

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--db', default=str(ROOT / 'data/recruitment.sqlite3'))
    args = parser.parse_args()
    server = HTTPServer(('127.0.0.1', args.port), handler(Workflow(args.db, parser_from_environment())))
    print(f'Recruitment demo: http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
