from agent_visual_bridge.parser import parse_html_report


def test_parse_html_with_user_feedback():
    sample_html = """<!DOCTYPE html>
<html>
<body>
  <article class="card" data-id="p1">
    <h2 class="card-title">Première Tâche</h2>
    <select id="status-p1">
      <option value="validate" selected>Validé</option>
      <option value="adjust">À ajuster</option>
    </select>
    <textarea id="remark-p1">Très bien, conforme aux attentes.</textarea>
  </article>

  <article class="card" data-id="p2">
    <h2 class="card-title">Deuxième Tâche</h2>
    <select id="status-p2">
      <option value="validate">Validé</option>
      <option value="adjust" selected>À ajuster</option>
    </select>
    <textarea id="remark-p2">Changer la couleur du bouton en rouge.</textarea>
  </article>
</body>
</html>"""

    result = parse_html_report(sample_html)

    summary = result["summary"]
    assert summary["total"] == 2
    assert summary["validated"] == 1
    assert summary["adjusted"] == 1
    assert summary["pending"] == 0

    decisions = {d["id"]: d for d in result["decisions"]}
    assert decisions["p1"]["status"] == "validate"
    assert decisions["p1"]["remark"] == "Très bien, conforme aux attentes."
    assert decisions["p2"]["status"] == "adjust"
    assert decisions["p2"]["remark"] == "Changer la couleur du bouton en rouge."

    assert "Deuxième Tâche" in result["mandate_markdown"]
    assert "Changer la couleur du bouton en rouge." in result["mandate_markdown"]
