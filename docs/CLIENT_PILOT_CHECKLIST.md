# Remaining external qualification

Status: prepared. No commercial MCP Apps qualification or participant observation is claimed.

## Hermes and OpenCode

Use a disposable project and a separate bridge database. Preserve provider credentials and global client configuration. Enable only required bridge tools; never grant wildcard action permission for a test.

1. Record actual client, provider/model, bridge revision and environment versions.
2. Have the agent create a proposal with one authorization, one clarification and a dependency.
3. Open the durable review. Submit a partial decision with a comment and two constraints; mark automated submissions explicitly synthetic.
4. Require a successful **actual MCP get_receipt tool result**, matching receipt ID, revision/fingerprint, comment and both constraints. A final model message alone is insufficient.
5. Verify the execution input carries those constraints; execute a bounded read-only task. Persist verifiable evidence, not an invented summary.
6. Disconnect the client, reconnect explicitly, retrieve the same receipt, revise the scope and verify the old agreement does not authorize the changed action.
7. Capture pause requested/applied with the cooperative adapter and the correct agent session. Do not describe this as interrupting an active LLM call.

Observed blockers on 2026-10-05: OpenCode's configured Ollama Cloud provider returned Unauthorized before a successful MCP read; Hermes's configured local provider at 127.0.0.1:11434 was unreachable and inference failed. Reconnect the selected provider in its own client, then rerun. No credentials should be added to this repository. See sanitized [observed evidence](evidence/qualification-20261005.json).

## Commercial MCP Apps / elicitation

Choose an authenticated installed host. Record its advertised capabilities and actual displayed UI. Verify initialization, partial submission, reply thread, changed revision, durable receipt after reload/reconnect, and fallback when Apps/form elicitation are absent or refused. Verify agent-side calls cannot submit UI-only human decisions under the host's visibility rules. Keep browser fallback available and do not infer a human author from capability advertisement alone.

The reference AppBridge browser host and SDK tests are technical qualification. They do not substitute for a commercial host journey.

## Human pilot

Use [PILOT.md](PILOT.md) with consenting participants and pseudonymous IDs. Record only actual observations. Keep synthetic technical records out of pilot observations. Compare submitted constraints, stored receipts and executor input; capture comprehension of pending/deferred actions and between-action controls. Export metrics voluntarily; do not publish private task text or credentials.
