# Migration

## 0.3.0.dev1: MCP interaction change

The official MCP `visual_bridge_ask_human` returns immediately by default. Pass `wait: true` to preserve the blocking receipt workflow; `open_browser: true` explicitly opens the server's browser. A wait timeout no longer expires the review. Poll `visual_bridge_get_review`, then fetch its receipt; `visual_bridge_open_review` renews browser access. The legacy compatibility dispatcher and synchronous Python/CLI waiting APIs keep their existing behavior.

Detached browser sessions survive MCP shutdown. Stop them for a specific database with `agent-bridge --db PATH browser-stop`. Schema version remains 1; no SQLite migration is performed. Setup does not move existing review databases. The new project installer uses `.agent-visual-bridge/reviews.sqlite3` unless you manually adapt its exported configuration to your existing path.

Existing `CodexTextExecutor` imports from the package and `adapters` remain valid; the implementation now lives in `executors/codex.py`. See [the common integration guide](AGENT_INTEGRATION.md) for client configuration and diagnostic limits.

## Migration to 0.2

## Compatibility

`VisualBridge`, `auto`, `init`, `read`, `watch`, `serve`, and `ask_human` remain available. Inputs may use legacy lists and `items`, `points`, `tasks`, `checks`, or `lots`. Old `desc` and string options normalize into the versioned contract. Useful extra item fields are retained. Duplicate IDs, unknown report types, invalid fields and cyclic dependencies now raise errors.

## Intentional corrections

- Agent statuses, preselected approvals and comments no longer create human permission.
- Comments survive independently of the decision. Markdown includes pending comments.
- `ask_human` and waiting CLI commands return the complete receipt; use `decisions` plus `pending`, not an assumed fully approved list.
- Timeout raises `TimeoutError` / a nonzero CLI exit, and expires a waiting server session.
- `watch` requires an explicit embedded submission. Saving an untouched proposal or arbitrary file change is insufficient.
- `read` defaults to JSON; `--markdown` is explicit.
- Browser submission no longer shuts down a review before persistence. A synchronous waiting wrapper returns the first explicit partial receipt; continue via `resume` and durable retrieval for subsequent decisions.
- The MCP executable requires the optional official SDK, Python 3.10+. Core report generation remains dependency-free on Python 3.9+.

## Durable API

Use `ReviewService.create_review` and retain its `review_id`. Submit only explicit human decisions with `revision`, each item's `authorization_fingerprint`, and a unique request key. Fetch immutable receipts by ID after a restart. Revision calls require the current revision. Decisions on changed items and transitive dependents are invalidated, unchanged decisions retained.

Offline JSON import is marked `imported-artifact-unverified`; import does not authenticate an external signer. Do not pass agent-produced submissions off as authenticated human decisions. The local service is intended for a trusted local operator.

Back up an existing SQLite file before future format upgrades. Schema version 1 is created transactionally; a newer unknown version is refused. Version 0.1 had no persisted review database to migrate.

## Execution

Existing clients must explicitly bind their executor to `CooperativeAgent` to enforce decisions. Calling the bridge alone does not pause or govern arbitrary agents. Register only controls implemented by your engine. Pause/stop apply between actions, not during a running external tool. Use evidence-backed progress and explicit reconciliation for uncertain outcomes; do not automatically repeat a claimed action.
