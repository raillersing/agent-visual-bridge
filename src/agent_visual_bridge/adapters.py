"""Cooperative adapter. Controls become applied only at execution checkpoints."""

from __future__ import annotations

from .models import ConflictError, ValidationError, canonical
from .policy import evaluate
from .store import Store
from .executors.codex import CodexTextExecutor as CodexTextExecutor


class CooperativeAgent:
    """Bind an agent's action executor to durable decisions and explicit policy.

    The callable receives the immutable item and human constraints. It must return
    JSON evidence. Hosts must route their actions through this adapter to enforce
    policy; this adapter cannot govern tool calls made outside it.
    """

    def __init__(self, service, review_id, executor, agent_id="cooperative-agent"):
        self.service, self.review_id, self.executor = service, review_id, executor
        self.agent_id = agent_id
        service.register_agent(review_id, agent_id,
                               ["pause", "resume", "stop", "priority", "constraint", "enforce_policy"])

    def checkpoint(self):
        events = self.service.events(self.review_id)
        states, requests = {}, []
        paused, stopped, constraints, priorities = False, False, [], {}
        for e in events:
            if e["kind"] == "control_requested":
                requests.append(e)
                states[e["control_id"]] = e["state"]
            elif e["kind"] == "control_updated":
                states[e["control_id"]] = e["state"]
        for request in requests:
            state = states[request["control_id"]]
            command, payload = request["command"], request["payload"]
            if state in {"unsupported", "rejected"}:
                continue
            valid = isinstance(payload, dict)
            if command == "constraint":
                valid = valid and isinstance(payload.get("text"), str) and bool(payload["text"].strip())
            if command == "priority":
                valid = valid and isinstance(payload.get("items"), list)
            if not valid:
                if state in {"requested", "acknowledged"}:
                    self.service.acknowledge_control(self.review_id, request["control_id"],
                                                     "rejected", "Invalid control payload")
                continue
            if state in {"requested", "acknowledged"}:
                self.service.acknowledge_control(self.review_id, request["control_id"],
                                                 "applied", "Applied at a cooperative checkpoint")
            if command == "pause":
                paused = True
            elif command == "resume":
                paused = False
            elif command == "stop":
                stopped = True
            elif command == "constraint":
                constraints.append(payload["text"])
            elif command == "priority":
                priorities = {key: i for i, key in enumerate(payload["items"])}
        return {"paused": paused, "stopped": stopped,
                "constraints": constraints, "priorities": priorities}

    def run_next(self):
        controls = self.checkpoint()
        if controls["paused"] or controls["stopped"]:
            return {"state": "paused" if controls["paused"] else "stopped"}
        review = self.service.get_review(self.review_id)
        if review["state"] in {"cancelled", "expired", "superseded"}:
            return {"state": "closed"}
        events = self.service.events(self.review_id)
        fingerprints = {i["id"]: i["authorization_fingerprint"] for i in review["items"]}
        latest = {e["item_id"]: e for e in events if e["kind"] == "progress"}
        successful = {key for key, e in latest.items() if e["state"] == "succeeded"
                      and e.get("fingerprint") == fingerprints.get(key)}
        items = sorted(review["items"], key=lambda i: controls["priorities"].get(i["id"], 1000))
        for item in items:
            if item["interaction_kind"] != "authorize":
                continue
            execution_key = item["authorization_fingerprint"]
            executions = [e for e in events if e["kind"] == "execution_started" and e["key"] == execution_key]
            if executions:
                continue  # Running/unknown/failed actions require explicit reconciliation, never blind retry.
            decision = review["decisions"].get(item["id"], {})
            if decision.get("decision_kind") in {"reject", "request_changes", "defer"}:
                continue
            action = item.get("action", {"operation": "task", "scope": "workspace"})
            if not isinstance(action, dict):
                raise ValidationError("action must be an object")
            policy = evaluate(self.service.settings(review["project_id"]), action)
            if policy["effect"] == "deny" or (policy["effect"] == "ask" and decision.get("decision_kind") != "approve"):
                continue
            if not set(item["dependencies"]) <= successful:
                continue
            if decision and decision.get("fingerprint") != execution_key:
                raise ConflictError("Authorization fingerprint changed")
            # Claim once under a lock; another worker cannot execute the same action.
            with self.service.store.transaction() as db:
                current = self.service._row(db, self.review_id)
                if current["document"] != canonical({k: v for k, v in review.items()
                                                       if k not in {"state", "decisions", "created_at", "updated_at", "receipts"}}):
                    raise ConflictError("Review changed before execution")
                import json
                configured = db.execute("SELECT document FROM settings WHERE project_id=?", (review["project_id"],)).fetchone()
                effect = evaluate(json.loads(configured[0]) if configured else {}, action)["effect"]
                if (current["state"] in {"cancelled", "expired"} or effect == "deny"
                        or (effect == "ask" and decision.get("decision_kind") != "approve")):
                    continue
                if db.execute("SELECT 1 FROM events WHERE review_id=? AND kind='execution_started' AND json_extract(document,'$.key')=?",
                              (self.review_id, execution_key)).fetchone():
                    continue
                Store.event(db, self.review_id, "execution_started", {"key": execution_key,
                            "item_id": item["id"], "revision": review["revision"], "agent_id": self.agent_id})
            self.service.publish_progress(self.review_id, item["id"], "running", revision=review["revision"])
            constraints = item["constraints"] + decision.get("constraints", []) + controls["constraints"]
            if decision.get("comment"):
                constraints.append(decision["comment"])
            try:
                evidence = self.executor(item, constraints)
                canonical(evidence)
                self.service.publish_progress(self.review_id, item["id"], "succeeded",
                                              "Executor completed", evidence, revision=review["revision"])
                return {"state": "succeeded", "id": item["id"], "evidence": evidence}
            except Exception as exc:
                self.service.publish_progress(self.review_id, item["id"], "failed", str(exc), revision=review["revision"])
                return {"state": "failed", "id": item["id"], "error": str(exc)}
        return {"state": "waiting"}

    def reconcile(self, item_id, state, message, evidence=None):
        if state not in {"succeeded", "failed", "unknown"}:
            raise ValidationError("Invalid reconciliation state")
        return self.service.publish_progress(self.review_id, item_id, state, message, evidence)
