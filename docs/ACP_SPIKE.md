# ACP boundary study — 5 October 2026

Status: design study completed; no ACP adapter shipped or runtime-qualified. ACP remains optional after the two-client v0.3 runtime gate.

The official [ACP overview](https://agentclientprotocol.com/protocol/v1/overview) describes agent/client sessions, prompt turns, progress updates and cancellation. [Tool-call updates](https://agentclientprotocol.com/protocol/v1/tool-calls) carry execution observations; tool names and reported states do not grant authorization.

Proposed integration, subject to a dedicated editor/agent pilot:

| ACP boundary | Bridge mapping | Required guard |
|---|---|---|
| `session/new` or negotiated `session/load` | Explicit attachment to a bridge review and agent session | Store a separate mapping; never infer identity from a review ID |
| `session/update` plan/tool call | Proposal revision or progress evidence | Informational state must not become human approval |
| `session/request_permission` | Human review + immutable receipt | Bind exact requested tool scope and revision; reject missing/mismatched receipt |
| `session/cancel` | Requested control, followed by engine observation | Cancellation notification alone does not establish termination or rollback |
| Transport loss | Unknown execution until verified | No automatic replay of a possibly executed action |

Implementation should be an optional adapter over `ExecutionRequest`/`ExecutionResult`, not another core transport or a provider-key store. Negotiate capabilities, map host-specific states conservatively and retain the exact ACP session/tool-call identifiers as evidence.

Acceptance scenarios for a future adapter: two editor/agent pairs; permission denied; constrained permission; cancellation during a tool call; unsupported session load; disconnect after dispatch; changed proposal; duplicate notifications. Each requires actual engine observation and durable receipt comparison. The current subprocess and SDK tests do not qualify these ACP cases.
