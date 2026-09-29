import tempfile
from pathlib import Path
from agent_visual_bridge.core import VisualBridge
from agent_visual_bridge.detector import ReportType


def test_visual_bridge_save_and_read():
    items = [
        {"id": "task-a", "title": "Setup Docker", "status": "pending"},
        {"id": "task-b", "title": "Run Migrations", "status": "pending"},
    ]
    bridge = VisualBridge("Project Setup", items, report_type=ReportType.PLAN)

    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = Path(tmpdir) / "report.html"
        bridge.save_html(out_file)

        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "Project Setup" in content
        assert "task-a" in content

        # Now simulate user editing the HTML
        edited_content = content.replace(
            '<textarea id="remark-task-a" class="user-textarea" placeholder="Saisissez ici vos consignes ou ajustements pour cet élément..." oninput="onInputUpdate(\'task-a\')"></textarea>',
            '<textarea id="remark-task-a" class="user-textarea" oninput="onInputUpdate(\'task-a\')">Utiliser compose v2.</textarea>'
        ).replace(
            '<option value="adjust" >',
            '<option value="adjust" selected>',
            1
        )
        out_file.write_text(edited_content, encoding="utf-8")

        # Parse back
        feedback = VisualBridge.read_feedback(out_file)
        assert feedback["summary"]["adjusted"] == 1
        adj_item = feedback["adjusted"][0]
        assert adj_item["id"] == "task-a"
        assert adj_item["remark"] == "Utiliser compose v2."
