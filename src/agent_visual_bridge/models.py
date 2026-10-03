"""Versioned, JSON-only contracts. Agent suggestions never create human decisions."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .detector import detect_report_type

SCHEMA_VERSION = 1
KINDS = {"inform", "clarify", "authorize"}
DECISIONS = {"approve", "request_changes", "reject", "defer", "answer", "choose"}
ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")


class ValidationError(ValueError):
    """An invalid or inconsistent document."""


class ConflictError(ValidationError):
    """A stale document or illegal transition."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Documents must contain finite JSON values") from exc


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def identifier(value: Any, name: str = "id") -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValidationError(f"{name}: expected 1–128 letters, digits, '.', '_', ':' or '-'")
    return value


def text(value: Any, name: str, limit: int = 100_000) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise ValidationError(f"{name}: expected text of at most {limit} characters")
    return value


def normalize(data: Any, *, title: str = "Agent Visual Report", report_type: str = None,
              review_id: str = None, revision: int = 1) -> dict:
    if isinstance(data, list):
        data = {"items": data}
    if not isinstance(data, dict):
        raise ValidationError("Report must be an object or a list of objects")
    data = copy.deepcopy(data)
    canonical(data)
    if data.get("schema_version", 1) != SCHEMA_VERSION:
        raise ValidationError("Unsupported schema_version")
    explicit = report_type or data.get("report_type")
    if explicit and explicit not in {"auto", "audit", "plan", "review", "decision"}:
        raise ValidationError("Unknown report_type")
    raw = next((data[key] for key in ("items", "points", "tasks", "checks", "lots")
                if key in data), [])
    if not isinstance(raw, list) or not raw or len(raw) > 1000:
        raise ValidationError("items must contain between 1 and 1000 objects")
    kind = data.get("interaction_kind", "authorize")
    if kind not in KINDS:
        raise ValidationError("Unknown interaction_kind")
    items, ids = [], set()
    for index, original in enumerate(raw, 1):
        if not isinstance(original, dict):
            raise ValidationError("Every item must be an object")
        item = copy.deepcopy(original)
        item["id"] = identifier(item.get("id", f"item-{index}"))
        if item["id"] in ids:
            raise ValidationError(f"Duplicate item id: {item['id']}")
        ids.add(item["id"])
        item["title"] = text(item.get("title", f"Élément {index}"), "title", 1000)
        item["description"] = text(item.get("description", item.get("desc", "")), "description")
        item["question"] = text(item.get("question", item["title"]), "question")
        item["interaction_kind"] = item.get("interaction_kind", kind)
        if item["interaction_kind"] not in KINDS:
            raise ValidationError("Unknown item interaction_kind")
        for key in ("recommendation", "consequences"):
            item[key] = text(item.get(key, ""), key)
        if "diff" in item:
            item["diff"] = text(item["diff"], "diff")
        if "action" in item:
            action = item["action"]
            if not isinstance(action, dict):
                raise ValidationError("action must be an object")
            for field in ("operation", "scope"):
                if not text(action.get(field), "action." + field, 1000):
                    raise ValidationError("action requires operation and scope")
            for field in ("external", "reversible"):
                if field in action and not isinstance(action[field], bool):
                    raise ValidationError("action." + field + " must be boolean")
            for field in ("required_tools", "required_output"):
                if field in action and (not isinstance(action[field], list) or
                                        any(not isinstance(v, str) for v in action[field])):
                    raise ValidationError("action." + field + " must be a list of strings")
        for key in ("dependencies", "unknowns", "constraints", "allowed_files", "forbidden_files"):
            values = item.get(key, [])
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise ValidationError(f"{key} must be a list of strings")
            item[key] = values
        options = item.get("options", item.get("choices", []))
        if not isinstance(options, list):
            raise ValidationError("options must be a list")
        item["options"] = []
        option_ids = set()
        for oi, opt in enumerate(options, 1):
            opt = {"id": f"option-{oi}", "label": opt} if isinstance(opt, str) else opt
            if not isinstance(opt, dict):
                raise ValidationError("option must be a string or object")
            opt = dict(opt)
            opt["id"] = identifier(opt.get("id", f"option-{oi}"), "option.id")
            opt["label"] = text(opt.get("label", opt.get("title", opt["id"])), "option.label")
            if opt["id"] in option_ids:
                raise ValidationError("Duplicate option id")
            option_ids.add(opt["id"])
            item["options"].append(opt)
        evidence = item.get("evidence", [])
        if not isinstance(evidence, list):
            raise ValidationError("evidence must be a list")
        for ev in evidence:
            if not isinstance(ev, dict) or not isinstance(ev.get("source"), str):
                raise ValidationError("Evidence requires a source")
            if ev.get("kind", "agent_observation") not in {
                "agent_observation", "tool_result", "human_statement", "document"
            }:
                raise ValidationError("Unknown evidence kind")
        item["evidence"] = evidence
        for key in ("status", "decision", "decision_kind", "remark", "comment", "fingerprint", "authorization_fingerprint"):
            item.pop(key, None)
        item["fingerprint"] = fingerprint(item)
        items.append(item)
    by_id = {i["id"]: i for i in items}
    visiting, visited = set(), set()

    def visit(item_id: str, depth: int = 0) -> None:
        if depth > 64:
            raise ValidationError("Dependency graph is too deep")
        if item_id in visiting:
            raise ValidationError("Dependency cycle")
        if item_id in visited:
            return
        visiting.add(item_id)
        for dep in by_id[item_id]["dependencies"]:
            if dep not in by_id:
                raise ValidationError(f"Unknown dependency: {dep}")
            visit(dep, depth + 1)
        visiting.remove(item_id)
        visited.add(item_id)
        by_id[item_id]["authorization_fingerprint"] = fingerprint({
            "item": by_id[item_id]["fingerprint"],
            "dependencies": {d: by_id[d]["authorization_fingerprint"]
                             for d in by_id[item_id]["dependencies"]},
        })

    for item_id in by_id:
        visit(item_id)
    result = {
        "schema_version": SCHEMA_VERSION,
        "review_id": identifier(review_id or data.get("review_id") or uuid4().hex, "review_id"),
        "revision": revision,
        "project_id": identifier(data.get("project_id", "default"), "project_id"),
        "title": text(data.get("title", title), "title", 1000),
        "subtitle": text(data.get("subtitle", data.get("description", "")), "subtitle"),
        "interaction_kind": kind,
        "report_type": detect_report_type(data, data.get("title", title),
                                          explicit_type=explicit).value,
        "items": items,
        "metadata": data.get("metadata", {}),
    }
    result["fingerprint"] = fingerprint(result)
    return result


def validate_decisions(proposal: dict, decisions: Any) -> list:
    if not isinstance(decisions, list) or not decisions:
        raise ValidationError("An explicit, non-empty list of decisions is required")
    items = {i["id"]: i for i in proposal["items"]}
    result, seen = [], set()
    for value in decisions:
        if not isinstance(value, dict):
            raise ValidationError("Decision must be an object")
        key = value.get("id")
        if key not in items or key in seen:
            raise ValidationError("Unknown or duplicate decision id")
        seen.add(key)
        item = items[key]
        kind = value.get("decision_kind", value.get("status"))
        kind = {"validate": "approve", "adjust": "request_changes", "pending": "defer"}.get(kind, kind)
        if kind not in DECISIONS:
            raise ValidationError("Unknown decision kind")
        allowed = set() if item["interaction_kind"] == "inform" else {"reject", "defer", "request_changes"}
        if item["interaction_kind"] == "authorize":
            allowed.add("approve")
        elif item["interaction_kind"] == "clarify":
            allowed.update({"answer", "choose"})
        if kind not in allowed:
            raise ValidationError("Decision does not match this interaction")
        if value.get("fingerprint") != item["authorization_fingerprint"]:
            raise ConflictError("Item changed; review the current proposal")
        options = value.get("options", [])
        if not isinstance(options, list) or any(o not in {x["id"] for x in item["options"]}
                                               for o in options) or len(set(options)) != len(options):
            raise ValidationError("Unknown or duplicate selected option")
        if kind == "choose" and len(options) != 1:
            raise ValidationError("Choose exactly one option")
        comment = text(value.get("comment", value.get("remark", "")), "comment")
        answer = text(value.get("answer", ""), "answer")
        if kind == "answer" and not answer.strip():
            raise ValidationError("Answer cannot be empty")
        constraints = value.get("constraints", [])
        if not isinstance(constraints, list) or not all(isinstance(c, str) for c in constraints):
            raise ValidationError("constraints must be a list of strings")
        result.append({"id": key, "title": item["title"], "decision_kind": kind,
                       "fingerprint": item["authorization_fingerprint"], "comment": comment,
                       "answer": answer, "constraints": constraints, "options": options})
    return result


def mandate(decisions: list, pending: list = None) -> str:
    lines = ["# Décisions humaines", ""]
    for d in decisions:
        lines.append(f"## [{d['id']}] {d.get('title', d['id'])}")
        lines.append(f"Décision : {d.get('decision_kind', d.get('status', 'pending'))}")
        for key in ("comment", "remark", "answer"):
            if d.get(key):
                lines.extend(f"> {line}" for line in d[key].splitlines())
        for key in ("options", "constraints"):
            if d.get(key):
                lines.append(f"{key} : {', '.join(d[key])}")
        lines.append("")
    if pending:
        lines.append("En attente, sans autorisation : " + ", ".join(pending))
    return "\n".join(lines)
