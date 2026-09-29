from agent_visual_bridge.detector import ReportType
from agent_visual_bridge.templates import render_html_report


def test_render_html_report_basic():
    items = [
        {
            "id": "point-1",
            "title": "Vérification des droits d'accès",
            "description": "Les permissions Django doivent être strictes.",
            "severity": "high",
            "status": "pending",
        }
    ]
    html = render_html_report(
        title="Audit de Sécurité",
        report_type=ReportType.AUDIT,
        items=items,
        subtitle="Vérification des règles de permissions",
    )

    assert "<!DOCTYPE html>" in html
    assert "Audit de Sécurité" in html
    assert "point-1" in html
    assert "Vérification des droits d'accès" in html
    assert "status-point-1" in html
    assert "remark-point-1" in html
    assert "REPORT_TYPE = \"audit\"" in html
