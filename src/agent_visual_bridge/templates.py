"""HTML Template and generation engine for Agent Visual Bridge.

Generates self-contained, zero-dependency, local-first interactive HTML dashboards.
Includes embedded CSS, JavaScript with DOM persistence, LocalStorage, filter system,
and support for direct POST submission to an ephemeral webhook server.
"""

from __future__ import annotations

import html
from typing import Any, Dict, List, Optional
from agent_visual_bridge.detector import ReportType


def render_html_report(
    title: str,
    report_type: ReportType,
    items: List[Dict[str, Any]],
    subtitle: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    server_port: Optional[int] = None,
) -> str:
    """Render a standalone, zero-dependency interactive HTML report."""
    metadata = metadata or {}
    server_port_js = server_port if server_port else "null"

    rendered_cards = []
    for idx, item in enumerate(items, 1):
        rendered_cards.append(_render_card(item, idx, report_type))

    cards_html = "\n".join(rendered_cards)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)} — Agent Visual Bridge</title>
<style>
  :root {{
    --bg: #090e17;
    --bg-surface: #101726;
    --card: #141e33;
    --card-alt: #1a2742;
    --line: #233456;
    --text: #f1f5f9;
    --text-muted: #94a3b8;
    --text-sub: #cbd5e1;
    --ok: #10b981;
    --ok-bg: rgba(16, 185, 129, 0.15);
    --warn: #f59e0b;
    --warn-bg: rgba(245, 158, 11, 0.15);
    --bad: #ef4444;
    --bad-bg: rgba(239, 68, 68, 0.15);
    --accent: #6366f1;
    --accent-bg: rgba(99, 102, 241, 0.15);
    --cyan: #38bdf8;
    --cyan-bg: rgba(56, 189, 248, 0.12);
    --remark-bg: #15233c;
    --remark-border: #3b82f6;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.6;
    padding-bottom: 120px;
  }}
  header {{
    background: linear-gradient(135deg, #0b1329 0%, #1e1b4b 50%, #082f49 100%);
    border-bottom: 1px solid var(--line);
    padding: 46px 24px 36px;
    text-align: center;
  }}
  .badge-type {{
    display: inline-block;
    color: var(--cyan);
    background: var(--cyan-bg);
    border: 1px solid rgba(56, 189, 248, 0.35);
    font-size: 0.75rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 2px;
    padding: 4px 16px;
    border-radius: 999px;
    margin-bottom: 12px;
  }}
  h1 {{
    font-size: 2.2rem;
    font-weight: 900;
    margin-bottom: 8px;
    background: linear-gradient(to right, #ffffff, #93c5fd, #c7d2fe);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .header-desc {{
    color: var(--text-muted);
    font-size: 1rem;
    max-width: 800px;
    margin: 0 auto;
  }}
  .stats {{
    display: flex;
    gap: 14px;
    justify-content: center;
    flex-wrap: wrap;
    margin-top: 26px;
  }}
  .stat {{
    background: var(--bg-surface);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 12px 22px;
    min-width: 140px;
    text-align: center;
  }}
  .stat .n {{ font-size: 1.8rem; font-weight: 800; line-height: 1.1; }}
  .stat .l {{ font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; }}
  .stat.total .n {{ color: var(--cyan); }}
  .stat.validated .n {{ color: var(--ok); }}
  .stat.adjusted .n {{ color: var(--warn); }}
  .stat.pending .n {{ color: var(--text-muted); }}

  .toolbar {{
    position: sticky;
    top: 0;
    z-index: 100;
    background: rgba(9, 14, 23, 0.95);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--line);
    padding: 10px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }}
  .toolbar-left, .toolbar-right {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }}
  .action-btn {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--card);
    border: 1px solid var(--line);
    color: var(--text);
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 700;
    cursor: pointer;
    transition: 0.15s;
  }}
  .action-btn:hover {{ background: var(--card-alt); border-color: var(--accent); }}
  .action-btn.apply {{
    background: #059669;
    border-color: #10b981;
    color: white;
    box-shadow: 0 2px 10px rgba(16, 185, 129, 0.3);
  }}
  .action-btn.apply:hover {{ background: #047857; }}
  .action-btn.primary {{ background: #2563eb; border-color: #3b82f6; color: white; }}
  .action-btn.primary:hover {{ background: #1d4ed8; }}

  .filter-btn {{
    background: transparent;
    border: 1px solid var(--line);
    color: var(--text-muted);
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 0.8rem;
    cursor: pointer;
    font-weight: 600;
  }}
  .filter-btn.active {{
    background: var(--accent-bg);
    border-color: var(--accent);
    color: #ffffff;
  }}
  .search-input {{
    background: var(--bg-surface);
    border: 1px solid var(--line);
    color: var(--text);
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.85rem;
    outline: none;
    width: 220px;
  }}
  .search-input:focus {{ border-color: var(--accent); }}

  .wrap {{
    max-width: 1060px;
    margin: 28px auto 0;
    padding: 0 20px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }}
  .card {{
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 22px;
    transition: 0.2s;
  }}
  .card:hover {{ border-color: rgba(99, 102, 241, 0.5); }}
  .card-top {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 14px;
    margin-bottom: 12px;
  }}
  .card-id-badge {{
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
    padding: 3px 10px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-muted);
  }}
  .card-title {{
    font-size: 1.15rem;
    font-weight: 700;
    color: #ffffff;
    margin-top: 4px;
  }}
  .tag {{
    font-size: 0.7rem;
    font-weight: 800;
    padding: 4px 10px;
    border-radius: 6px;
    text-transform: uppercase;
  }}
  .tag.ok {{ background: var(--ok-bg); color: var(--ok); }}
  .tag.warn {{ background: var(--warn-bg); color: var(--warn); }}
  .tag.bad {{ background: var(--bad-bg); color: var(--bad); }}

  .card-body {{
    font-size: 0.92rem;
    color: var(--text-sub);
    margin-bottom: 16px;
    line-height: 1.6;
  }}
  .card-body p {{ margin-bottom: 8px; }}
  .card-body pre, .card-body code {{
    background: rgba(0, 0, 0, 0.4);
    color: #93c5fd;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.85em;
  }}
  .card-body pre {{
    padding: 10px 14px;
    overflow-x: auto;
    margin: 8px 0;
  }}

  .input-zone {{
    background: var(--remark-bg);
    border: 1px solid var(--remark-border);
    border-radius: 12px;
    padding: 16px 20px;
  }}
  .input-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
    flex-wrap: wrap;
  }}
  .input-title {{
    font-size: 0.85rem;
    font-weight: 700;
    color: #93c5fd;
  }}
  .status-select {{
    background: var(--bg-surface);
    border: 1px solid var(--line);
    color: #ffffff;
    padding: 5px 10px;
    border-radius: 6px;
    font-size: 0.82rem;
    font-weight: 700;
    outline: none;
    cursor: pointer;
  }}
  .user-textarea {{
    width: 100%;
    min-height: 70px;
    background: rgba(9, 14, 23, 0.9);
    border: 1px solid rgba(59, 130, 246, 0.3);
    border-radius: 8px;
    color: #ffffff;
    font-family: inherit;
    font-size: 0.9rem;
    padding: 10px 14px;
    outline: none;
    resize: vertical;
  }}
  .user-textarea:focus {{
    border-color: #60a5fa;
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25);
  }}

  .toast {{
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: #0f172a;
    border: 1px solid var(--ok);
    color: #ffffff;
    padding: 12px 20px;
    border-radius: 10px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    font-size: 0.9rem;
    font-weight: 700;
    z-index: 1000;
    opacity: 0;
    transform: translateY(20px);
    transition: 0.3s;
    pointer-events: none;
  }}
  .toast.show {{ opacity: 1; transform: translateY(0); }}
</style>
</head>
<body>

<header>
  <div class="badge-type">{html.escape(report_type.value)} · Agent Visual Bridge</div>
  <h1>{html.escape(title)}</h1>
  <p class="header-desc">{html.escape(subtitle or "Veuillez examiner les points ci-dessous, ajuster les statuts et saisir vos remarques.")}</p>

  <div class="stats">
    <div class="stat total"><div class="n" id="stat-total">{len(items)}</div><div class="l">Total Points</div></div>
    <div class="stat validated"><div class="n" id="stat-validated">0</div><div class="l">Validés</div></div>
    <div class="stat adjusted"><div class="n" id="stat-adjusted">0</div><div class="l">À Ajuster</div></div>
    <div class="stat pending"><div class="n" id="stat-pending">{len(items)}</div><div class="l">En Attente</div></div>
  </div>
</header>

<div class="toolbar">
  <div class="toolbar-left">
    <button class="action-btn apply" onclick="submitToAgent()" title="Valider et envoyer les instructions directement à l'agent IA">
      🚀 Valider & Envoyer à l'Agent
    </button>
    <button class="action-btn primary" onclick="copyForAgent()" title="Copier le mandat prêt à coller dans le chat">
      📋 Copier pour l'Agent
    </button>
    <button class="action-btn" onclick="saveHtml()" title="Enregistrer le fichier HTML avec vos réponses figées sur disque">
      💾 Sauvegarder HTML
    </button>
    <button class="action-btn" onclick="exportMarkdown()" title="Télécharger le compte-rendu au format Markdown">
      📥 Exporter MD
    </button>
  </div>
  <div class="toolbar-right">
    <div class="filter-group">
      <button class="filter-btn active" onclick="setFilter('all')">Tous</button>
      <button class="filter-btn" onclick="setFilter('validated')">Validés</button>
      <button class="filter-btn" onclick="setFilter('adjusted')">À Ajuster</button>
      <button class="filter-btn" onclick="setFilter('pending')">En Attente</button>
    </div>
    <input type="text" class="search-input" id="searchBox" placeholder="Rechercher..." oninput="onSearch(this.value)">
  </div>
</div>

<main class="wrap" id="cardsContainer">
{cards_html}
</main>

<div class="toast" id="toast">Action effectuée avec succès !</div>

<script>
const REPORT_TYPE = "{report_type.value}";
const SERVER_PORT = {server_port_js};
const STORAGE_KEY = "AVB_" + window.location.pathname;

let activeFilter = 'all';
let searchQuery = '';

function showToast(msg, duration = 3000) {{
  const toast = document.getElementById('toast');
  toast.innerText = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}}

function updateCounters() {{
  const cards = document.querySelectorAll('.card');
  let valCount = 0, adjCount = 0, pendCount = 0;

  cards.forEach(card => {{
    const id = card.getAttribute('data-id');
    const sel = document.getElementById('status-' + id);
    const val = sel ? sel.value : 'pending';
    if (val === 'validate') valCount++;
    else if (val === 'adjust') adjCount++;
    else pendCount++;
  }});

  document.getElementById('stat-validated').innerText = valCount;
  document.getElementById('stat-adjusted').innerText = adjCount;
  document.getElementById('stat-pending').innerText = pendCount;
}}

function onInputUpdate(cardId) {{
  updateCounters();
  saveToLocalStorage();
}}

function saveToLocalStorage() {{
  const data = {{}};
  document.querySelectorAll('.card').forEach(card => {{
    const id = card.getAttribute('data-id');
    const sel = document.getElementById('status-' + id);
    const txt = document.getElementById('remark-' + id);
    data[id] = {{
      status: sel ? sel.value : 'pending',
      remark: txt ? txt.value : ''
    }};
  }});
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}}

function loadFromLocalStorage() {{
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return;
  try {{
    const data = JSON.parse(raw);
    Object.keys(data).forEach(id => {{
      const sel = document.getElementById('status-' + id);
      const txt = document.getElementById('remark-' + id);
      if (sel && data[id].status) sel.value = data[id].status;
      if (txt && data[id].remark) txt.value = data[id].remark;
    }});
  }} catch (e) {{}}
  updateCounters();
}}

function collectDecisions() {{
  const results = [];
  document.querySelectorAll('.card').forEach(card => {{
    const id = card.getAttribute('data-id');
    const titleEl = card.querySelector('.card-title');
    const title = titleEl ? titleEl.innerText : id;
    const sel = document.getElementById('status-' + id);
    const txt = document.getElementById('remark-' + id);

    results.push({{
      id: id,
      title: title,
      status: sel ? sel.value : 'pending',
      remark: txt ? txt.value.trim() : ''
    }});
  }});
  return results;
}}

function buildMandateMarkdown(decisions) {{
  let md = "# Mandat d'Arbitrage — " + document.title + "\\n\\n";
  const validated = decisions.filter(d => d.status === 'validate');
  const adjusted = decisions.filter(d => d.status === 'adjust');
  const pending = decisions.filter(d => d.status === 'pending');

  md += "## Résumé des Décisions :\\n";
  md += "- ✅ **Validés sans modification :** " + validated.length + "\\n";
  md += "- ✏️ **Validés avec ajustements :** " + adjusted.length + "\\n";
  md += "- ⏳ **En attente / Non traités :** " + pending.length + "\\n\\n";

  if (adjusted.length > 0) {{
    md += "### ✏️ Consignes & Ajustements Prioritaires :\\n";
    adjusted.forEach(d => {{
      md += "- **[" + d.id + "] " + d.title + "**\\n";
      md += "  > " + (d.remark || "(Aucune consigne spécifiée)") + "\\n";
    }});
    md += "\\n";
  }}

  if (validated.length > 0) {{
    md += "### ✅ Points Validés :\\n";
    validated.forEach(d => {{
      md += "- **[" + d.id + "]** " + d.title + (d.remark ? " — *Remarque : " + d.remark + "*" : "") + "\\n";
    }});
    md += "\\n";
  }}

  return md;
}}

function copyForAgent() {{
  const decisions = collectDecisions();
  const md = buildMandateMarkdown(decisions);
  navigator.clipboard.writeText(md).then(() => {{
    showToast("📋 Mandat copié dans le presse-papier !");
  }}).catch(() => {{
    showToast("⚠️ Impossible d'accéder au presse-papier.");
  }});
}}

function saveHtml() {{
  // Mutate DOM attributes before saving so file on disk preserves values
  document.querySelectorAll('.card').forEach(card => {{
    const id = card.getAttribute('data-id');
    const sel = document.getElementById('status-' + id);
    const txt = document.getElementById('remark-' + id);

    if (sel) {{
      Array.from(sel.options).forEach(opt => {{
        if (opt.value === sel.value) opt.setAttribute('selected', 'selected');
        else opt.removeAttribute('selected');
      }});
    }}
    if (txt) {{
      txt.innerHTML = txt.value.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }}
  }});

  const htmlContent = "<!DOCTYPE html>\\n" + document.documentElement.outerHTML;
  const blob = new Blob([htmlContent], {{ type: "text/html;charset=utf-8" }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = window.location.pathname.split('/').pop() || "report.html";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast("💾 Fichier HTML sauvegardé ! Remplacez le fichier existant.");
}}

function exportMarkdown() {{
  const decisions = collectDecisions();
  const md = buildMandateMarkdown(decisions);
  const blob = new Blob([md], {{ type: "text/markdown;charset=utf-8" }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = "mandate-" + REPORT_TYPE + ".md";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast("📥 Mandat Markdown exporté !");
}}

async function submitToAgent() {{
  const decisions = collectDecisions();
  const md = buildMandateMarkdown(decisions);

  if (SERVER_PORT) {{
    try {{
      const resp = await fetch("http://localhost:" + SERVER_PORT + "/api/submit", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ decisions: decisions, markdown: md }})
      }});
      if (resp.ok) {{
        showToast("🚀 Transmis avec succès à l'agent !", 4000);
        return;
      }}
    }} catch (e) {{}}
  }}

  // Fallback if no server is running
  copyForAgent();
  saveHtml();
}}

function setFilter(filter) {{
  activeFilter = filter;
  document.querySelectorAll('.filter-btn').forEach(btn => {{
    btn.classList.toggle('active', btn.innerText.toLowerCase().includes(filter));
  }});
  applyFilters();
}}

function onSearch(query) {{
  searchQuery = query.toLowerCase().trim();
  applyFilters();
}}

function applyFilters() {{
  const cards = document.querySelectorAll('.card');
  cards.forEach(card => {{
    const id = card.getAttribute('data-id');
    const sel = document.getElementById('status-' + id);
    const status = sel ? sel.value : 'pending';
    const text = card.innerText.toLowerCase();

    let matchesFilter = true;
    if (activeFilter === 'validated') matchesFilter = (status === 'validate');
    else if (activeFilter === 'adjusted') matchesFilter = (status === 'adjust');
    else if (activeFilter === 'pending') matchesFilter = (status === 'pending');

    let matchesSearch = !searchQuery || text.includes(searchQuery);

    card.style.display = (matchesFilter && matchesSearch) ? 'block' : 'none';
  }});
}}

window.addEventListener('DOMContentLoaded', () => {{
  loadFromLocalStorage();
}});
</script>

</body>
</html>"""


def _render_card(item: Dict[str, Any], idx: int, report_type: ReportType) -> str:
    """Render a single interactive card."""
    item_id = str(item.get("id") or f"item-{idx}")
    title = str(item.get("title") or f"Élément {idx}")
    description = str(item.get("description") or item.get("desc") or "")
    severity = str(item.get("severity") or item.get("verdict") or "").lower()
    initial_status = str(item.get("status") or "pending").lower()
    initial_remark = str(item.get("remark") or item.get("comment") or "")

    tag_class = "ok" if severity in ["ok", "low", "conforme"] else ("bad" if severity in ["critical", "high", "ko", "bloquant"] else "warn")
    tag_label = severity.upper() if severity else report_type.value.upper()

    # Format description with markdown backticks to <code>
    desc_html = html.escape(description, quote=False)
    # Simple formatting for inline code
    parts = desc_html.split("`")
    if len(parts) > 1:
        formatted = []
        for i, p in enumerate(parts):
            formatted.append(f"<code>{p}</code>" if i % 2 == 1 else p)
        desc_html = "".join(formatted)

    selected_validate = "selected" if initial_status == "validate" else ""
    selected_adjust = "selected" if initial_status in ["adjust", "modify"] else ""
    selected_pending = "selected" if initial_status not in ["validate", "adjust", "modify"] else ""

    return f"""  <article class="card" data-id="{html.escape(item_id)}">
    <div class="card-top">
      <div>
        <span class="card-id-badge">{html.escape(item_id)}</span>
        <h2 class="card-title">{html.escape(title, quote=False)}</h2>
      </div>
      <span class="tag {tag_class}">{html.escape(tag_label)}</span>
    </div>
    <div class="card-body">
      <p>{desc_html}</p>
    </div>
    <div class="input-zone">
      <div class="input-header">
        <span class="input-title">💬 Votre Décision & Remarques :</span>
        <select id="status-{html.escape(item_id)}" class="status-select" onchange="onInputUpdate('{html.escape(item_id)}')">
          <option value="pending" {selected_pending}>⏳ En attente</option>
          <option value="validate" {selected_validate}>✅ Validé</option>
          <option value="adjust" {selected_adjust}>✏️ À ajuster</option>
        </select>
      </div>
      <textarea id="remark-{html.escape(item_id)}" class="user-textarea" placeholder="Saisissez ici vos consignes ou ajustements pour cet élément..." oninput="onInputUpdate('{html.escape(item_id)}')">{html.escape(initial_remark)}</textarea>
    </div>
  </article>"""
