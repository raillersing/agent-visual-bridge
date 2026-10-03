import copy
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from agent_visual_bridge import ReviewService, ValidationError, ConflictError, CooperativeAgent
from agent_visual_bridge.models import normalize
from agent_visual_bridge.policy import evaluate
from agent_visual_bridge.metrics import record, summarize


@pytest.fixture
def service(tmp_path):
    return ReviewService(tmp_path / 'reviews.db')


def proposal():
    return {'title': 'Plan', 'items': [
        {'id': 'a', 'title': 'First', 'scope': 'src/a', 'action': {'operation': 'edit', 'scope': 'src/a', 'reversible': True}},
        {'id': 'b', 'title': 'Second', 'dependencies': ['a']},
        {'id': 'c', 'title': 'Independent'}]}


def decide(review, key, kind='approve', **kwargs):
    item = next(i for i in review['items'] if i['id'] == key)
    return {'id': key, 'fingerprint': item['authorization_fingerprint'], 'decision_kind': kind, **kwargs}


@pytest.mark.parametrize('data', [None, {'items': []}, {'items': ['x']},
    {'items': [{'id': 'a'}, {'id': 'a'}]}, {'items': [{'id': "x');alert(1)//"}]},
    {'items': [{'id': 'a', 'dependencies': ['b']}]},
    {'items': [{'id': 'a', 'dependencies': ['b']}, {'id': 'b', 'dependencies': ['a']}]},
    {'items': [{'id': 'a', 'options': ['x', {'id': 'option-1', 'label': 'y'}]}]},
    {'items': [{}], 'report_type': 'unknown'}, {'items': [{}], 'extra': float('nan')}])
def test_invalid_documents(data):
    with pytest.raises(ValidationError):
        normalize(data)


def test_agent_status_is_never_human_authority(service):
    review = service.create_review({'items': [{'id': 'a', 'status': 'validate', 'remark': 'agent note'}]})
    assert review['decisions'] == {}


def test_partial_persistence_comments_and_idempotency(service):
    review = service.create_review(proposal())
    decisions = [decide(review, 'a', comment='Only src/', constraints=['Keep compatibility'])]
    receipt = service.submit_decisions(review['review_id'], 1, decisions, 'request-1')
    assert receipt['pending'] == ['b', 'c']
    assert 'Only src/' in receipt['mandate_markdown']
    other = ReviewService(service.store.path)
    assert other.get_receipt(receipt['receipt_id']) == receipt
    assert service.submit_decisions(review['review_id'], 1, decisions, 'request-1') == receipt
    with pytest.raises(ConflictError):
        service.submit_decisions(review['review_id'], 1, [decide(review, 'b')], 'request-1')


def test_deferred_can_be_answered_later(service):
    review = service.create_review({'items': [{'id': 'a', 'interaction_kind': 'clarify'}]})
    first = service.submit_decisions(review['review_id'], 1, [decide(review, 'a', 'defer', comment='Question only')], 'one')
    assert first['state'] == 'partially_submitted'
    assert first['decisions'][0]['decision_kind'] == 'defer'
    second = service.submit_decisions(review['review_id'], 1, [decide(review, 'a', 'answer', answer='Yes')], 'two')
    assert second['state'] == 'submitted'


def test_wrong_kind_and_option(service):
    review = service.create_review({'items': [{'id': 'a', 'interaction_kind': 'clarify', 'options': ['x','y']}]})
    for value in [decide(review, 'a'), decide(review, 'a', 'choose', options=['invalid']),
                  decide(review, 'a', 'choose', options=[]), decide(review, 'a', 'answer', answer='')]:
        with pytest.raises(ValidationError):
            service.submit_decisions(review['review_id'], 1, [value], 'one')
    result = service.submit_decisions(review['review_id'], 1, [decide(review, 'a', 'choose', options=['option-2'])], 'two')
    assert result['decisions'][0]['options'] == ['option-2']


def test_revision_invalidates_transitive_dependencies_only(service):
    original = proposal()
    review = service.create_review(original)
    service.submit_decisions(review['review_id'], 1, [decide(review, i) for i in ('a','b','c')], 'one')
    changed = copy.deepcopy(original)
    changed['items'][0]['scope'] = 'different/'
    revised = service.revise_review(review['review_id'], changed, 1)
    assert list(revised['decisions']) == ['c']
    with pytest.raises(ConflictError):
        service.submit_decisions(review['review_id'], 1, [decide(review, 'a')], 'stale')
    with pytest.raises(ConflictError):
        service.submit_decisions(review['review_id'], 2, [decide(review, 'a')], 'stale-item')


def test_two_threads_submit_one_receipt(service):
    review = service.create_review({'items': [{'id': 'a'}]})
    def submit():
        return service.submit_decisions(review['review_id'], 1, [decide(review, 'a')], 'one')
    with ThreadPoolExecutor(2) as pool:
        receipts = list(pool.map(lambda _: submit(), range(2)))
    assert receipts[0] == receipts[1]
    assert len(service.get_review(review['review_id'])['receipts']) == 1


def test_timeout_cancel_and_closed_reviews(service):
    review = service.create_review({'items': [{'id': 'a'}]})
    service.close_review(review['review_id'], 'expired')
    with pytest.raises(ConflictError):
        service.submit_decisions(review['review_id'], 1, [decide(review, 'a')], 'one')


def test_controls_and_dependency_execution(service, tmp_path):
    review = service.create_review(proposal())
    seen = []
    def execute(item, constraints):
        seen.append((item['id'], constraints))
        output = tmp_path / item['id']
        output.write_text(json.dumps(constraints))
        return [{'source': str(output), 'content': output.read_text()}]
    agent = CooperativeAgent(service, review['review_id'], execute)
    assert agent.run_next()['state'] == 'waiting'
    control = service.request_control(review['review_id'], 'pause')
    assert control['state'] == 'requested'
    assert agent.run_next()['state'] == 'paused'
    assert service.events(review['review_id'])[-1]['state'] == 'applied'
    service.request_control(review['review_id'], 'constraint', {'text': 'Keep compatibility'})
    service.request_control(review['review_id'], 'resume')
    service.submit_decisions(review['review_id'], 1, [decide(review, 'b')], 'second-before-first')
    assert agent.run_next()['state'] == 'waiting'
    service.submit_decisions(review['review_id'], 1, [decide(review, 'a', comment='Only src')], 'first')
    assert agent.run_next()['id'] == 'a'
    assert seen[0][1] == ['Keep compatibility', 'Only src']
    assert agent.run_next()['id'] == 'b'
    assert agent.run_next()['state'] == 'waiting'
    assert len(seen) == 2
    assert not (tmp_path/'c').exists()


def test_policy_preferences_dont_authorize_and_revocation_enforced(service):
    action = {'operation': 'edit', 'scope': 'src/a', 'reversible': True}
    assert evaluate({'preferences': {'detail': 'full'}}, action)['effect'] == 'ask'
    settings = {'rules': [{'id': 'src', 'operation': 'edit', 'scope': 'src/', 'reversible': True, 'effect': 'deny'}]}
    review = service.create_review(proposal())
    service.submit_decisions(review['review_id'], 1, [decide(review, 'a')], 'one')
    service.settings('default', settings)
    agent = CooperativeAgent(service, review['review_id'], lambda *_: pytest.fail('Revoked operation executed'))
    assert agent.run_next()['state'] == 'waiting'
    assert evaluate(settings, {'operation': 'edit', 'scope': '../src/a'})['effect'] == 'deny'
    assert evaluate(settings, {'operation': 'edit', 'scope': 'src-other/a'})['effect'] == 'ask'


def test_questions_replies_and_human_revision(service):
    review = service.create_review(proposal())
    question = service.ask_item_question(review['review_id'], 'a', 'Why?')
    service.publish_item_reply(review['review_id'], 'a', 'Evidence missing', category='missing', question_seq=question['seq'])
    revised = service.request_revision(review['review_id'], 1, 'a', {'scope': 'src/new', 'position': 2})
    assert revised['items'][1]['id'] == 'a'
    assert revised['items'][1]['action']['scope'] == 'src/new'
    assert service.events(review['review_id'])[-1]['kind'] == 'human_revision_requested'
    record(service, review['review_id'], 'opened', 'view')
    record(service, review['review_id'], 'hidden', 'view')
    assert summarize(service, review['review_id'])['questions'] == 1


def test_execution_result_belongs_to_started_revision(service):
    source={'items':[{'id':'a','scope':'src/old'}]}
    review=service.create_review(source)
    service.submit_decisions(review['review_id'],1,[decide(review,'a')],'one')
    def execute(item, constraints):
        service.revise_review(review['review_id'],{'items':[{'id':'a','scope':'src/new'}]},1)
        return [{'source':'old-scope','content':'completed'}]
    agent=CooperativeAgent(service,review['review_id'],execute)
    assert agent.run_next()['state']=='succeeded'
    last=service.events(review['review_id'])[-1]
    assert last['revision']==1
    assert last['fingerprint']==review['items'][0]['authorization_fingerprint']
    assert service.get_review(review['review_id'])['decisions']=={}
    assert agent.run_next()['state']=='waiting'


def test_pilot_requires_real_observations_and_reports_denominators(service):
    from agent_visual_bridge.evaluation import record_observation, pilot_report
    review=service.create_review({'items':[{'id':'a'}]})
    assert pilot_report(service,review['review_id'])['status']=='no_observations'
    sample={'participant':'test-fixture','task':'question','condition':'bridge','active_seconds':10,
            'interruptions':1,'understood_scope':True,'constraints_lost':0,
            'resume_attempts':1,'resume_successes':1,'effort':2}
    record_observation(service,review['review_id'],sample)
    report=pilot_report(service,review['review_id'])
    assert report['conditions']['bridge']['scope_comprehension_rate']==1
    assert report['comparable_tasks']==[]


def test_information_does_not_request_authorization(tmp_path):
    service = ReviewService(tmp_path/'info.db')
    review = service.create_review({'items':[{'id':'info','title':'Observation','interaction_kind':'inform'}]})
    assert review['state'] == 'published'
    revised = service.revise_review(review['review_id'], {'items':[{'id':'info','title':'New observation','interaction_kind':'inform'}]}, 1)
    assert revised['state'] == 'published'


def test_policy_rejects_noncanonical_paths():
    from agent_visual_bridge.policy import evaluate
    for scope in ['/src/a', 'src/../secret', 'src\\..\\secret', 'C:/src/file']:
        assert evaluate({}, {'operation':'edit','scope':scope})['effect'] == 'deny'
