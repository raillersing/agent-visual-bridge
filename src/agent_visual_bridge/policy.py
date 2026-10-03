"""Explicit project rules. Presentation preferences do not grant permissions."""

from __future__ import annotations

from pathlib import PurePosixPath

from .models import ValidationError, canonical


def validate_settings(value):
    if not isinstance(value, dict) or set(value) - {"preferences", "rules"}:
        raise ValidationError("Settings contain preferences and explicit rules only")
    prefs = {"language": "fr", "detail": "summary", "notifications": True}
    given = value.get("preferences", {})
    if not isinstance(given, dict) or set(given) - set(prefs):
        raise ValidationError("Unknown presentation preference")
    prefs.update(given)
    if prefs["language"] not in {"fr", "en"} or prefs["detail"] not in {"summary", "full"}:
        raise ValidationError("Unsupported language/detail preference")
    if not isinstance(prefs["notifications"], bool):
        raise ValidationError("notifications must be boolean")
    rules = value.get("rules", [])
    if not isinstance(rules, list):
        raise ValidationError("rules must be a list")
    ids = set()
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) - {
            "id", "operation", "scope", "effect", "external", "reversible"
        }:
            raise ValidationError("Unknown policy field")
        if not isinstance(rule.get("id"), str) or rule["id"] in ids:
            raise ValidationError("Policy requires unique ids")
        ids.add(rule["id"])
        if rule.get("effect") not in {"allow", "ask", "deny"}:
            raise ValidationError("Policy effect must be allow, ask or deny")
        if not isinstance(rule.get("operation"), str) or not rule["operation"]:
            raise ValidationError("Policy requires an exact operation")
        scope = rule.get("scope")
        if not isinstance(scope, str) or not scope or (scope.startswith("/") or "\\" in scope or ":" in scope) or ".." in PurePosixPath(scope).parts:
            raise ValidationError("Policy scope must be a relative project path")
        if any(not isinstance(rule.get(k, False), bool) for k in ("external", "reversible")):
            raise ValidationError("external/reversible must be boolean")
    canonical(value)
    return {"preferences": prefs, "rules": rules}


def evaluate(settings, action):
    """Deny wins; no rule means ask. Scope is a path prefix with component boundaries."""
    settings = validate_settings(settings)
    operation = action.get("operation")
    scope = action.get("scope", "")
    if not isinstance(scope, str) or (scope.startswith("/") or "\\" in scope or ":" in scope) or ".." in PurePosixPath(scope).parts:
        return {"effect": "deny", "reason": "Path outside relative project scope"}
    matches = []
    for rule in settings["rules"]:
        prefix = rule["scope"].rstrip("/")
        if (rule["operation"] == operation and (scope == prefix or scope.startswith(prefix + "/"))
                and rule.get("external", False) == action.get("external", False)
                and rule.get("reversible", False) == action.get("reversible", False)):
            matches.append(rule)
    chosen = next((r for effect in ("deny", "ask", "allow") for r in matches if r["effect"] == effect), None)
    return {"effect": chosen["effect"] if chosen else "ask",
            "reason": f"Explicit rule {chosen['id']}" if chosen else "No applicable explicit authorization"}
