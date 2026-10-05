"""Detached, loopback-only browser sessions, independent of an MCP connection.

One supervisor per database owns bounded review listeners. Runtime credentials
are stored in a private directory and never included in exported reviews.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, ProxyHandler, build_opener
from urllib.error import HTTPError

from .api import LocalServer
from .sessions import ReviewService


def _paths(database):
    database = Path(database).resolve()
    key = hashlib.sha256(str(database).encode()).hexdigest()[:20]
    directory = database.parent / '.avb-runtime' / key
    directory.mkdir(parents=True, exist_ok=True)
    if os.name == 'posix':
        directory.chmod(0o700)
        directory.parent.chmod(0o700)
    return database, directory / 'supervisor.json', directory / 'startup.lock'


def _request(manifest, action, **values):
    info = json.loads(manifest.read_text(encoding='utf-8'))
    # Never send the control credential to a URL supplied by the manifest.
    port = info['port']
    if type(port) is not int or not 0 < port < 65536:
        raise ValueError('Invalid supervisor port')
    request = Request(f'http://127.0.0.1:{port}/{action}',
                      data=json.dumps(values).encode(), method='POST',
                      headers={'Content-Type': 'application/json', 'X-AVB-Token': info['token']})
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=3) as response:
            return json.load(response)
    except HTTPError as exc:
        raise RuntimeError('Browser supervisor refused the operation') from exc


def open_browser_session(database, review_id, *, lease_seconds=3600):
    """Return a local URL promptly; expiration closes access, not the review."""
    if not math.isfinite(lease_seconds) or not 1 <= lease_seconds <= 86400:
        raise ValueError('lease_seconds must be between 1 and 86400')
    service = ReviewService(database)
    service.get_review(review_id)
    database, manifest, lock = _paths(service.store.path)
    for attempt in range(100):
        if manifest.exists():
            try:
                return _request(manifest, 'open', review_id=review_id, lease_seconds=lease_seconds)
            except (OSError, ValueError, KeyError):
                pass
        try:
            descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            # A crashed startup can be retried; never remove an active lease.
            try:
                if time.time() - lock.stat().st_mtime > 30:
                    lock.unlink(missing_ok=True)
            except FileNotFoundError:
                pass
            time.sleep(.1)
            continue
        os.close(descriptor)
        try:
            environment = os.environ.copy()
            environment['PYTHONPATH'] = str(Path(__file__).resolve().parents[1]) + os.pathsep + environment.get('PYTHONPATH', '')
            options = {'start_new_session': True} if os.name == 'posix' else {
                'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS}
            process = subprocess.Popen([sys.executable, '-m', 'agent_visual_bridge.browser', str(database)],
                                       env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, **options)
            for _ in range(60):
                try:
                    return _request(manifest, 'open', review_id=review_id, lease_seconds=lease_seconds)
                except (OSError, ValueError, KeyError):
                    time.sleep(.1)
            # Do not leave a slow failed startup able to publish a second owner.
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            raise RuntimeError('Browser supervisor failed to start')
        finally:
            lock.unlink(missing_ok=True)
    raise RuntimeError('Browser supervisor startup is busy; retry')


def stop_browser_sessions(database):
    """Close listeners for this database only, preserving every review/receipt."""
    _, manifest, _ = _paths(database)
    if not manifest.exists():
        return {'state': 'not_running'}
    try:
        identity = json.loads(manifest.read_text(encoding='utf-8'))['token']
        result = _request(manifest, 'stop')
        for _ in range(100):
            try:
                if json.loads(manifest.read_text(encoding='utf-8'))['token'] != identity:
                    return result
            except FileNotFoundError:
                return result
            time.sleep(.1)
        return {'state': 'stop-requested'}
    except (OSError, ValueError, KeyError):
        return {'state': 'not_running'}


def run_supervisor(database):
    database, manifest, _ = _paths(database)
    service = ReviewService(database)
    token = secrets.token_urlsafe(32)
    sessions, mutex, stopped = {}, threading.Lock(), threading.Event()
    started = time.monotonic()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            import hmac
            try:
                self.connection.settimeout(3)
                if self.headers.get('Host') != f'127.0.0.1:{server.server_port}' or self.headers.get('Origin'):
                    raise PermissionError('Invalid origin or host')
                if not hmac.compare_digest(self.headers.get('X-AVB-Token', ''), token):
                    raise PermissionError('Invalid capability')
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 8192 or self.headers.get_content_type() != 'application/json' or self.headers.get('Transfer-Encoding'):
                    raise ValueError('Expected bounded JSON')
                data = json.loads(self.rfile.read(size))
                if self.path == '/stop':
                    stopped.set()
                    value = {'state': 'stopped'}
                elif self.path == '/open':
                    if stopped.is_set():
                        raise ValueError('Supervisor is shutting down; retry')
                    review = service.get_review(data['review_id'])
                    duration = data['lease_seconds']
                    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or not 1 <= duration <= 86400:
                        raise ValueError('Invalid lease')
                    with mutex:
                        existing = sessions.get(review['review_id'])
                        if existing is None:
                            if len(sessions) >= 32:
                                raise ValueError('Browser session limit reached (32)')
                            existing = (LocalServer(service, review['review_id']).start(), 0)
                        local, _ = existing
                        sessions[review['review_id']] = (local, time.monotonic() + duration)
                    value = {'review_id': review['review_id'], 'revision': review['revision'],
                             'state': review['state'], 'url': local.url, 'url_scope': 'server-loopback',
                             'lease_seconds': duration, 'supervisor_pid': os.getpid(),
                             'resume': 'Open again to renew access; the review remains in SQLite'}
                else:
                    raise ValueError('Unknown operation')
                status = 200
            except (ValueError, KeyError, TypeError, PermissionError) as exc:
                status = 403 if isinstance(exc, PermissionError) else 400
                value = {'error': str(exc)}
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.timeout = .2
    temporary = manifest.with_suffix('.tmp')
    descriptor = os.open(str(temporary), os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        json.dump({'port': server.server_port, 'token': token, 'pid': os.getpid()}, output)
    temporary.replace(manifest)
    try:
        while not stopped.is_set():
            server.handle_request()
            with mutex:
                expired = []
                for key, (local, deadline) in list(sessions.items()):
                    if time.monotonic() >= deadline:
                        expired.append(local)
                        del sessions[key]
                if expired:
                    with ThreadPoolExecutor(max_workers=8) as pool:
                        list(pool.map(lambda local: local.close(), expired))
                if not sessions and time.monotonic() - started > 15:
                    break
    finally:
        server.server_close()
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda session: session[0].close(), sessions.values()))
        manifest.unlink(missing_ok=True)


if __name__ == '__main__':
    run_supervisor(sys.argv[1])
