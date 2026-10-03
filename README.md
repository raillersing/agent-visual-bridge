# Agent Visual Bridge

A local interface for reviewing agent proposals, asking questions and returning durable human decisions. Version 0.2 adds versioned reviews, immutable receipts and cooperative execution controls.

The Python core uses only the standard library (Python 3.9+). Reports embed their CSS and JavaScript and work offline. SQLite stores reviews locally. Optional agent integrations can send the authorized task to their configured provider; the bridge does not store provider credentials.

## Install

```bash
pip install -e .
# Official MCP server, Python 3.10+:
pip install -e '.[mcp]'
```

## Review a proposal

```bash
agent-bridge init plan -o proposal.json
agent-bridge auto proposal.json --serve --timeout 600 --feedback-out receipt.json
```

The browser opens a review. Choose decisions, add independent comments and constraints, inspect the mandate, then explicitly submit. The command returns the complete receipt, including undecided items. Timeout raises an error; absence of a response grants no permission. A returned receipt does not itself execute the task.

For reviews that span several sessions:

```bash
agent-bridge --db reviews.sqlite3 create proposal.json -o reports/review.html
agent-bridge --db reviews.sqlite3 list
agent-bridge --db reviews.sqlite3 resume REVIEW_ID
agent-bridge --db reviews.sqlite3 get REVIEW_ID
agent-bridge --db reviews.sqlite3 receipt RECEIPT_ID
```

`resume` prints a local URL and serves until interrupted. Decisions remain in SQLite after restart. Set `AVB_DB` or use `--db` before the subcommand; the default is `~/.local/share/agent-visual-bridge/reviews.sqlite3`.

Offline reports export explicitly submitted JSON and HTML without session tokens. Import using `agent-bridge --db reviews.sqlite3 submit REVIEW_ID decisions.json`. Imported files have unverified provenance; they are suitable for a trusted local operator and do not authenticate a human. `read report.html --markdown` preserves comments even for undecided items. In `watch` mode, replace the watched artifact with the explicitly submitted download; a browser download does not automatically replace the original.

## The decision contract

An item has one interaction kind:

| Kind | Meaning | Decisions |
|---|---|---|
| `inform` | Present information | No authorization control |
| `clarify` | Obtain an answer or option | `answer`, `choose`, `defer`, `reject`, `request_changes` |
| `authorize` | Permit proposed actions | `approve`, `request_changes`, `reject`, `defer` |

A comment never implies approval. Agent-supplied decision/status fields never count as human decisions. Every submission specifies the review revision and the exact item authorization fingerprint. Changes to an item or its transitive dependencies invalidate affected decisions; unchanged decisions survive a revision. Partial submissions leave other items pending. Repeated submissions with the same key return the same receipt; different content with that key conflicts.

Four views share this contract: audit findings and provenance, plan scopes and dependencies, review diffs and checks, and decision options and tradeoffs. Keyboard controls, search, filters, narrow layouts and an explicit preview are included. Questions and replies preserve item, author and revision. A human can revise scope, dependencies, options and order through a new version.

[Input and submission schemas](src/agent_visual_bridge/schemas/) describe JSON shapes. Runtime validation additionally checks IDs, dependency cycles, fingerprints and legal decision transitions.

## Python integration

```python
from agent_visual_bridge import VisualBridge

receipt = VisualBridge.ask_human(
    title='Review the API change',
    items=[{'id': 'api', 'title': 'Preserve the public API',
            'scope': 'src/', 'consequences': 'Only internal implementation changes'}],
    mode='serve', timeout=600,
)
print(receipt['decisions'], receipt['pending'])
```

For execution, bind your real executor to `CooperativeAgent`. It receives the approved item, all constraints and the approval comment. It runs only eligible actions whose dependencies have succeeded. Explicit project rules default to `ask`; `deny` wins and rules are rechecked before an action starts. Presentation preferences grant no permissions.

```python
from agent_visual_bridge import ReviewService, CooperativeAgent

service = ReviewService('reviews.sqlite3')
# execute_action must perform the action and verify its outcome before returning evidence.
worker = CooperativeAgent(service, review_id, execute_action)
result = worker.run_next()
```

Pause, resume, stop, priority and constraints apply at checkpoints between actions. The interface distinguishes requested, acknowledged, applied, rejected and unsupported. It cannot interrupt an arbitrary tool already running or govern tools that bypass the adapter. Execution claims prevent duplicate starts; uncertain outcomes need explicit reconciliation before further action. Completed actions are not undone by revocation.

`CodexTextExecutor` provides an optional installed Codex CLI integration for read-only synthesis. Its `action.required_tools` and `action.required_output` checks prevent a refused required tool or missing literal evidence from being treated as successful. These checks establish the execution contract, not the general correctness of a model's prose. See [qualification evidence](docs/QUALIFICATION.md) and [the cooperative example](examples/cooperative.py).

## MCP and native interfaces

Install the `mcp` extra, then configure your MCP client:

```json
{"mcpServers":{"visual-bridge":{"command":"/absolute/path/to/python","args":["-m","agent_visual_bridge.mcp.server"],"env":{"AVB_DB":"/absolute/path/reviews.sqlite3"}}}}
```

The executable uses the official Python SDK **1.30.0**. It exposes creation, revision, retrieval, receipts, questions, agent registration, progress and control acknowledgments. `visual_bridge_ask_human` opens the local browser and awaits a submission. `visual_bridge_ask_question` uses form elicitation when negotiated and returns an explicit fallback otherwise; decline and cancel remain distinct.

`visual_bridge_open_review` advertises an MCP Apps resource when the host negotiates `io.modelcontextprotocol/ui`. The embedded App uses the official Apps SDK **2.0.3** and submits through an app-only action tool. Clients without Apps receive structured/textual review data without the native metadata or app-only tool. App visibility relies on the host's advertised capability; it is not independent cryptographic proof of human authorship. A reference host is tested; commercial desktop hosts still require qualification.

## Security and limits

The local server binds to loopback, checks Host and Origin, uses distinct human/agent session tokens, caps request size, and serves a restrictive CSP. Exports omit tokens and safely escape embedded JSON. Agent tokens cannot submit human decisions. Local filesystem access and an MCP host are trusted boundaries; this is a single-user local tool, not a remotely hosted authorization service.

Project preferences persist language, detail and notifications. English translates static controls; dynamic messages remain French in this release. Policy rules describe exact operations, relative path scopes, external effects and reversibility. The host must truthfully describe and enforce its actions.

Local metrics measure active review segments, submissions, questions, revisions, executed actions and resumes. Understanding and perceived effort require manual observations. [The pilot protocol](docs/PILOT.md) provides comparable terminal/bridge tasks; no user benefit is claimed without those observations.

## Development

```bash
pip install -e '.[dev,qualification]'
python -m playwright install chromium
cd ui
npm ci
npm run build
npm run build:host
cd ..
ruff check src/ tests/
pytest -q
python -m build
```

The locked Node dependencies are used to build the native App; Node is unnecessary for installed report generation. CI runs the core on Python 3.9–3.14 and the browser/MCP qualification suite on Python 3.12, then checks the installed wheel without extras.

- [Implementation plan and delivery status](docs/IMPLEMENTATION_PLAN.md)
- [Migration guide](docs/MIGRATION.md)
- [Qualification matrix and limitations](docs/QUALIFICATION.md)
- [Release notes](docs/RELEASE_NOTES.md)

MIT license. No package publication has been performed as part of this implementation.
