"""Cooperative adapter. Controls become applied only at execution checkpoints."""

from __future__ import annotations

from .models import ConflictError, ValidationError, canonical
from .policy import evaluate
from .store import Store


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


class CodexTextExecutor:
    """Optional installed CLI integration for read-only synthesis tasks.

    The host routes authorized work through CooperativeAgent. The CLI runs in
    read-only mode; this integration does not grant arbitrary shell/file writes.
    Credentials remain managed by the installed CLI, outside the bridge.
    """

    def __init__(self, workspace, configuration=None, timeout=120):
        self.workspace = str(workspace)
        self.configuration = configuration or []
        self.timeout = timeout

    def __call__(self, item, constraints):
        import json
        import subprocess
        argv = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "-C", self.workspace,
                "-s", "read-only", "--json"]
        for configuration in self.configuration:
            argv.extend(["-c", configuration])
        prompt = ("Perform this authorized read-only synthesis task. Respect every human constraint. "
                  "Do not modify files or take external actions. Return the requested content.\n" +
                  canonical({"item": item, "human_constraints": constraints}))
        response = subprocess.run(argv + ["-"], input=prompt, text=True,
                                  capture_output=True, timeout=self.timeout, check=False)
        if response.returncode:
            raise RuntimeError(f"Codex CLI exited with code {response.returncode}")
        events = []
        for line in response.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
        completed = next((e for e in reversed(events) if e.get("type") == "turn.completed"), None)
        messages = [e["item"].get("text", "") for e in events if e.get("type") == "item.completed"
                    and e.get("item", {}).get("type") == "agent_message"]
        if not completed or not messages or not messages[-1].strip():
            raise RuntimeError("Codex returned no completed response")
        calls = [e["item"] for e in events if e.get("type") == "item.completed"
                 and e.get("item", {}).get("type") == "mcp_tool_call"]
        required = item.get("action", {}).get("required_tools", [])
        if not isinstance(required, list) or any(not isinstance(t, str) for t in required):
            raise ValidationError("required_tools must be a list of tool names")
        for tool in required:
            if not any(c.get("tool") == tool and c.get("status") == "completed"
                       and not c.get("error") and not (c.get("result") or {}).get("isError", False)
                       for c in calls):
                raise RuntimeError(f"Required tool did not succeed: {tool}")
        markers = item.get("action", {}).get("required_output", [])
        if not isinstance(markers, list) or any(not isinstance(t, str) for t in markers):
            raise ValidationError("required_output must be a list of literal strings")
        if any(marker not in messages[-1] for marker in markers):
            raise RuntimeError("Required output evidence is missing")
        return [{"kind": "tool_result", "source": "codex exec (read-only)",
                 "content": messages[-1], "usage": completed.get("usage", {}),
                 "tool_calls": [{"tool": c.get("tool"), "status": c.get("status"),
                                 "error": c.get("error")} for c in calls]}]
