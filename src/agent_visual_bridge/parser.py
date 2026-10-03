"""Parser module for Agent Visual Bridge.

Zero-dependency HTML parser using standard library `html.parser` to extract
human decisions, remarks, statuses, and options from saved HTML artifacts.
"""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class FeedbackHTMLParser(HTMLParser):
    """Parses an Agent Visual Bridge HTML file to extract user inputs."""

    def __init__(self) -> None:
        super().__init__()
        self.cards: Dict[str, Dict[str, Any]] = {}
        self.current_card_id: Optional[str] = None
        self.current_tag: Optional[str] = None
        self.current_id: Optional[str] = None

        self._in_title = False
        self._in_textarea = False
        self._textarea_buffer: List[str] = []
        self._title_buffer: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        attr_dict = dict(attrs)
        self.current_tag = tag

        # Track card container
        if tag in ["article", "div"] and "data-id" in attr_dict:
            card_id = attr_dict["data-id"]
            self.current_card_id = card_id
            if card_id not in self.cards:
                self.cards[card_id] = {
                    "id": card_id,
                    "title": "",
                    "status": "pending",
                    "remark": "",
                    "options": [],
                }

        # Track card title
        classes = attr_dict.get("class", "")
        if self.current_card_id and ("card-title" in classes or "pillar-title" in classes):
            self._in_title = True
            self._title_buffer = []

        # Track select dropdown and selected option
        if tag == "option" and self.current_card_id:
            parent_select_id = self.current_id or ""
            is_selected = "selected" in attr_dict or attr_dict.get("selected") is not None
            val = attr_dict.get("value", "")
            if is_selected and ("status-" in parent_select_id or val in ["validate", "adjust", "pending", "reject"]):
                self.cards[self.current_card_id]["status"] = val

        if tag == "select":
            self.current_id = attr_dict.get("id")

        # Track textarea
        if tag == "textarea" and self.current_card_id and (attr_dict.get("id") or "").startswith("remark-"):
            self._in_textarea = True
            self._textarea_buffer = []
            self.current_id = attr_dict.get("id")

        # Track checked radios or checkboxes
        if tag == "input" and self.current_card_id:
            input_type = attr_dict.get("type", "")
            is_checked = "checked" in attr_dict or attr_dict.get("checked") is not None
            if is_checked and input_type in ["radio", "checkbox"]:
                val = attr_dict.get("value") or attr_dict.get("name") or "checked"
                self.cards[self.current_card_id]["options"].append(val)

    def handle_endtag(self, tag: str) -> None:
        if tag in ["h1", "h2", "h3", "div", "span"] and self._in_title:
            self._in_title = False
            if self.current_card_id:
                self.cards[self.current_card_id]["title"] = "".join(self._title_buffer).strip()

        if tag == "textarea" and self._in_textarea:
            self._in_textarea = False
            if self.current_card_id:
                raw_text = "".join(self._textarea_buffer).strip()
                unescaped = raw_text
                self.cards[self.current_card_id]["remark"] = unescaped

        if tag == "article":
            self.current_card_id = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_buffer.append(data)
        elif self._in_textarea:
            self._textarea_buffer.append(data)


def parse_html_report(html_content: str) -> Dict[str, Any]:
    """Parse HTML string and extract decisions, remarks, and statistics."""
    embedded = extract_json_script(html_content, "avb-feedback")
    if isinstance(embedded, dict):
        embedded["provenance"] = "imported-artifact-unverified"
        return embedded
    # 1. First pass with standard HTMLParser
    parser = FeedbackHTMLParser()
    parser.feed(html_content)

    cards_list = list(parser.cards.values())

    # 2. Fallback regex pass for any textareas/selects outside article tags or custom layouts
    if not cards_list:
        cards_list = _fallback_regex_parse(html_content)

    # Classify decisions
    validated: List[Dict[str, Any]] = []
    adjusted: List[Dict[str, Any]] = []
    pending: List[Dict[str, Any]] = []

    for c in cards_list:
        status = (c.get("status") or "pending").lower()
        if status in ["validate", "validé", "ok", "approve"]:
            validated.append(c)
        elif status in ["adjust", "ajuster", "modify", "request_changes"]:
            adjusted.append(c)
        else:
            pending.append(c)

    summary = {
        "total": len(cards_list),
        "validated": len(validated),
        "adjusted": len(adjusted),
        "pending": len(pending),
    }

    mandate_markdown = _generate_mandate_markdown(cards_list, validated, adjusted, pending)

    return {
        "decisions": cards_list,
        "summary": summary,
        "validated": validated,
        "adjusted": adjusted,
        "pending": pending,
        "mandate_markdown": mandate_markdown,
        "provenance": "legacy-html-unverified",
        "submitted_at": None,
    }


def parse_html_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Read an HTML file on disk and extract human decisions and instructions."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"HTML artifact not found: {path}")

    content = path.read_text(encoding="utf-8")
    result = parse_html_report(content)
    result["file_path"] = str(path.resolve())
    return result


def _fallback_regex_parse(content: str) -> List[Dict[str, Any]]:
    """Regex fallback parser for custom layouts (like roadmaps or tables)."""
    results: Dict[str, Dict[str, Any]] = {}

    # Find textareas
    textarea_matches = re.finditer(
        r'<textarea[^>]*id=["\'](?:remark-)?([^"\']+)["\'][^>]*>(.*?)</textarea>',
        content,
        re.DOTALL,
    )
    for m in textarea_matches:
        cid = m.group(1)
        remark = html.unescape(m.group(2).strip())
        results[cid] = {
            "id": cid,
            "title": cid,
            "status": "pending",
            "remark": remark,
            "options": [],
        }

    # Find selects
    select_matches = re.finditer(
        r'<select[^>]*id=["\'](?:status-)?([^"\']+)["\'][^>]*>(.*?)</select>',
        content,
        re.DOTALL,
    )
    for sm in select_matches:
        cid = sm.group(1)
        body = sm.group(2)
        selected_match = re.search(r'<option[^>]*value=["\']([^"\']+)["\'][^>]*selected', body)
        status_val = selected_match.group(1) if selected_match else "pending"
        if cid in results:
            results[cid]["status"] = status_val
        else:
            results[cid] = {
                "id": cid,
                "title": cid,
                "status": status_val,
                "remark": "",
                "options": [],
            }

    return list(results.values())


def _generate_mandate_markdown(
    all_cards: List[Dict[str, Any]],
    validated: List[Dict[str, Any]],
    adjusted: List[Dict[str, Any]],
    pending: List[Dict[str, Any]],
) -> str:
    """Generate ready-to-use markdown instructions for an AI agent."""
    lines = [
        "# Mandat d'Arbitrage & Consignes Humaines",
        "",
        "## Bilan Global :",
        f"- ✅ **Validés sans modification :** {len(validated)}",
        f"- ✏️ **Révision demandée, sans autorisation :** {len(adjusted)}",
        f"- ⏳ **En attente :** {len(pending)}",
        "",
    ]

    if adjusted:
        lines.append("## ✏️ Consignes & Ajustements Spécifiques (Prioritaires) :")
        for item in adjusted:
            title = item.get("title") or item["id"]
            lines.append(f"### Point `{item['id']}` : {title}")
            lines.append(f"**Statut :** `{item['status']}`")
            if item.get("options"):
                lines.append(f"**Options choisies :** {', '.join(item['options'])}")
            if item.get("remark"):
                lines.append(f"> **Remarque du développeur :**\n> {item['remark']}")
            lines.append("")

    if validated:
        lines.append("## ✅ Points Validés Conformes :")
        for item in validated:
            title = item.get("title") or item["id"]
            opt_str = f" ({', '.join(item['options'])})" if item.get("options") else ""
            lines.append(f"- **[`{item['id']}`]** {title}{opt_str}")
            if item.get("remark"):
                lines.extend(f"> {line}" for line in item["remark"].splitlines())
        lines.append("")

    if pending:
        lines.append("## En attente, sans autorisation")
        for item in pending:
            lines.append(f"- [{item['id']}] {item.get('title', '')}")
            if item.get("remark"):
                lines.extend(f"> {line}" for line in item["remark"].splitlines())
    return "\n".join(lines)


class _EmbeddedParser(HTMLParser):
    def __init__(self, target):
        super().__init__()
        self.target, self.active, self.parts = target, False, []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == self.target:
            self.active = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def extract_json_script(content, target):
    parser = _EmbeddedParser(target)
    parser.feed(content)
    return json.loads("".join(parser.parts)) if parser.parts else None


def extract_proposal(content):
    return extract_json_script(content, "avb-proposal")
