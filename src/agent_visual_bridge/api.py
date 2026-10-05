"""Loopback HTTP transport with per-instance capabilities and bounded requests."""
from __future__ import annotations

import hmac
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .metrics import record, summarize
from .models import ConflictError, ValidationError
from .templates import render_review


class LocalServer:
    def __init__(self, service, review_id, port=0):
        self.service, self.review_id = service, review_id
        self.human_token, self.agent_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.submitted = threading.Event()
        self.receipt = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(5)

            def log_message(self, *args):
                pass

            def guard(self, role=None):
                host = self.headers.get('Host', '')
                if host not in {f'127.0.0.1:{owner.port}', f'localhost:{owner.port}'}:
                    raise PermissionError('Invalid Host')
                origin = self.headers.get('Origin')
                if origin and origin not in {f'http://127.0.0.1:{owner.port}', f'http://localhost:{owner.port}'}:
                    raise PermissionError('Foreign origin')
                if role:
                    token = self.headers.get('X-AVB-Token', '')
                    expected = [owner.human_token] if role == 'human' else [owner.agent_token] if role == 'agent' else [owner.human_token, owner.agent_token]
                    if not any(hmac.compare_digest(token, value) for value in expected):
                        raise PermissionError('Invalid session capability')

            def respond(self, status, value, content_type='application/json', nonce=None):
                content = json.dumps(value, ensure_ascii=False).encode() if content_type == 'application/json' else value.encode()
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Referrer-Policy', 'no-referrer')
                if nonce:
                    self.send_header('Content-Security-Policy', f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'none'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(content)

            def do_GET(self):
                try:
                    path = urlsplit(self.path)
                    self.guard(None if path.path == '/' else 'either')
                    if path.path == '/':
                        view = owner.service.get_review(owner.review_id)
                        nonce = secrets.token_urlsafe(18)
                        body = render_review(view, {'token': owner.human_token}, owner.service.settings(view['project_id']))
                        body = body.replace('<script', f'<script nonce="{nonce}"')
                        self.respond(200, body, 'text/html; charset=utf-8', nonce)
                    elif path.path == '/api/review':
                        self.respond(200, owner.service.get_review(owner.review_id))
                    elif path.path == '/api/agents':
                        self.respond(200, owner.service.agent_sessions(owner.review_id))
                    elif path.path == '/api/events':
                        after = int(parse_qs(path.query).get('after', ['0'])[0])
                        self.respond(200, owner.service.events(owner.review_id, max(0, after)))
                    elif path.path == '/api/metrics':
                        self.respond(200, summarize(owner.service, owner.review_id))
                    else:
                        self.respond(404, {'error': 'Not found'})
                except (BrokenPipeError, ConnectionResetError):
                    return
                except Exception as exc:
                    self.error(exc)

            def body(self):
                if self.headers.get('Transfer-Encoding'):
                    raise ValidationError('Chunked requests not supported')
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2_000_000:
                    raise ValidationError('Body required, maximum 2 MB')
                if self.headers.get_content_type() != 'application/json':
                    raise ValidationError('Expected application/json')
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict):
                    raise ValidationError('Expected JSON object')
                return value

            def do_POST(self):
                try:
                    path = urlsplit(self.path).path
                    self.guard('agent' if path.startswith('/api/agent/') else 'human')
                    data = self.body()
                    if path == '/api/submit':
                        if data.get('review_id') != owner.review_id:
                            raise ValidationError('Wrong review')
                        result = owner.service.submit_decisions(owner.review_id, data.get('revision'), data.get('decisions'), data.get('request_key', ''))
                        owner.receipt = result
                        self.respond(200, result)
                        owner.submitted.set()
                        return
                    elif path == '/api/question':
                        result = owner.service.ask_item_question(owner.review_id, data.get('item_id'), data.get('message'))
                    elif path == '/api/control':
                        result = owner.service.request_control(owner.review_id, data.get('command'), data.get('payload'), data.get('agent_id'), data.get('session_id'))
                    elif path == '/api/revision-request':
                        result = owner.service.request_revision(owner.review_id, data.get('revision'), data.get('item_id'), data.get('changes'))
                    elif path == '/api/settings':
                        result = owner.service.settings(owner.service.get_review(owner.review_id)['project_id'], data)
                    elif path == '/api/metric':
                        record(owner.service, owner.review_id, data.get('event'), data.get('view_id', 'default'))
                        result = {'recorded': True}
                    elif path == '/api/cancel':
                        result = owner.service.close_review(owner.review_id)
                    elif path == '/api/agent/register':
                        result = owner.service.register_agent(owner.review_id, data.get('agent_id'), data.get('capabilities'), data.get('session_id'), data.get('lease_seconds', 300))
                    elif path == '/api/agent/release':
                        result = owner.service.release_agent(owner.review_id, data.get('agent_id'), data.get('session_id'))
                    elif path == '/api/agent/reply':
                        result = owner.service.publish_item_reply(owner.review_id, data.get('item_id'), data.get('message'), category=data.get('category', 'explanation'), question_seq=data.get('question_seq'))
                    elif path == '/api/agent/revise':
                        result = owner.service.revise_review(owner.review_id, data.get('proposal'), data.get('revision'))
                    elif path == '/api/agent/progress':
                        result = owner.service.publish_progress(owner.review_id, data.get('item_id'), data.get('state'), data.get('message', ''), data.get('evidence'), data.get('revision'), data.get('execution_id'))
                    elif path == '/api/agent/acknowledge':
                        result = owner.service.acknowledge_control(owner.review_id, data.get('control_id'), data.get('state'), data.get('reason', ''), data.get('agent_id'), data.get('session_id'))
                    else:
                        self.respond(404, {'error': 'Not found'})
                        return
                    self.respond(200, result)
                except (BrokenPipeError, ConnectionResetError):
                    return
                except Exception as exc:
                    self.error(exc)

            def error(self, exc):
                status = 403 if isinstance(exc, PermissionError) else 409 if isinstance(exc, ConflictError) else 400 if isinstance(exc, (ValueError, TypeError, KeyError)) else 500
                self.respond(status, {'error': str(exc) if status != 500 else 'Internal error'})

        self.server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        self.port = self.server.server_port
        self.url = f'http://127.0.0.1:{self.port}/'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=6)

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.close()
