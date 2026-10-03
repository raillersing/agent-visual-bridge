"""Local, content-free interaction metrics; no network or telemetry."""

from __future__ import annotations

import math
from datetime import datetime
from statistics import median


def summarize(service, review_id):
    events = service.events(review_id)
    opened = {}
    active = []
    completed = {e["item_id"] for e in events if e["kind"] == "progress" and e["state"] == "succeeded"}
    for e in events:
        if e["kind"] == "interaction_metric":
            if e["event"] == "opened":
                opened.setdefault(e.get("view_id", "default"), datetime.fromisoformat(e["created_at"]))
            elif e["event"] in {"hidden", "submitted"}:
                start = opened.pop(e.get("view_id", "default"), None)
                if start:
                    active.append((datetime.fromisoformat(e["created_at"]) - start).total_seconds())
    active.sort()
    return {"review_id": review_id, "active_seconds": sum(active),
            "segment_median": median(active) if active else None,
            "segment_p90": active[max(0, math.ceil(len(active) * .9) - 1)] if active else None,
            "submissions": sum(e["kind"] == "decisions_submitted" for e in events),
            "questions": sum(e["kind"] == "item_message" and e["category"] == "question" for e in events),
            "revisions": sum(e["kind"] == "review_revised" for e in events),
            "completed_actions": len(completed),
            "resumptions": sum(e["kind"] == "control_updated" and e.get("command") == "resume"
                               and e["state"] == "applied" for e in events)}


def record(service, review_id, event, view_id="default"):
    from .models import ValidationError, text
    from .store import Store
    if event not in {"opened", "hidden", "submitted"}:
        raise ValidationError("Unknown metric event")
    service.get_review(review_id)
    with service.store.transaction() as db:
        Store.event(db, review_id, "interaction_metric",
                    {"event": event, "view_id": text(view_id, "view_id", 128)})
