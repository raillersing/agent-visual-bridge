"""Optional read-only Codex CLI adapter."""
from __future__ import annotations

from ..models import ValidationError, canonical


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
