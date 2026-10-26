"""Loopback-only development server with async jobs and polling trace updates."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .agent import Agent, markdown
from .demo import DemoWeb, DemoModel, QUESTION
from .providers import Nimble, ProviderError
from .hosted import NimbleAgent
from .storage import Store

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    path = ROOT / '.env'
    if path.is_file():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                if key.strip() in ('NIMBLE_API_KEY',):
                    os.environ.setdefault(key.strip(), value.strip().strip('\"\''))


def make_server(port=8765, db_path=None):
    store = Store(db_path or ROOT / 'data' / 'proof.db')
    slot = threading.BoundedSemaphore(1)

    def execute(rid, question, mode):
        try:
            emit = lambda event: store.event(rid, event)
            agent = Agent(DemoWeb(), DemoModel(), emit) if mode == 'demo' else NimbleAgent(emit)
            result = agent.run(question)
            result['mode'] = 'synthetic offline demo' if mode == 'demo' else 'live'
            store.finish(rid, result=result)
        except (ValueError, ProviderError) as error:
            store.finish(rid, error=str(error))
        except Exception:
            store.finish(rid, error='Unexpected run failure. Check the local server console.')
            import traceback
            traceback.print_exc()
        finally:
            slot.release()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def allowed(self):
            expected = '127.0.0.1:%s' % self.server.server_port
            host = self.headers.get('Host')
            if host not in (expected, 'localhost:%s' % self.server.server_port):
                return False
            origin = self.headers.get('Origin')
            return origin is None or origin in ('http://' + expected, 'http://localhost:%s' % self.server.server_port)

        def send(self, status, body, content_type='application/json'):
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.allowed():
                return self.send(403, {'error': 'Local origin required.'})
            path = urlsplit(self.path).path
            if path == '/api/config':
                return self.send(200, {'live_ready': bool(os.environ.get('NIMBLE_API_KEY'))})
            if path == '/api/runs':
                return self.send(200, store.recent())
            if path.startswith('/api/runs/'):
                parts = path.split('/')
                run = store.get(parts[3])
                if run is None:
                    return self.send(404, {'error': 'Run not found.'})
                if len(parts) == 5 and parts[4] == 'markdown':
                    if run['status'] != 'complete':
                        return self.send(409, {'error': 'Run is not complete.'})
                    return self.send(200, markdown(run['result']), 'text/markdown; charset=utf-8')
                return self.send(200, run)
            files = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
            if path in files:
                name, mime = files[path]
                return self.send(200, (ROOT / 'web' / name).read_bytes(), mime + '; charset=utf-8')
            self.send(404, {'error': 'Not found.'})

        def do_POST(self):
            if not self.allowed():
                return self.send(403, {'error': 'Local origin required.'})
            if self.path != '/api/runs':
                return self.send(404, {'error': 'Not found.'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send(415, {'error': 'Use application/json.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 8192:
                    raise ValueError('Request must contain 1–8192 bytes.')
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('Request must be an object.')
                mode = body.get('mode')
                if mode not in ('demo', 'live'):
                    raise ValueError('Mode must be demo or live.')
                question = QUESTION if mode == 'demo' else body.get('question')
                if not isinstance(question, str) or not 5 <= len(question.strip()) <= 1000:
                    raise ValueError('Question must contain 5–1000 characters.')
                if mode == 'live':
                    Nimble()  # Fail early before creating a job.
            except (ValueError, ProviderError) as error:
                return self.send(400, {'error': str(error)})
            if not slot.acquire(blocking=False):
                return self.send(409, {'error': 'One run is already active. Wait for it to finish.'})
            try:
                rid = store.create(question, mode)
                threading.Thread(target=execute, args=(rid, question, mode), daemon=True).start()
            except Exception:
                slot.release()
                raise
            self.send(202, {'id': rid})

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    return server


def serve(port):
    load_env()
    server = make_server(port)
    print('Proof is running at http://127.0.0.1:%s' % server.server_port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
