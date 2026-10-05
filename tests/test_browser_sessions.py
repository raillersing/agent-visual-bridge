"""Browser ownership survives an originating process and expires without approval."""
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from urllib.request import Request, urlopen

from agent_visual_bridge.browser import open_browser_session, stop_browser_sessions
from agent_visual_bridge.sessions import ReviewService


def test_detached_access_survives_origin_and_reuses_one_supervisor(tmp_path):
    database = tmp_path / 'reviews.db'
    service = ReviewService(database)
    first = service.create_review({'items': [{'id': 'a'}]})
    second = service.create_review({'items': [{'id': 'b'}]})
    env = {**os.environ, 'PATH': ''}  # No Codex executable, no external agent.
    try:
        origin = subprocess.run([sys.executable, '-m', 'agent_visual_bridge', '--db', str(database),
                                 'open', first['review_id']], env=env, capture_output=True,
                                text=True, timeout=15, check=True)
        browser = json.loads(origin.stdout)
        with urlopen(browser['url'], timeout=3) as response:
            html = response.read().decode()
        assert first['review_id'] in html and 'avb-proposal' in html
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            opened = list(pool.map(lambda review: open_browser_session(database, review['review_id']), [first, second]))
        assert {s['supervisor_pid'] for s in opened} == {browser['supervisor_pid']}
        assert opened[0]['url'] == browser['url']
        # Submit through the real browser HTTP route, then reread durable receipt.
        import re
        token = re.search(r'"token"\s*:\s*"([^"]+)"', html).group(1)
        body = {'review_id': first['review_id'], 'revision': 1, 'request_key': 'browser-once',
                'decisions': [{'id': 'a', 'decision_kind': 'approve',
                               'fingerprint': first['items'][0]['authorization_fingerprint']}]}
        request = Request(browser['url'] + 'api/submit', data=json.dumps(body).encode(),
                          headers={'Content-Type': 'application/json', 'X-AVB-Token': token})
        with urlopen(request, timeout=3) as response:
            receipt = json.load(response)
        assert ReviewService(database).get_receipt(receipt['receipt_id']) == receipt
    finally:
        stop_browser_sessions(database)


def test_access_expiry_does_not_expire_review(tmp_path):
    database = tmp_path / 'reviews.db'
    service = ReviewService(database)
    review = service.create_review({'items': [{'id': 'a'}]})
    try:
        browser = open_browser_session(database, review['review_id'], lease_seconds=1)
        time.sleep(1.5)
        current = service.get_review(review['review_id'])
        assert current['state'] == 'awaiting_input' and current['receipts'] == []
        renewed = open_browser_session(database, review['review_id'])
        assert renewed['supervisor_pid'] == browser['supervisor_pid']
        with urlopen(renewed['url'], timeout=3) as response:
            assert response.status == 200
    finally:
        stop_browser_sessions(database)


def test_concurrent_cold_start_uses_one_supervisor(tmp_path):
    database = tmp_path / 'cold.db'
    review = ReviewService(database).create_review({'items': [{'id': 'a'}]})
    try:
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            sessions = list(pool.map(lambda _: open_browser_session(database, review['review_id']), range(2)))
        assert sessions[0]['supervisor_pid'] == sessions[1]['supervisor_pid']
        assert sessions[0]['url'] == sessions[1]['url']
    finally:
        assert stop_browser_sessions(database)['state'] == 'stopped'


def test_unresponsive_startup_is_terminated_without_authorizing(tmp_path, monkeypatch):
    import pytest
    from agent_visual_bridge import browser
    database = tmp_path / 'failed.db'
    service = ReviewService(database)
    review = service.create_review({'items': [{'id': 'a'}]})
    original = subprocess.Popen
    processes = []
    def unresponsive(_args, **kwargs):
        process = original([sys.executable, '-c', 'import time; time.sleep(60)'], **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(browser.subprocess, 'Popen', unresponsive)
    with pytest.raises(RuntimeError, match='failed to start'):
        open_browser_session(database, review['review_id'])
    assert processes[0].poll() is not None
    assert service.get_review(review['review_id'])['state'] == 'awaiting_input'
