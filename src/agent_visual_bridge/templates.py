"""Self-contained HTML views over the versioned review contract."""
from __future__ import annotations

import html
import json
from pathlib import Path

from .models import normalize
from .policy import evaluate

ASSETS = Path(__file__).parent / 'assets'


def safe_json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def escape(value):
    return html.escape(str(value))


def render_review(review, runtime=None, settings=None):
    cards = []
    decisions = review.get('decisions', {})
    for item in review['items']:
        key = item['id']
        decision = decisions.get(key, {})
        selected = decision.get('decision_kind', 'pending')
        policy = evaluate(settings or {}, item.get('action') or {'operation': 'task', 'scope': 'workspace'}) if item['interaction_kind'] == 'authorize' else None
        policy_ui = (f'<p class="policy-reason">Règle applicable : {escape(policy["effect"])} · {escape(policy["reason"])}</p>'
                     if policy else '<p>Information ou clarification : aucune permission d’exécution demandée.</p>')
        kinds = [('pending', 'En attente'), ('defer', 'Différer'), ('reject', 'Refuser'),
                 ('request_changes', 'Demander une révision')]
        if item['interaction_kind'] == 'authorize':
            kinds.insert(1, ('approve', 'Autoriser les actions présentées'))
        elif item['interaction_kind'] == 'clarify':
            kinds.insert(1, ('answer', 'Répondre'))
            if item['options']:
                kinds.insert(2, ('choose', 'Choisir une option'))
        options = ''.join(f'<option value="{value}" {"selected" if value == selected else ""}>{label}</option>'
                          for value, label in kinds)
        option_ui = ''.join(f'<label class="choice"><input type="radio" name="choice-{key}" value="{escape(opt["id"])}" '
                            f'{"checked" if opt["id"] in decision.get("options", []) else ""}>'
                            f'{escape(opt["label"])} <small>{escape(opt.get("description", ""))}</small></label>'
                            for opt in item['options'])
        details = []
        for field, label in [('severity', 'Sévérité'), ('verdict', 'Constat'), ('lot', 'Lot'),
                             ('scope', 'Périmètre'), ('allowed_files', 'Fichiers autorisés'),
                             ('forbidden_files', 'Fichiers exclus'), ('dependencies', 'Dépendances'),
                             ('constraints', 'Contraintes'), ('action', 'Action'),
                             ('tradeoffs', 'Compromis'), ('checks', 'Vérifications')]:
            if item.get(field):
                val = item[field]
                val = json.dumps(val, ensure_ascii=False, indent=2) if isinstance(val, (dict, list)) else str(val)
                details.append(f'<div><strong>{label}</strong><pre>{escape(val)}</pre></div>')
        if item.get('diff'):
            lines = item['diff'].splitlines()
            details.append('<strong>Diff</strong><pre class="diff">' + '\n'.join(
                f'<span class="{"added" if line.startswith("+") else "removed" if line.startswith("-") else "context"}">{escape(line)}</span>'
                for line in lines) + '</pre>')
        evidence = ''.join(f'<li><strong>{escape(ev.get("kind", "agent_observation"))}</strong> — '
                           f'{escape(ev["source"])}<pre>{escape(ev.get("content", ev.get("summary", "")))}</pre></li>'
                           for ev in item['evidence'])
        unknowns = ''.join(f'<li>{escape(u)}</li>' for u in item['unknowns'])
        cards.append(f'''<article class="card" data-id="{escape(key)}">
          <span class="badge">{escape(item['interaction_kind'])} · {escape(key)}</span>
          <h2 class="card-title">{escape(item['title'])}</h2>
          {policy_ui}<p class="question">{escape(item['question'])}</p><p>{escape(item['description'])}</p>
          <p><strong>Recommandation :</strong> {escape(item['recommendation'] or 'Non fournie')}</p>
          <p><strong>Conséquence du choix :</strong> {escape(item['consequences'] or 'À préciser avant autorisation si nécessaire')}</p>
          <details><summary>Preuves, périmètre et informations manquantes</summary>
            {''.join(details)}<h3>Preuves et provenance</h3><ul>{evidence or '<li>Aucune preuve fournie</li>'}</ul>
            <h3>Informations manquantes</h3><ul>{unknowns or '<li>Aucune information manquante déclarée</li>'}</ul></details>
          <div class="choices">{option_ui}</div>
          <label for="status-{key}">Votre décision</label><select id="status-{key}" class="status-select">{options}</select>
          <label for="answer-{key}">Réponse à la question</label><input id="answer-{key}" class="answer" value="{escape(decision.get('answer', ''))}">
          <label for="remark-{key}">Remarque ou demande de révision</label>
          <textarea id="remark-{key}" class="user-textarea">{escape(decision.get('comment', ''))}</textarea>
          <label for="constraints-{key}">Contraintes, une par ligne</label>
          <textarea id="constraints-{key}" class="constraints">{escape(chr(10).join(decision.get('constraints', [])))}</textarea>
          <details class="conversation"><summary>Questions et réponses sur ce point</summary>
            <div class="thread" aria-live="polite"></div><label for="question-{key}">Question à l’agent</label>
            <input id="question-{key}" class="ask-message" placeholder="Pourquoi ? Quelle preuve ? Quelle alternative ?">
            <div class="quick-questions"><button type="button" data-question="Pourquoi cette recommandation ?">Pourquoi ?</button><button type="button" data-question="Quelle preuve soutient cette recommandation ?">Preuve ?</button><button type="button" data-question="Quelle alternative et quels compromis ?">Alternative ?</button></div><button type="button" class="ask">Poser la question</button>
          </details><details><summary>Ajuster le périmètre, les options ou l’ordre</summary>
          <label for="scope-{key}">Périmètre proposé</label><input id="scope-{key}" class="edit-scope" value="{escape(item.get('scope', ''))}">
          <label for="deps-{key}">Dépendances, identifiants séparés par des virgules</label><input id="deps-{key}" class="edit-deps" value="{escape(','.join(item['dependencies']))}">
          <label for="position-{key}">Position dans le plan</label><input id="position-{key}" class="edit-position" type="number" min="1" max="{len(review['items'])}" value="{len(cards)+1}">
          <label for="options-{key}">Options proposées, une par ligne</label><textarea id="options-{key}" class="edit-options">{escape(chr(10).join(opt['label'] for opt in item['options']))}</textarea>
          <button class="revise" type="button">Présenter une nouvelle version</button><p>Les accords affectés devront être réexaminés.</p>
          </details><p class="execution" aria-live="polite"></p>
        </article>''')
    prefs = (settings or {}).get('preferences', {})
    runtime = {**(runtime or {}), 'preferences': prefs}
    css = (ASSETS / 'style.css').read_text()
    js = (ASSETS / 'review.js').read_text()
    return f'''<!DOCTYPE html>
<html lang="{escape(prefs.get('language', 'fr'))}"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(review['title'])} — Agent Visual Bridge</title><style>{css}</style></head>
<body><header><span class="badge">{escape(review['report_type'])} · Agent Visual Bridge</span><h1>{escape(review['title'])}</h1>
<p>{escape(review.get('subtitle', ''))}</p><p id="summary" aria-live="polite"></p></header>
<nav aria-label="Actions de revue"><button id="submit">Envoyer mes décisions</button><button id="preview">Prévisualiser le mandat</button>
<button id="export">Exporter JSON</button><button id="save">Sauvegarder HTML</button><button id="copy">Copier le mandat</button>
<label for="filter">Afficher</label><select id="filter"><option value="all">Tous</option><option value="pending">En attente</option><option value="decided">Décidés</option></select>
<label for="search">Rechercher</label><input id="search" type="search"></nav>
<aside id="controls"><h2>Pilotage de l’agent</h2><p id="capabilities">Aucun moteur connecté</p>
<button data-control="pause">Pause</button><button data-control="resume">Reprendre</button><button data-control="stop">Arrêter</button>
<label for="constraint">Nouvelle contrainte</label><input id="constraint"><button data-control="constraint">Transmettre la contrainte</button>
<label for="priority">Priorité : identifiants séparés par des virgules</label><input id="priority"><button data-control="priority">Changer la priorité</button>
<p id="control-status" aria-live="polite"></p><p id="execution-summary" aria-live="polite"></p></aside>
<main>{''.join(cards)}</main><aside><h2>Modifications entre versions</h2><div id="changes">Première version</div>
<details><summary>Préférences du projet et règles explicites</summary><p>Les préférences de présentation ne changent pas les permissions.</p>
<label for="settings">Configuration JSON</label><textarea id="settings">{escape(json.dumps(settings or {}, ensure_ascii=False, indent=2))}</textarea>
<button id="settings-save">Enregistrer la configuration</button></details></aside>
<dialog id="mandate"><h2>Décisions à transmettre</h2><pre id="mandate-text"></pre><button id="confirm">Confirmer l’envoi</button><button id="close-dialog">Fermer</button></dialog>
<p id="notice" role="status" aria-live="polite"></p>
<script id="avb-proposal" type="application/json">{safe_json(review)}</script>
<script id="avb-feedback" type="application/json">null</script>
<script id="avb-runtime">const AVB_RUNTIME = {safe_json(runtime or {})};</script>
<script>const REPORT_TYPE = {safe_json(review['report_type'])};\n{js}</script></body></html>'''


def render_html_report(title, report_type, items, subtitle='', metadata=None, server_port=None):
    proposal = normalize({'title': title, 'subtitle': subtitle, 'items': items, 'metadata': metadata or {}},
                         report_type=report_type.value)
    return render_review(proposal)


def render_app_resource():
    bundle = (ASSETS / 'mcp-app.js').read_text()
    return '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body><p>Chargement de la revue…</p><script>' + bundle.replace('</script', '<\\/script') + '</script></body></html>'
