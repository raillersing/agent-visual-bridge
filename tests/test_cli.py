import os
import subprocess
import sys
import json
import tempfile
from pathlib import Path
from agent_visual_bridge.cli import main


def test_cli_init():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_json = Path(tmpdir) / "audit_template.json"
        exit_code = main(["init", "audit", "-o", str(out_json)])
        assert exit_code == 0
        assert out_json.exists()

        data = json.loads(out_json.read_text(encoding="utf-8"))
        assert "items" in data
        assert len(data["items"]) >= 1


def test_cli_utf8_proposal_and_receipt_import(tmp_path, capsys):
    database = tmp_path / 'reviews.db'
    proposal = tmp_path / 'proposal.json'
    title = 'Révision du périmètre — hébergement'
    proposal.write_text(json.dumps({'title': title, 'items': [{'id': 'a', 'title': title}]},
                                   ensure_ascii=False), encoding='utf-8')
    assert main(['--db', str(database), 'create', str(proposal)]) == 0
    review = json.loads(capsys.readouterr().out)
    assert review['title'] == title
    feedback = {'review_id': review['review_id'], 'revision': 1, 'submitted_at': '2026-10-05T00:00:00Z',
                'request_key': 'utf8-import', 'decisions': [{'id': 'a', 'decision_kind': 'approve',
                    'fingerprint': review['items'][0]['authorization_fingerprint'], 'comment': title}]}
    exported = tmp_path / 'decisions.json'
    exported.write_text(json.dumps(feedback, ensure_ascii=False), encoding='utf-8')
    assert main(['--db', str(database), 'submit', review['review_id'], str(exported)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt['decisions'][0]['comment'] == title


def test_cli_auto_and_read():
    with tempfile.TemporaryDirectory() as tmpdir:
        input_json = Path(tmpdir) / "plan.json"
        output_html = Path(tmpdir) / "plan.html"

        input_json.write_text(json.dumps({
            "title": "Roadmap v1",
            "items": [
                {"id": "step-1", "title": "Database schema", "lot": "Lot 1"}
            ]
        }))

        exit_code = main(["auto", str(input_json), "-o", str(output_html), "--no-open"])
        assert exit_code == 0
        assert output_html.exists()

        # Read back
        exit_code_read = main(["read", str(output_html)])
        assert exit_code_read == 0


def test_cli_lifecycle_and_explicit_import(tmp_path):
    database = tmp_path / 'reviews.db'
    proposal = tmp_path / 'proposal.json'
    proposal.write_text(json.dumps({'items': [{'id': 'a', 'title': 'Confirm scope'}]}))

    def cli(*args, expected=0):
        result = subprocess.run([sys.executable, '-m', 'agent_visual_bridge', '--db', str(database), *args],
                                capture_output=True, text=True, env=os.environ.copy(), timeout=15)
        assert result.returncode == expected, result.stderr
        return json.loads(result.stdout) if expected == 0 else result

    review = cli('create', str(proposal), '-o', str(tmp_path / 'nested/review.html'))
    assert cli('get', review['review_id'])['state'] == 'awaiting_input'
    export = tmp_path / 'decisions.json'
    export.write_text(json.dumps({'review_id': review['review_id'], 'revision': 1, 'request_key': 'import-once',
                     'submitted_at': '2026-10-02T00:00:00Z', 'decisions': [{'id': 'a',
                     'fingerprint': review['items'][0]['authorization_fingerprint'], 'decision_kind': 'approve',
                     'comment': 'Preserve public API', 'constraints': ['No database migration']}]}))
    receipt = cli('submit', review['review_id'], str(export))
    assert cli('submit', review['review_id'], str(export)) == receipt
    assert cli('receipt', receipt['receipt_id']) == receipt
    assert receipt['decisions'][0]['constraints'] == ['No database migration']
    assert receipt['provenance'] == 'imported-artifact-unverified'
    export.write_text(json.dumps({'review_id': review['review_id'], 'decisions': []}))
    rejected = cli('submit', review['review_id'], str(export), expected=1)
    assert 'Explicit submission' in rejected.stderr
