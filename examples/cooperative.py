"""Run a real, reversible local executor after an explicit browser decision.

python examples/cooperative.py --db /tmp/bridge-example.db
No permission is created programmatically.
"""
import argparse
from pathlib import Path
import time

from agent_visual_bridge import ReviewService, CooperativeAgent
from agent_visual_bridge.api import LocalServer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='example-reviews.sqlite3')
    args = parser.parse_args()
    service = ReviewService(args.db)
    artifact = Path(args.db).resolve().parent / 'approved-summary.txt'
    review = service.create_review({'title': 'Write a local summary', 'report_type': 'plan', 'items': [
        {'id': 'summary', 'title': 'Create approved-summary.txt next to the example database',
         'scope': artifact.name, 'consequences': 'Creates one text file containing your instructions',
         'action': {'operation': 'write_summary', 'scope': artifact.name, 'reversible': True}}]})

    def execute(item, constraints):
        content = '\n'.join(constraints) or 'Explicitly approved local example'
        artifact.write_text(content, encoding='utf-8')
        assert artifact.read_text(encoding='utf-8') == content
        return [{'kind': 'tool_result', 'source': str(artifact), 'content': content, 'verification': 'disk reread matched'}]

    worker = CooperativeAgent(service, review['review_id'], execute)
    with LocalServer(service, review['review_id']) as server:
        print(server.url, flush=True)
        while True:
            result = worker.run_next()
            if result['state'] in {'succeeded', 'failed', 'closed', 'stopped'}:
                print(result)
                break
            time.sleep(0.2)


if __name__ == '__main__':
    main()
