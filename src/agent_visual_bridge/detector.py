"""Auto-detection module for Agent Visual Bridge.

Analyzes input data or descriptions to automatically classify the artifact type:
- audit: list of checks, verifications, compliance rules with pass/fail/deviation states.
- plan: action plan, lots, roadmap, sequential tasks with dependencies.
- review: code review, PR diff analysis, risk assessment.
- decision: architectural choices, multi-choice trade-offs, configuration pillars.
"""

from __future__ import annotations

import re
import unicodedata
from enum import Enum
from typing import Any, Dict, List, Optional, Union


def _normalize_text(text: str) -> str:
    """Normalize text by lowering and removing accents."""
    text = text.lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )



class ReportType(str, Enum):
    AUDIT = "audit"
    PLAN = "plan"
    REVIEW = "review"
    DECISION = "decision"


# Keywords associated with each report type
TYPE_KEYWORDS: Dict[ReportType, List[str]] = {
    ReportType.AUDIT: [
        "audit", "verification", "verifications", "check", "checks", "controle",
        "conformite", "compliance", "ecart", "constat", "severity", "severite",
        "conforme", "non-conforme", "status", "statut"
    ],
    ReportType.PLAN: [
        "plan", "action", "lot", "lots", "phase", "phases", "roadmap", "etape",
        "etapes", "sprint", "task", "tasks", "milestone", "dependencies",
        "dependance", "scope", "perimetre", "planning"
    ],
    ReportType.REVIEW: [
        "review", "code-review", "pr", "diff", "pull-request", "patch",
        "regression", "syntax", "refactor", "security-review", "commit"
    ],
    ReportType.DECISION: [
        "decision", "choices", "options", "tradeoff", "trade-offs", "pillar",
        "pilier", "architecture", "adr", "arbitrage", "selection", "matrix"
    ],
}


def detect_report_type(
    data: Optional[Union[Dict[str, Any], List[Any]]] = None,
    title: str = "",
    description: str = "",
    explicit_type: Optional[str] = None,
) -> ReportType:
    """Automatically detect the best visual report type.

    If explicit_type is provided and valid, it is honored.
    Otherwise, structural heuristic and textual scoring are applied.
    """
    if explicit_type:
        explicit_clean = explicit_type.strip().lower()
        for rt in ReportType:
            if rt.value == explicit_clean:
                return rt

    scores: Dict[ReportType, int] = {rt: 0 for rt in ReportType}

    # 1. Inspect text from title and description
    combined_text = _normalize_text(f"{title} {description}")
    for rt, words in TYPE_KEYWORDS.items():
        for w in words:
            w_norm = _normalize_text(w)
            if re.search(r"\b" + re.escape(w_norm), combined_text):
                scores[rt] += 3

    # 2. Inspect structure of data
    if isinstance(data, dict):
        # Look for explicit top-level keys
        for key in data.keys():
            k_lower = key.lower()
            if any(w in k_lower for w in ["audit", "checks", "verifications", "findings"]):
                scores[ReportType.AUDIT] += 5
            elif any(w in k_lower for w in ["lots", "phases", "plan", "steps", "tasks"]):
                scores[ReportType.PLAN] += 5
            elif any(w in k_lower for w in ["diff", "files", "review", "changes"]):
                scores[ReportType.REVIEW] += 5
            elif any(w in k_lower for w in ["pillars", "decisions", "questions", "options"]):
                scores[ReportType.DECISION] += 5

        # Check items in data lists
        items = (
            data.get("items")
            or data.get("points")
            or data.get("tasks")
            or data.get("checks")
            or data.get("lots")
            or []
        )
        if isinstance(items, list) and items:
            sample = items[0]
            if isinstance(sample, dict):
                _score_item(sample, scores)

    elif isinstance(data, list) and data:
        for sample in data[:3]:
            if isinstance(sample, dict):
                _score_item(sample, scores)

    # Return report type with highest score, default to AUDIT if tie or zero
    sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    if sorted_types[0][1] > 0:
        return sorted_types[0][0]

    return ReportType.AUDIT


def _score_item(item: Dict[str, Any], scores: Dict[ReportType, int]) -> None:
    """Score a single sample item based on its keys."""
    keys = {k.lower() for k in item.keys()}

    # Audit item indicators
    if "severity" in keys or "severite" in keys:
        scores[ReportType.AUDIT] += 4
    if "verdict" in keys or "statut" in keys or "status" in keys:
        scores[ReportType.AUDIT] += 3

    # Plan item indicators
    if "lot" in keys or "phase" in keys or "dependencies" in keys:
        scores[ReportType.PLAN] += 4
    if "scope" in keys or "allowed_files" in keys or "forbidden_files" in keys:
        scores[ReportType.PLAN] += 4

    # Review item indicators
    if "file" in keys and ("diff" in keys or "additions" in keys or "patch" in keys):
        scores[ReportType.REVIEW] += 4

    # Decision item indicators
    if "options" in keys or "choices" in keys or "tradeoffs" in keys:
        scores[ReportType.DECISION] += 4
