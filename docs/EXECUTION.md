# Portable cooperative execution (contract v1)

`CooperativeAgent` binds a durable authorization fingerprint to one execution claim, one agent and one session. Codex remains an optional legacy callable. `JsonProcessExecutor` supplies a second concrete engine using a host-selected argument list and working directory; it runs without a shell.

```python
from agent_visual_bridge import CooperativeAgent, JsonProcessExecutor, ReviewService

service = ReviewService('reviews.sqlite3')
engine = JsonProcessExecutor(['/absolute/python', '/absolute/worker.py'],
                             cwd='/project', timeout=60)
agent = CooperativeAgent(service, 'REVIEW_ID', engine, agent_id='my-engine')
result = agent.run_next()
```

The worker reads one UTF-8 JSON request from stdin. Fields: `contract_version=1`, `execution_id`, `review_id`, `revision`, `agent_id`, `session_id`, `engine_id`, `fingerprint`, `item`, `constraints`, `authorization`. The authorization object includes the exact selected decision, review receipt IDs and the evaluated policy effect. Constraints include the proposal constraints, submitted human constraints, checkpoint constraints and submitted comment. Provider credentials remain under host/engine control.

The worker writes one JSON result to stdout:

```json
{"execution_id":"EXACT_REQUEST_ID","state":"succeeded","evidence":[{"source":"verification","content":"actual observation"}],"message":"Completed"}
```

States are `succeeded`, `failed` (a confirmed failure) and `unknown` (effects cannot be confirmed). A start failure is confirmed failed. A deadline, abnormal exit, malformed output, wrong identity or unclassified callable exception produces unknown. Stderr and exception details are not copied into review events. Output reads are bounded in memory; workers can write to temporary disk files and must be trusted host programs. On POSIX a deadline terminates the spawned process group; Windows terminates the direct child and cannot guarantee descendant termination.

Every claim blocks automatic replay, including failed and unknown claims. Reconcile only after independent verification, using the exact execution ID:

```python
agent.reconcile('item-id', 'succeeded', 'Verified independently', evidence,
                execution_id=result['execution_id'])
```

Reconciliation records the original revision/fingerprint, even when the proposal has changed. It never authorizes a changed item. A confirmed retry needs a newly reviewed proposal/execution boundary; there is no blind retry command.

## Sessions and controls

A cooperative adapter creates a random session ID and a 300-second lease. Call `agent.renew()` explicitly before expiration, then checkpoint; `agent.release()` ends ownership before a handoff. One renewal keeps that session's intent; a new session receives no old session controls. Session IDs cannot be reassigned to a different agent, including after expiry.

The browser lists active sessions. With multiple agents, a human must select a session before a control is submitted. Controls bind to agent/session, and acknowledgement requires that same active owner. The transaction that claims an action rechecks the lease, policy, proposal and pending commands. Ambiguous controls fail rather than choose the latest agent.

Pause/resume/stop/priority/constraint are cooperative controls **between actions**. They do not interrupt a running LLM or external action. A requested command becomes applied only at its checkpoint. Session expiry blocks the next claim; it does not prove cancellation of an existing action. The adapter enforces policy only for actions routed through it.

For MCP integrations, `visual_bridge_register_agent` accepts `session_id`/`lease_seconds` and doubles as explicit renewal; `visual_bridge_release_agent` releases ownership. Acknowledgement accepts `agent_id`/`session_id`; progress can include an existing `execution_id`. Browser agent endpoints expose the same arguments and require the agent token.

Older registrations without a session remain supported as **legacy, unbound** integrations. IDs and leases provide coordination and auditability within the trusted local host; they are not cryptographic user authentication. All local MCP clients share the selected server capability. Commercial hosts must enforce human-only App tool visibility.

## Evidence limits

The real subprocess test verifies JSON I/O and mandate preservation with a Python worker. It does not qualify a second LLM product. Hermes and OpenCode require separately successful provider inference, MCP calls and receipt verification before runtime support can be claimed.
