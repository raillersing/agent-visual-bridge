"""Cooperative adapter. Controls become applied only at execution checkpoints."""

from __future__ import annotations

from uuid import uuid4
from .execution import ExecutionRequest, ExecutionResult, UnknownExecution
import subprocess
import json

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

    def __init__(self, service, review_id, executor, agent_id="cooperative-agent", *, session_id=None, lease_seconds=300):
        self.service, self.review_id, self.executor = service, review_id, executor
        self.agent_id = agent_id
        self.session_id = session_id or uuid4().hex
        self.lease_seconds = lease_seconds
        self.capabilities = ["pause", "resume", "stop", "priority", "constraint", "enforce_policy"]
        self.renew()

    def renew(self):
        return self.service.register_agent(self.review_id, self.agent_id, self.capabilities,
                                           self.session_id, self.lease_seconds)

    def release(self):
        return self.service.release_agent(self.review_id, self.agent_id, self.session_id)

    def _acknowledge(self, control_id, state, reason):
        return self.service.acknowledge_control(self.review_id, control_id, state, reason,
                                                self.agent_id, self.session_id)

    def checkpoint(self):
        with self.service.store.transaction() as db:
            owner = self.service._active_sessions(db, self.review_id).get(self.session_id)
            if not owner or owner["agent_id"] != self.agent_id:
                raise ConflictError("Agent lease expired or released; renew explicitly")
        events = self.service.events(self.review_id)
        states, requests = {}, []
        paused, stopped, constraints, priorities = False, False, [], {}
        for e in events:
            if e["kind"] == "control_requested" and e.get("session_id") == self.session_id:
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
                    self._acknowledge(request["control_id"],
                                                     "rejected", "Invalid control payload")
                continue
            if state in {"requested", "acknowledged"}:
                self._acknowledge(request["control_id"],
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
            return {"state": "stopped" if controls["stopped"] else "paused"}
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
            execution_id = uuid4().hex
            # Claim once under a lock; another worker cannot execute the same action.
            with self.service.store.transaction() as db:
                owner = self.service._active_sessions(db, self.review_id).get(self.session_id)
                if not owner or owner["agent_id"] != self.agent_id:
                    raise ConflictError("Agent lease expired before execution")
                # A newly requested pause/stop must reach a checkpoint before claiming.
                controls_now = [json.loads(r[0]) for r in db.execute(
                    "SELECT document FROM events WHERE review_id=? AND kind IN ('control_requested','control_updated') ORDER BY seq", (self.review_id,))]
                controls_latest = {c["control_id"]: c for c in controls_now}
                if any(c.get("session_id") == self.session_id and c["state"] in {"requested", "acknowledged"} for c in controls_latest.values()):
                    return {"state": "waiting", "reason": "Pending control checkpoint"}
                current = self.service._row(db, self.review_id)
                if current["document"] != canonical({k: v for k, v in review.items()
                                                       if k not in {"state", "decisions", "created_at", "updated_at", "receipts"}}):
                    raise ConflictError("Review changed before execution")
                configured = db.execute("SELECT document FROM settings WHERE project_id=?", (review["project_id"],)).fetchone()
                effect = evaluate(json.loads(configured[0]) if configured else {}, action)["effect"]
                if (current["state"] in {"cancelled", "expired"} or effect == "deny"
                        or (effect == "ask" and decision.get("decision_kind") != "approve")):
                    continue
                if db.execute("SELECT 1 FROM events WHERE review_id=? AND kind='execution_started' AND json_extract(document,'$.key')=?",
                              (self.review_id, execution_key)).fetchone():
                    continue
                Store.event(db, self.review_id, "execution_started", {"key": execution_key,
                            "item_id": item["id"], "revision": review["revision"], "agent_id": self.agent_id, "session_id": self.session_id,
                            "execution_id": execution_id, "engine_id": getattr(self.executor, "engine_id", "legacy-callback")})
            self.service.publish_progress(self.review_id, item["id"], "running", revision=review["revision"], execution_id=execution_id)
            constraints = item["constraints"] + decision.get("constraints", []) + controls["constraints"]
            if decision.get("comment"):
                constraints.append(decision["comment"])
            item_id = item["id"]
            request = ExecutionRequest(execution_id, self.review_id, review["revision"],
                                       self.agent_id, self.session_id, execution_key, item, constraints,
                                       engine_id=getattr(self.executor, "engine_id", "legacy-callback"),
                                       authorization={"decision": decision, "receipt_ids": review["receipts"],
                                                      "policy_effect": policy["effect"]})
            try:
                if hasattr(self.executor, "execute"):
                    value = self.executor.execute(request)
                    result = ExecutionResult.parse(value.__dict__ if isinstance(value, ExecutionResult) else value, request)
                else:
                    evidence = self.executor(item, constraints)
                    result = ExecutionResult.parse({"execution_id": execution_id, "state": "succeeded",
                                                    "evidence": evidence, "message": "Executor completed"}, request)
            except (UnknownExecution, TimeoutError, subprocess.TimeoutExpired, ValidationError):
                result = ExecutionResult(execution_id, "unknown", [], "Execution outcome requires reconciliation")
            except Exception:
                # Unclassified failures may happen after side effects. Never infer rollback.
                result = ExecutionResult(execution_id, "unknown", [], "Executor failed without a confirmed outcome")
            self.service.publish_progress(self.review_id, item_id, result.state, result.message,
                                          result.evidence, revision=review["revision"], execution_id=execution_id)
            return {"state": result.state, "id": item_id, "evidence": result.evidence,
                    "execution_id": execution_id}
        return {"state": "waiting"}

    def reconcile(self, item_id, state, message, evidence=None, execution_id=None):
        if state not in {"succeeded", "failed", "unknown"}:
            raise ValidationError("Invalid reconciliation state")
        claims = [e for e in self.service.events(self.review_id) if e["kind"] == "execution_started"
                  and e["item_id"] == item_id and (execution_id is None or e.get("execution_id") == execution_id)]
        if len(claims) != 1:
            raise ConflictError("Select exactly one existing execution to reconcile")
        claim = claims[0]
        return self.service.publish_progress(self.review_id, item_id, state, message, evidence,
                                             revision=claim["revision"], execution_id=claim.get("execution_id"))
