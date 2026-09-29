from agent_visual_bridge.detector import ReportType, detect_report_type


def test_detect_explicit_type():
    assert detect_report_type(explicit_type="plan") == ReportType.PLAN
    assert detect_report_type(explicit_type="audit") == ReportType.AUDIT
    assert detect_report_type(explicit_type="review") == ReportType.REVIEW
    assert detect_report_type(explicit_type="decision") == ReportType.DECISION


def test_detect_from_title():
    assert detect_report_type(title="Audit de conformité Django") == ReportType.AUDIT
    assert detect_report_type(title="Plan d'action et roadmap des lots") == ReportType.PLAN
    assert detect_report_type(title="Code review de la PR #42") == ReportType.REVIEW
    assert detect_report_type(title="Matrice de décision architecturale") == ReportType.DECISION


def test_detect_from_data_structure():
    audit_data = {"items": [{"id": "1", "severity": "high", "status": "ko"}]}
    assert detect_report_type(data=audit_data) == ReportType.AUDIT

    plan_data = {"items": [{"id": "1", "lot": "Lot 1", "dependencies": ["lot-0"]}]}
    assert detect_report_type(data=plan_data) == ReportType.PLAN

    review_data = {"items": [{"id": "1", "file": "app.py", "diff": "+ print('hello')"}]}
    assert detect_report_type(data=review_data) == ReportType.REVIEW

    decision_data = {"items": [{"id": "1", "options": ["Option A", "Option B"]}]}
    assert detect_report_type(data=decision_data) == ReportType.DECISION
