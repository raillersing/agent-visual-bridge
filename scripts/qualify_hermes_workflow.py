"""Optional installed-Hermes integration probe; never a human participant study."""

import sys
import json
import tempfile
import time
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Real Hermes MCP workflow, synthetic decisions, no business writes"
    )
    parser.add_argument("--hermes-source", required=True, type=Path)
    parser.add_argument("--bridge-python", required=True, type=Path)
    parser.add_argument("--provider", default="openai-codex")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path)
    options = parser.parse_args()
    sys.path[:0] = [
        str(options.hermes_source.resolve()),
        str(Path(__file__).resolve().parents[1] / "src"),
    ]
    from run_agent import AIAgent
    from hermes_cli.runtime_provider import resolve_runtime_provider
    from tools.mcp_tool import register_mcp_servers, shutdown_mcp_servers
    from agent_visual_bridge import ReviewService, CooperativeAgent

    if options.output:
        root = options.output.resolve()
        root.mkdir(mode=448, parents=True, exist_ok=False)
    else:
        root = Path(tempfile.mkdtemp(prefix="avb-hermes-workflow-"))
    root.chmod(448)
    db = root / "reviews.db"
    service = ReviewService(db)
    started = time.monotonic()
    report = {
        "client": "Hermes",
        "provider": options.provider,
        "model": options.model,
        "human_participants": 0,
        "scope": "Synthetic review; no business writes",
        "status": "not-qualified",
        "stages": [],
    }
    runtime = resolve_runtime_provider(requested=options.provider, target_model=options.model)
    args = {k: runtime[k] for k in ["provider", "base_url", "api_key", "api_mode"] if k in runtime}
    server = {
        "bridge": {
            "command": str(options.bridge_python.absolute()),
            "args": ["-m", "agent_visual_bridge", "mcp"],
            "env": {"AVB_DB": str(db)},
            "tools": {
                "include": [
                    "visual_bridge_create_review",
                    "visual_bridge_get_receipt",
                    "visual_bridge_get_review",
                ]
            },
            "resources": False,
            "prompts": False,
        }
    }

    def turn(prompt, label):
        agent = AIAgent(
            **args,
            model=options.model,
            enabled_toolsets=["bridge"],
            max_iterations=4,
            max_tokens=1600,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            save_trajectories=False,
        )
        answer = agent.run_conversation(prompt)
        p = root / (label + ".private")
        p.write_text(json.dumps(answer, default=str))
        p.chmod(384)
        assert answer.get("completed") and (not answer.get("failed")), "Agent turn incomplete"
        messages = answer.get("messages", [])
        calls = [c for m in messages if isinstance(m, dict) for c in m.get("tool_calls", [])]
        report["stages"].append(
            {
                "stage": label,
                "tool_names": [c.get("function", {}).get("name") for c in calls],
                "api_calls": answer.get("api_calls"),
            }
        )
        return answer

    def receipts(answer, expected):
        decoder = json.JSONDecoder()
        found = []
        for m in answer.get("messages", []):
            if (
                not isinstance(m, dict)
                or m.get("role") != "tool"
                or (not isinstance(m.get("content"), str))
            ):
                continue
            text = m["content"]
            for i, ch in enumerate(text):
                if ch != "{":
                    continue
                try:
                    d, _ = decoder.raw_decode(text[i:])
                except ValueError:
                    continue
                if isinstance(d, dict) and d.get("receipt_id") == expected["receipt_id"]:
                    found.append(d)
        assert any((d == expected for d in found)), (
            "Exact durable receipt not found in actual tool response"
        )

    try:
        register_mcp_servers(server)
        proposal = {
            "project_id": "synthetic-hermes-qualification",
            "title": "Synthetic bounded workflow",
            "items": [
                {"id": "a", "title": "Read a synthetic receipt", "scope": "scratch-only"},
                {
                    "id": "b",
                    "title": "Storage clarification",
                    "interaction_kind": "clarify",
                    "options": ["SQLite", "Postgres"],
                },
                {"id": "c", "title": "Dependent read", "dependencies": ["a"]},
            ],
        }
        with service.store.transaction() as conn:
            ids = [r[0] for r in conn.execute("select id from reviews")]
        if not ids:
            turn(
                "Call visual_bridge_create_review exactly once with proposal "
                + json.dumps(proposal)
                + ". This is a synthetic technical test. Do not call any other tool. Return the review identifier.",
                "create",
            )
            with service.store.transaction() as conn:
                ids = [r[0] for r in conn.execute("select id from reviews")]
        assert len(ids) == 1
        review = service.get_review(ids[0])
        receipt = service.submit_decisions(
            ids[0],
            1,
            [
                {
                    "id": "a",
                    "fingerprint": review["items"][0]["authorization_fingerprint"],
                    "decision_kind": "approve",
                    "comment": "Keep the public API",
                    "constraints": ["Read-only", "No database migration"],
                }
            ],
            "synthetic-1",
            actor="automated-qualification",
            provenance="synthetic-technical-check",
        )

        def execute(item, constraints):
            assert constraints == ["Read-only", "No database migration", "Keep the public API"]
            answer = turn(
                "Call visual_bridge_get_receipt with receipt_id "
                + receipt["receipt_id"]
                + ". No other tools or actions. Return the actual constraints and comment.",
                "execute",
            )
            receipts(answer, receipt)
            return [
                {
                    "source": "actual-Hermes-MCP-tool-result",
                    "receipt_id": receipt["receipt_id"],
                    "constraints_verified": True,
                }
            ]

        worker = CooperativeAgent(service, ids[0], execute, agent_id="hermes-codex-qualification")
        control = service.request_control(ids[0], "pause")
        assert worker.run_next()["state"] == "paused"
        assert any(
            e["kind"] == "control_updated"
            and e["control_id"] == control["control_id"]
            and e["state"] == "applied"
            for e in service.events(ids[0])
        )
        service.request_control(ids[0], "resume")
        out = worker.run_next()
        assert out["state"] == "succeeded"
        changed = service.request_revision(ids[0], 1, "a", {"scope": "changed-scratch-only"})
        assert "a" not in changed["decisions"]
        assert worker.run_next()["state"] == "waiting"
        shutdown_mcp_servers()
        register_mcp_servers(server)
        answer = turn(
            "Retrieve receipt "
            + receipt["receipt_id"]
            + " using get_receipt, then get_review for "
            + ids[0]
            + ". Confirm the stored receipt constraints; current revision 2 has no approval for changed item a. Do not execute any action.",
            "reconnect",
        )
        receipts(answer, receipt)
        assert any(
            (
                c.get("function", {}).get("name", "").endswith("visual_bridge_get_review")
                for m in answer["messages"]
                if isinstance(m, dict)
                for c in m.get("tool_calls", [])
            )
        )
        assert ReviewService(db).get_receipt(receipt["receipt_id"]) == receipt
        report.update(
            status="technical-workflow-qualified",
            review_id=ids[0],
            receipt_id=receipt["receipt_id"],
            partial_decision=True,
            constraints_preserved=True,
            checkpoint_pause_applied=True,
            revision_invalidates_approval=True,
            reconnect_verified=True,
        )
    except Exception as exc:
        report.update(error_type=type(exc).__name__)
    finally:
        shutdown_mcp_servers()
        report["elapsed_seconds"] = round(time.monotonic() - started, 2)
        (root / "evidence.json").write_text(json.dumps(report, indent=2))
        print(json.dumps({**report, "evidence_directory": str(root)}))
    if report["status"] != "technical-workflow-qualified":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
