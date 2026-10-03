"""Published schemas accept actual proposals and immutable receipts."""
import json
from pathlib import Path

import pytest

from agent_visual_bridge import ReviewService

jsonschema = pytest.importorskip('jsonschema')


@pytest.mark.parametrize('kind', ['audit', 'plan', 'review', 'decision'])
def test_published_contracts(kind, tmp_path):
    package = Path(__import__('agent_visual_bridge').__file__).parent
    root = Path(__file__).resolve().parents[1]
    proposal = json.loads((root/'examples'/f'{kind}.json').read_text())
    proposal_schema = json.loads((package/'schemas/proposal.schema.json').read_text())
    submission_schema = json.loads((package/'schemas/submission.schema.json').read_text())
    jsonschema.Draft202012Validator.check_schema(proposal_schema)
    jsonschema.Draft202012Validator.check_schema(submission_schema)
    jsonschema.validate(proposal, proposal_schema)
    service = ReviewService(tmp_path/'schemas.db')
    review = service.create_review(proposal)
    jsonschema.validate(review, proposal_schema)
    item = review['items'][0]
    decision = {'id': item['id'], 'fingerprint': item['authorization_fingerprint'],
                'decision_kind': 'choose' if kind == 'decision' else 'approve',
                'options': [item['options'][0]['id']] if kind == 'decision' else [],
                'constraints': ['Keep public API'], 'comment': 'Reviewed example'}
    submission = {'review_id': review['review_id'], 'revision': 1, 'request_key': 'schema', 'decisions': [decision]}
    jsonschema.validate(submission, submission_schema)
    receipt = service.submit_decisions(review['review_id'], 1, [decision], 'schema')
    jsonschema.validate(receipt, submission_schema)
