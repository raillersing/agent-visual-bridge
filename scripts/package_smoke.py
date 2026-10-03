"""Run against an installed wheel without optional dependencies."""
import importlib.util
import tempfile
from pathlib import Path

from agent_visual_bridge import ReviewService, VisualBridge

assert importlib.util.find_spec('mcp') is None
with tempfile.TemporaryDirectory() as directory:
    service = ReviewService(Path(directory) / 'reviews.db')
    proposal = {'title': 'Wheel qualification', 'items': [{'id': 'a', 'title': 'Approve?'}]}
    review = service.create_review(proposal)
    item = review['items'][0]
    receipt = service.submit_decisions(review['review_id'], 1, [{'id': 'a', 'fingerprint': item['authorization_fingerprint'],
                                       'decision_kind': 'approve', 'constraints': ['Read-only']}], 'smoke')
    assert ReviewService(service.store.path).get_receipt(receipt['receipt_id']) == receipt
    html = VisualBridge.from_data(proposal).render_html()
    assert 'avb-proposal' in html and 'function collect()' in html
    assets = Path(__import__('agent_visual_bridge').__file__).parent
    assert (assets / 'assets/mcp-app.js').stat().st_size > 1000
    assert (assets / 'schemas/proposal.schema.json').is_file()
print('Minimal installed wheel: HTML, persistence, receipt, native assets and schemas OK')
