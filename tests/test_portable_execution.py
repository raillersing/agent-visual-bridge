import copy
import json
import sys

import pytest

from agent_visual_bridge import CooperativeAgent, ReviewService, ConflictError
from agent_visual_bridge.execution import ExecutionRequest
from agent_visual_bridge.executors.process import JsonProcessExecutor


def authorized(tmp_path):
    service = ReviewService(tmp_path / 'reviews.db')
    review = service.create_review({'items': [{'id': 'a', 'scope': 'src/a'}]})
    service.submit_decisions(review['review_id'], 1, [{'id': 'a',
        'fingerprint': review['items'][0]['authorization_fingerprint'], 'decision_kind': 'approve',
        'constraints': ['Preserve API'], 'comment': 'Read only'}], 'synthetic-check',
        actor='automated-qualification', provenance='synthetic-technical-check')
    return service, review


def test_process_engine_receives_durable_mandate(tmp_path):
    service, review = authorized(tmp_path)
    worker = tmp_path / 'worker.py'
    worker.write_text('import sys,json\nr=json.load(sys.stdin)\n'
        'print(json.dumps({"execution_id":r["execution_id"],"state":"succeeded",'
        '"evidence":[{"source":"worker","content":r["constraints"]}]}))\n')
    agent = CooperativeAgent(service, review['review_id'], JsonProcessExecutor([sys.executable, str(worker)], cwd=tmp_path))
    result = agent.run_next()
    assert result['state'] == 'succeeded'
    assert result['evidence'][0]['content'] == ['Preserve API', 'Read only']
    assert agent.run_next()['state'] == 'waiting'
    event = service.events(review['review_id'])[-1]
    assert event['execution_id'] == result['execution_id']


@pytest.mark.parametrize('body', ['import time; time.sleep(5)',
    'import sys; sys.exit(1)', 'print("not JSON")',
    'print(\'{"execution_id":"wrong","state":"succeeded","evidence":[]}\')'])
def test_uncertain_process_never_replays(tmp_path, body):
    service, review = authorized(tmp_path)
    worker = tmp_path / 'worker.py'
    worker.write_text(body)
    agent = CooperativeAgent(service, review['review_id'], JsonProcessExecutor([sys.executable, str(worker)], cwd=tmp_path, timeout=0.1))
    result = agent.run_next()
    assert result['state'] == 'unknown'
    assert agent.run_next()['state'] == 'waiting'
    assert len([e for e in service.events(review['review_id']) if e['kind'] == 'execution_started']) == 1


def test_controls_session_ownership_and_handoff(tmp_path):
    service, review = authorized(tmp_path)
    a = CooperativeAgent(service, review['review_id'], lambda *_: [], 'first')
    control = service.request_control(review['review_id'], 'pause')
    b = CooperativeAgent(service, review['review_id'], lambda *_: [], 'second')
    with pytest.raises(ConflictError, match='Select an agent session'):
        service.request_control(review['review_id'], 'stop')
    with pytest.raises(ConflictError, match='another or expired'):
        service.acknowledge_control(review['review_id'], control['control_id'], 'applied', agent_id=b.agent_id, session_id=b.session_id)
    assert a.run_next()['state'] == 'paused'
    a.release()
    with pytest.raises(ConflictError, match='expired or released'):
        a.run_next()
    assert b.run_next()['state'] == 'succeeded'
    assert service.request_control(review['review_id'], 'stop')['session_id'] == b.session_id


def test_expired_lease_cannot_ack_or_execute(tmp_path, monkeypatch):
    service, review = authorized(tmp_path)
    import time
    stamp = time.time()
    monkeypatch.setattr(time, 'time', lambda: stamp)
    a = CooperativeAgent(service, review['review_id'], lambda *_: pytest.fail('expired action'), lease_seconds=1)
    control = service.request_control(review['review_id'], 'pause')
    monkeypatch.setattr(time, 'time', lambda: stamp + 2)
    with pytest.raises(ConflictError):
        a.run_next()
    with pytest.raises(ConflictError):
        service.acknowledge_control(review['review_id'], control['control_id'], 'applied', agent_id=a.agent_id, session_id=a.session_id)
    assert service.request_control(review['review_id'], 'pause')['state'] == 'unsupported'
    with pytest.raises(ConflictError):
        service.register_agent(review['review_id'], 'impostor', ['pause'], a.session_id)


def test_reconcile_keeps_original_revision(tmp_path):
    service, review = authorized(tmp_path)
    agent = CooperativeAgent(service, review['review_id'], lambda *_: (_ for _ in ()).throw(TimeoutError()))
    result = agent.run_next()
    changed = copy.deepcopy(review)
    changed['items'][0]['scope'] = 'another/'
    service.revise_review(review['review_id'], changed, 1)
    progress = agent.reconcile('a', 'succeeded', 'Verified separately', [{'source': 'verification'}], result['execution_id'])
    assert progress['revision'] == 1
    assert progress['fingerprint'] == review['items'][0]['authorization_fingerprint']
    with pytest.raises(ConflictError):
        service.publish_progress(review['review_id'], 'a', 'succeeded', execution_id=result['execution_id'])


def test_output_bound_and_result_validation(tmp_path):
    worker = tmp_path / 'worker.py'
    worker.write_text('print("x"*1000)')
    request = ExecutionRequest('e', 'r', 1, 'a', 's', 'f', {}, [])
    from agent_visual_bridge.execution import UnknownExecution
    with pytest.raises(UnknownExecution):
        JsonProcessExecutor([sys.executable, str(worker)], cwd=tmp_path, max_output=100).execute(request)
    assert json.loads(json.dumps(request.document()))['contract_version'] == 1
