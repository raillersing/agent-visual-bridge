import json
import urllib.error
import urllib.request

import pytest

from agent_visual_bridge import ReviewService, VisualBridge
from agent_visual_bridge.api import LocalServer
from agent_visual_bridge.watcher import serve_and_wait, watch_html_file


def post(server, data, token=None, origin=None, path='/api/submit'):
    headers = {'Content-Type': 'application/json', 'X-AVB-Token': token or server.human_token}
    if origin:
        headers['Origin'] = origin
    request = urllib.request.Request(server.url.rstrip('/')+path, data=json.dumps(data).encode(), headers=headers)
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.load(response)


def test_http_validates_origin_payload_and_role(tmp_path):
    service = ReviewService(tmp_path/'reviews.db')
    review = service.create_review({'items': [{'id': 'a'}]})
    with LocalServer(service, review['review_id']) as server:
        for value, token, origin, status in [({}, None, None, 400), ({}, None, 'https://foreign.example', 403),
                                            ({}, server.agent_token, None, 403)]:
            with pytest.raises(urllib.error.HTTPError) as error:
                post(server, value, token, origin)
            assert error.value.code == status
            assert not server.submitted.is_set()
        payload = {'review_id': review['review_id'], 'revision': 1, 'request_key': 'one', 'decisions': [
            {'id': 'a', 'decision_kind': 'approve', 'fingerprint': review['items'][0]['authorization_fingerprint'], 'comment': 'Only src'}]}
        receipt = post(server, payload)
        assert receipt['receipt_id'] == server.receipt['receipt_id']
        assert 'Only src' in ReviewService(service.store.path).get_receipt(receipt['receipt_id'])['mandate_markdown']
        assert post(server, payload) == receipt


def test_two_servers_have_separate_reports_tokens_and_decisions(tmp_path):
    service = ReviewService(tmp_path/'reviews.db')
    one = service.create_review({'title':'One','items':[{'id':'a'}]})
    two = service.create_review({'title':'Two','items':[{'id':'a'}]})
    with LocalServer(service, one['review_id']) as first, LocalServer(service, two['review_id']) as second:
        assert first.human_token != second.human_token
        with pytest.raises(urllib.error.HTTPError) as error:
            post(second, {}, token=first.human_token)
        assert error.value.code == 403
        assert 'One' in urllib.request.urlopen(first.url).read().decode()
        assert 'Two' in urllib.request.urlopen(second.url).read().decode()


def test_serve_timeout_never_reads_unsubmitted_html(tmp_path):
    service = ReviewService(tmp_path/'reviews.db')
    path = VisualBridge('Review',[{'id':'a'}]).save_html(tmp_path/'report.html')
    with pytest.raises(TimeoutError):
        serve_and_wait(path, open_browser=False, timeout=.01, service=service)
    assert service.list_reviews()[0]['state'] == 'expired'
    with pytest.raises(TimeoutError):
        watch_html_file(path, timeout=.01, check_interval=.002)
