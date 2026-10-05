"""Durable review lifecycle, revisions, conversations and acknowledged controls."""

from __future__ import annotations

import json
from uuid import uuid4

from .models import (
    ConflictError,
    ValidationError,
    canonical,
    fingerprint,
    mandate,
    normalize,
    now,
    text,
    validate_decisions,
)
from .store import Store

TERMINAL = {"expired", "cancelled", "superseded"}


class ReviewService:
    def __init__(self, path=None):
        self.store = path if isinstance(path, Store) else Store(path)

    def create_review(self, data, **kwargs):
        proposal = normalize(data, **kwargs)
        stamp = now()
        with self.store.transaction() as db:
            if db.execute("SELECT 1 FROM reviews WHERE id=?", (proposal["review_id"],)).fetchone():
                raise ConflictError("Review already exists")
            db.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?)",
                       (proposal["review_id"], canonical(proposal),
                        "published" if all(i["interaction_kind"] == "inform" for i in proposal["items"]) else "awaiting_input",
                        "{}", stamp, stamp))
            db.execute("INSERT INTO revisions VALUES(?,?,?)",
                       (proposal["review_id"], 1, canonical(proposal)))
            Store.event(db, proposal["review_id"], "review_created", {"revision": 1})
        return self.get_review(proposal["review_id"])

    @staticmethod
    def _row(db, review_id):
        row = db.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
        if row is None:
            raise ValidationError("Review not found")
        return row

    def get_review(self, review_id):
        with self.store.transaction() as db:
            row = self._row(db, review_id)
            result = json.loads(row["document"])
            result.update(state=row["state"], decisions=json.loads(row["decisions"]),
                          created_at=row["created_at"], updated_at=row["updated_at"])
            result["receipts"] = [r[0] for r in db.execute(
                "SELECT id FROM receipts WHERE review_id=? ORDER BY rowid", (review_id,))]
        return result

    def list_reviews(self):
        with self.store.transaction() as db:
            return [dict(r) for r in db.execute(
                "SELECT id,state,created_at,updated_at FROM reviews ORDER BY updated_at DESC")]

    def submit_decisions(self, review_id, revision, decisions, request_key, *,
                         actor="local-human", provenance="local-browser"):
        text(request_key, "request_key", 200)
        if not request_key:
            raise ValidationError("request_key required")
        request_hash = fingerprint({"revision": revision, "decisions": decisions,
                                    "actor": actor, "provenance": provenance})
        with self.store.transaction() as db:
            existing = db.execute("SELECT * FROM receipts WHERE review_id=? AND request_key=?",
                                  (review_id, request_key)).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise ConflictError("Idempotency key reused for a different submission")
                return json.loads(existing["document"])
            row = self._row(db, review_id)
            proposal = json.loads(row["document"])
            if row["state"] in TERMINAL or row["state"] == "submitted":
                raise ConflictError("Review closed; create a revision to change decisions")
            if revision != proposal["revision"]:
                raise ConflictError("Stale review revision")
            validated = validate_decisions(proposal, decisions)
            previous = json.loads(row["decisions"])
            for decision in validated:
                if (decision["id"] in previous and previous[decision["id"]] != decision
                        and previous[decision["id"]]["decision_kind"] != "defer"):
                    raise ConflictError("Decision already submitted; revise the proposal")
                previous[decision["id"]] = decision
            pending = [i["id"] for i in proposal["items"] if i["interaction_kind"] != "inform"
                       and (i["id"] not in previous or previous[i["id"]]["decision_kind"] == "defer")]
            state = "partially_submitted" if pending else "submitted"
            all_decisions = list(previous.values())
            receipt = {"schema_version": 1, "receipt_id": uuid4().hex, "review_id": review_id,
                       "revision": revision, "proposal_fingerprint": proposal["fingerprint"],
                       "submitted_at": now(), "actor": text(actor, "actor", 200),
                       "provenance": text(provenance, "provenance", 200),
                       "request_key": request_key, "decisions": all_decisions,
                       "pending": pending, "state": state,
                       "mandate_markdown": mandate(all_decisions, pending)}
            receipt["markdown"] = receipt["mandate_markdown"]
            db.execute("INSERT INTO receipts VALUES(?,?,?,?,?)",
                       (receipt["receipt_id"], review_id, request_key, request_hash, canonical(receipt)))
            db.execute("UPDATE reviews SET decisions=?,state=?,updated_at=? WHERE id=?",
                       (canonical(previous), state, now(), review_id))
            Store.event(db, review_id, "decisions_submitted", {"receipt_id": receipt["receipt_id"],
                        "revision": revision, "count": len(validated), "pending": len(pending)})
        return receipt

    def get_receipt(self, receipt_id):
        with self.store.transaction() as db:
            row = db.execute("SELECT document FROM receipts WHERE id=?", (receipt_id,)).fetchone()
            if not row:
                raise ValidationError("Receipt not found")
            return json.loads(row[0])

    def revise_review(self, review_id, data, revision):
        with self.store.transaction() as db:
            row = self._row(db, review_id)
            old = json.loads(row["document"])
            if revision != old["revision"] or row["state"] in TERMINAL:
                raise ConflictError("Stale or closed review")
            proposal = normalize(data, review_id=review_id, revision=revision + 1)
            if proposal["project_id"] != old["project_id"]:
                raise ValidationError("Cannot change project on an existing review")
            before = {i["id"]: i for i in old["items"]}
            decisions = json.loads(row["decisions"])
            retained = {i["id"]: decisions[i["id"]] for i in proposal["items"]
                        if i["id"] in decisions and i["id"] in before
                        and before[i["id"]]["authorization_fingerprint"] == i["authorization_fingerprint"]}
            changed = [i["id"] for i in proposal["items"] if i["id"] not in before or
                       i["authorization_fingerprint"] != before[i["id"]]["authorization_fingerprint"]]
            removed = sorted(set(before) - {i["id"] for i in proposal["items"]})
            state = "awaiting_input" if not retained else "partially_submitted"
            required = [i for i in proposal["items"] if i["interaction_kind"] != "inform"]
            if not required:
                state = "published"
            elif all(i["id"] in retained and retained[i["id"]]["decision_kind"] != "defer"
                     for i in required):
                state = "submitted"
            db.execute("UPDATE reviews SET document=?, decisions=?,state=?,updated_at=? WHERE id=?",
                       (canonical(proposal), canonical(retained), state, now(), review_id))
            db.execute("INSERT INTO revisions VALUES(?,?,?)", (review_id, revision + 1, canonical(proposal)))
            Store.event(db, review_id, "review_revised", {"revision": revision + 1,
                        "changed": changed, "removed": removed, "retained": list(retained),
                        "changes": [{"id": i["id"], "before": before.get(i["id"]), "after": i}
                                    for i in proposal["items"] if i["id"] in changed] +
                                   [{"id": key, "before": before[key], "after": None} for key in removed]})
        return self.get_review(review_id)

    def close_review(self, review_id, state="cancelled"):
        if state not in {"cancelled", "expired"}:
            raise ValidationError("Invalid closure")
        with self.store.transaction() as db:
            row = self._row(db, review_id)
            if row["state"] == "submitted":
                raise ConflictError("Submitted decisions cannot be revoked by closing the view")
            db.execute("UPDATE reviews SET state=?,updated_at=? WHERE id=?", (state, now(), review_id))
            Store.event(db, review_id, "review_closed", {"state": state})
        return self.get_review(review_id)

    def events(self, review_id, after=0):
        self.get_review(review_id)
        return self.store.events(review_id, after)

    def ask_item_question(self, review_id, item_id, message):
        return self._message(review_id, item_id, "human", "question", message)

    def request_revision(self, review_id, revision, item_id, changes):
        review = self.get_review(review_id)
        if not isinstance(changes, dict) or set(changes) - {"scope", "dependencies", "options", "constraints", "position"}:
            raise ValidationError("Unknown revision field")
        proposal = {k: v for k, v in review.items() if k not in {
            "state", "decisions", "created_at", "updated_at", "receipts", "fingerprint"}}
        item = next((i for i in proposal["items"] if i["id"] == item_id), None)
        if not item:
            raise ValidationError("Item not found")
        position = changes.get("position")
        item.update({k: v for k, v in changes.items() if k != "position"})
        if "scope" in changes and isinstance(item.get("action"), dict):
            item["action"] = {**item["action"], "scope": changes["scope"]}
        if position is not None:
            if not isinstance(position, int) or not 1 <= position <= len(proposal["items"]):
                raise ValidationError("Invalid position")
            proposal["items"].remove(item)
            proposal["items"].insert(position - 1, item)
        result = self.revise_review(review_id, proposal, revision)
        with self.store.transaction() as db:
            Store.event(db, review_id, "human_revision_requested", {
                "item_id": item_id, "revision": result["revision"], "fields": list(changes)})
        return result

    def publish_item_reply(self, review_id, item_id, message, *, category="explanation", question_seq=None):
        if category not in {"explanation", "fact", "hypothesis", "missing", "integrated", "impossible"}:
            raise ValidationError("Unknown reply category")
        return self._message(review_id, item_id, "agent", category, message, question_seq)

    def _message(self, review_id, item_id, author, category, message, question_seq=None):
        with self.store.transaction() as db:
            proposal = json.loads(self._row(db, review_id)["document"])
            if item_id not in {i["id"] for i in proposal["items"]}:
                raise ValidationError("Item not found")
            doc = {"item_id": item_id, "revision": proposal["revision"], "author": author,
                   "category": category, "message": text(message, "message"), "question_seq": question_seq}
            seq = Store.event(db, review_id, "item_message", doc)
        return {"seq": seq, **doc}

    def _active_sessions(self, db, review_id):
        import time
        sessions = {}
        for row in db.execute("SELECT document FROM events WHERE review_id=? AND kind IN ('agent_registered','agent_released') ORDER BY seq", (review_id,)):
            event = json.loads(row[0])
            key = event.get("session_id")
            if key:
                if event.get("released"):
                    sessions.pop(key, None)
                else:
                    sessions[key] = event
        return {key: value for key, value in sessions.items() if value["expires_at"] > time.time()}

    def agent_sessions(self, review_id):
        with self.store.transaction() as db:
            self._row(db, review_id)
            active = list(self._active_sessions(db, review_id).values())
            if active:
                return active
            row = db.execute("SELECT document FROM events WHERE review_id=? AND kind='agent_registered' ORDER BY seq DESC LIMIT 1", (review_id,)).fetchone()
            legacy = json.loads(row[0]) if row else None
            return [legacy] if legacy and not legacy.get("session_id") else []

    def register_agent(self, review_id, agent_id, capabilities, session_id=None, lease_seconds=300):
        import time
        allowed = {"pause", "resume", "stop", "priority", "constraint", "enforce_policy"}
        if not isinstance(capabilities, list) or any(not isinstance(c, str) for c in capabilities) or not set(capabilities) <= allowed:
            raise ValidationError("Unknown agent capability")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 1 <= lease_seconds <= 86400:
            raise ValidationError("Invalid agent lease")
        doc = {"agent_id": text(agent_id, "agent_id", 200), "capabilities": capabilities}
        if session_id is not None:
            if not isinstance(session_id, str) or not session_id.strip():
                raise ValidationError("Agent session identifier must be nonempty")
            doc.update(session_id=text(session_id, "session_id", 200), expires_at=time.time() + lease_seconds)
        with self.store.transaction() as db:
            self._row(db, review_id)
            if session_id is not None:
                prior = db.execute("SELECT document FROM events WHERE review_id=? AND kind='agent_registered' AND json_extract(document,'$.session_id')=? ORDER BY seq DESC LIMIT 1", (review_id, session_id)).fetchone()
                if prior and json.loads(prior[0])["agent_id"] != agent_id:
                    raise ConflictError("Session belongs to another agent")
            Store.event(db, review_id, "agent_registered", doc)
        return doc

    def release_agent(self, review_id, agent_id, session_id):
        with self.store.transaction() as db:
            self._row(db, review_id)
            owner = self._active_sessions(db, review_id).get(session_id)
            if not owner or owner["agent_id"] != agent_id:
                raise ConflictError("Agent session is not active")
            doc = {"agent_id": agent_id, "session_id": session_id, "released": True}
            Store.event(db, review_id, "agent_released", doc)
        return doc

    def request_control(self, review_id, command, payload=None, agent_id=None, session_id=None):
        if command not in {"pause", "resume", "stop", "priority", "constraint"}:
            raise ValidationError("Unknown control")
        with self.store.transaction() as db:
            self._row(db, review_id)
            active = self._active_sessions(db, review_id)
            candidates = [a for a in active.values() if (agent_id is None or a["agent_id"] == agent_id)
                          and (session_id is None or a["session_id"] == session_id)]
            if len(candidates) > 1:
                raise ConflictError("Select an agent session for this control")
            agent = candidates[0] if candidates else None
            if not active and agent_id is None and session_id is None:
                row = db.execute("SELECT document FROM events WHERE review_id=? AND kind='agent_registered' ORDER BY seq DESC LIMIT 1", (review_id,)).fetchone()
                legacy = json.loads(row[0]) if row else None
                if legacy and not legacy.get("session_id"):
                    agent = legacy
            doc = {"control_id": uuid4().hex, "command": command,
                   "payload": {} if payload is None else payload,
                   "state": "requested" if agent and command in agent["capabilities"] else "unsupported"}
            if agent:
                doc.update(agent_id=agent["agent_id"], session_id=agent.get("session_id"))
            canonical(doc)
            Store.event(db, review_id, "control_requested", doc)
        return doc

    def acknowledge_control(self, review_id, control_id, state, reason="", agent_id=None, session_id=None):
        if state not in {"acknowledged", "applied", "rejected"}:
            raise ValidationError("Unknown acknowledgement")
        with self.store.transaction() as db:
            self._row(db, review_id)
            history = [json.loads(r[0]) for r in db.execute(
                "SELECT document FROM events WHERE review_id=? AND kind IN ('control_requested','control_updated') ORDER BY seq",
                (review_id,))]
            current = next((e for e in reversed(history) if e["control_id"] == control_id), None)
            transitions = {"requested": {"acknowledged", "applied", "rejected"},
                           "acknowledged": {"applied", "rejected"}}
            if not current or state not in transitions.get(current["state"], set()):
                raise ConflictError("Control cannot transition to this state")
            if current.get("session_id"):
                owner = self._active_sessions(db, review_id).get(session_id)
                if (not owner or current["session_id"] != session_id
                        or current["agent_id"] != agent_id or owner["agent_id"] != agent_id):
                    raise ConflictError("Control belongs to another or expired agent session")
            doc = {**current, "state": state, "reason": text(reason, "reason")}
            Store.event(db, review_id, "control_updated", doc)
        return doc

    def publish_progress(self, review_id, item_id, state, message="", evidence=None, revision=None, execution_id=None):
        if state not in {"not_started", "running", "succeeded", "failed", "unknown", "skipped"}:
            raise ValidationError("Unknown execution state")
        review = self.get_review(review_id)
        if revision is not None and revision != review["revision"]:
            with self.store.transaction() as db:
                row = db.execute("SELECT document FROM revisions WHERE review_id=? AND revision=?",
                                 (review_id, revision)).fetchone()
                if not row:
                    raise ValidationError("Execution revision not found")
                review = json.loads(row[0])
        if item_id not in {i["id"] for i in review["items"]}:
            raise ValidationError("Item not found")
        item = next(i for i in review["items"] if i["id"] == item_id)
        doc = {"item_id": item_id, "revision": review["revision"], "state": state,
               "fingerprint": item["authorization_fingerprint"],
               "message": text(message, "message"), "evidence": evidence or []}
        if not isinstance(doc["evidence"], list):
            raise ValidationError("Progress evidence must be a list")
        if execution_id is not None:
            doc["execution_id"] = execution_id
        canonical(doc)
        with self.store.transaction() as db:
            if execution_id is not None:
                claim = db.execute("SELECT document FROM events WHERE review_id=? AND kind='execution_started' AND json_extract(document,'$.execution_id')=?", (review_id, execution_id)).fetchone()
                claimed = json.loads(claim[0]) if claim else None
                if not claimed or claimed["item_id"] != item_id or claimed["revision"] != review["revision"] or claimed["key"] != doc["fingerprint"]:
                    raise ConflictError("Progress does not match execution claim")
            Store.event(db, review_id, "progress", doc)
        return doc

    def settings(self, project_id, value=None):
        from .policy import validate_settings
        with self.store.transaction() as db:
            if value is not None:
                value = validate_settings(value)
                db.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (project_id, canonical(value)))
            row = db.execute("SELECT document FROM settings WHERE project_id=?", (project_id,)).fetchone()
            return json.loads(row[0]) if row else validate_settings({})
