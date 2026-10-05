"""Authenticated loopback Streamable HTTP. No public deployment or OAuth claim."""
from __future__ import annotations

import hmac
import os
import stat
from pathlib import Path

from ..models import ValidationError


def load_token(path):
    if not path:
        raise ValidationError('Streamable HTTP requires --token-file')
    target = Path(path)
    if target.is_symlink():
        raise ValidationError('Token file must not be a symlink')
    info = target.stat()
    if not stat.S_ISREG(info.st_mode) or (os.name != 'nt' and info.st_mode & 0o077):
        raise ValidationError('Token file must be private (0600)')
    if info.st_size > 4096:
        raise ValidationError('Token file is too large')
    token = target.read_text(encoding='utf-8').strip()
    if not 32 <= len(token) <= 512 or not token.isascii() or any(c.isspace() for c in token):
        raise ValidationError('Token must contain 32 to 512 non-whitespace ASCII characters')
    return token


class LocalBearerGuard:
    def __init__(self, app, token, port):
        self.app, self.token = app, token
        self.host = f'127.0.0.1:{port}'
        self.origin = f'http://{self.host}'

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = scope.get('headers', [])
        hosts = [v.decode('latin1') for k, v in headers if k.lower() == b'host']
        origins = [v.decode('latin1') for k, v in headers if k.lower() == b'origin']
        auth = [v.decode('latin1') for k, v in headers if k.lower() == b'authorization']
        status = None
        if hosts != [self.host] or (origins and origins != [self.origin]):
            status = 403
        elif len(auth) != 1 or not hmac.compare_digest(auth[0].encode('latin1'), ('Bearer ' + self.token).encode('ascii')):
            status = 401
        if status:
            extra = [(b'www-authenticate', b'Bearer')] if status == 401 else []
            await send({'type': 'http.response.start', 'status': status,
                        'headers': [(b'content-type', b'text/plain'), (b'cache-control', b'no-store')] + extra})
            await send({'type': 'http.response.body', 'body': b'Access denied'})
            return
        await self.app(scope, receive, send)


def run_http(database, host, port, token_file):
    if host != '127.0.0.1' or not 1 <= port <= 65535:
        raise ValidationError('Streamable HTTP is restricted to 127.0.0.1 and a valid port')
    token = load_token(token_file)
    import uvicorn
    from mcp.server.transport_security import TransportSecuritySettings
    from .sdk import create_server
    server = create_server(database, host=host, port=port, json_response=True,
                           max_sessions=64, session_idle_timeout=300,
                           max_request_body_size=1024 * 1024,
                           transport_security=TransportSecuritySettings(
                               enable_dns_rebinding_protection=True,
                               allowed_hosts=[f'{host}:{port}'],
                               allowed_origins=[f'http://{host}:{port}']))
    app = LocalBearerGuard(server.streamable_http_app(), token, port)
    uvicorn.run(app, host=host, port=port, log_level='warning', access_log=False)
