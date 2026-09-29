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
