"""Real socket/client qualification, including authentication and reconnect."""
import asyncio
import json
import os
import secrets
import socket
import subprocess
import sys
import time

import pytest

pytest.importorskip('mcp')
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from agent_visual_bridge import ReviewService, ValidationError
from agent_visual_bridge.mcp.http import load_token


@pytest.fixture
def running_server(tmp_path):
    token = secrets.token_urlsafe(48)
    token_path = tmp_path / 'token'
    token_path.write_text(token)
    token_path.chmod(0o600)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    database = tmp_path / 'http.db'
    service = ReviewService(database)
    review = service.create_review({'items': [{'id': 'a'}]})
    env = {**os.environ, 'AVB_DB': str(database)}
    with (tmp_path / 'server.log').open('w') as log:
        child = subprocess.Popen([sys.executable, '-m', 'agent_visual_bridge', 'mcp',
            '--transport', 'streamable-http', '--port', str(port), '--token-file', str(token_path)],
            env=env, stdout=log, stderr=log)
        url = f'http://127.0.0.1:{port}/mcp'
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if child.poll() is not None:
                    pytest.fail('MCP HTTP process exited: ' + (tmp_path / 'server.log').read_text())
                try:
                    if httpx.get(url, timeout=0.2).status_code == 401:
                        break
                except httpx.TransportError:
                    time.sleep(0.05)
            else:
                pytest.fail('MCP HTTP did not become ready')
            yield url, token, service, review
        finally:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


def test_real_http_authorization_origin_and_host(running_server):
    url, token, _, _ = running_server
    assert httpx.post(url, json={}, timeout=2).status_code == 401
    assert httpx.post(url, headers={'Authorization': 'Bearer wrong'}, json={}).status_code == 401
    headers = {'Authorization': f'Bearer {token}'}
    assert httpx.post(url, headers={**headers, 'Origin': 'https://evil.example'}, json={}).status_code == 403
    assert httpx.post(url, headers={**headers, 'Host': 'evil.example'}, json={}).status_code == 403
    assert httpx.get(url, headers={**headers, 'Accept': 'text/event-stream',
                                  'Mcp-Session-Id': 'unknown-session'}).status_code == 404


def test_http_session_reconnect_and_receipt_persistence(running_server):
    url, token, service, review = running_server

    async def read_receipt():
        headers = {'Authorization': f'Bearer {token}'}
        async with httpx.AsyncClient(headers=headers, timeout=10, trust_env=False) as http_client, streamable_http_client(url, http_client=http_client) as (read, write, session_id):
            async with ClientSession(read, write) as client:
                await client.initialize()
                first_id = session_id()
                assert first_id
                result = await client.call_tool('visual_bridge_get_review', {'review_id': review['review_id']})
                assert json.loads(result.content[0].text)['revision'] == 1
        # Exiting terminates the protocol session, preserving the durable review.
        receipt = service.submit_decisions(review['review_id'], 1, [{'id': 'a',
            'fingerprint': review['items'][0]['authorization_fingerprint'], 'decision_kind': 'approve',
            'constraints': ['Read only']}], 'synthetic-http', actor='automated-qualification',
            provenance='synthetic-technical-check')
        async with httpx.AsyncClient(headers=headers, timeout=10, trust_env=False) as http_client, streamable_http_client(url, http_client=http_client) as (read, write, session_id):
            async with ClientSession(read, write) as client:
                await client.initialize()
                assert session_id() != first_id
                result = await client.call_tool('visual_bridge_get_receipt', {'receipt_id': receipt['receipt_id']})
                assert json.loads(result.content[0].text)['decisions'][0]['constraints'] == ['Read only']
        return first_id

    terminated = asyncio.run(read_receipt())
    assert httpx.get(url, headers={'Authorization': f'Bearer {token}',
        'Accept': 'text/event-stream', 'Mcp-Session-Id': terminated}).status_code == 404
    assert ReviewService(service.store.path).get_review(review['review_id'])['decisions']['a']['constraints'] == ['Read only']


def test_private_token_required(tmp_path):
    path = tmp_path / 'token'
    path.write_text('x' * 48)
    if os.name != 'nt':
        path.chmod(0o644)
        with pytest.raises(ValidationError, match='private'):
            load_token(path)
    path.chmod(0o600)
    assert load_token(path) == 'x' * 48
    path.write_text('short')
    with pytest.raises(ValidationError):
        load_token(path)
    if os.name != 'nt':
        link = tmp_path / 'link'
        link.symlink_to(path)
        with pytest.raises(ValidationError):
            load_token(link)
    from agent_visual_bridge.mcp.http import run_http
    with pytest.raises(ValidationError, match='restricted'):
        run_http(tmp_path / 'db', '0.0.0.0', 8000, path)
