# Qualification — 0.2.0

Date: 2026-10-02. Implementation delivered locally. External product qualification remains partial. No commit, push, release publication or remote CI run is claimed.

## Verified environment and results

| Layer | Evidence | Result |
|---|---|---|
| Complete suite | Python 3.12.13, pytest 9.1.1; `pytest -q` | **59 passed**, no skipped tests |
| Static checks | Ruff 0.16.10, `ruff check src/ tests/`; `git diff --check` | Passed |
| Python 3.9 core | CPython 3.9.25, pytest 8.4.2; optional browser/MCP/schema modules explicitly excluded | **42 passed** |
| Python 3.14 core | CPython 3.14.4; installed wheel; same explicit exclusions | **42 passed** |
| Browser | Playwright 1.63.0, real Chromium; local HTTP and AppBridge iframe | All browser journeys passed |
| Minimal installation | Wheel installed `--no-deps` on Python 3.9 and 3.14; `scripts/package_smoke.py` | HTML, durable receipt reread, packaged assets and schemas passed, MCP absent |
| Distribution | `python -m build` builds wheel from sdist | Wheel and sdist generated in `/tmp/avb-dist` |
| Native bundle | Apps SDK 2.0.3, esbuild 0.28.2; locked `npm ci` / builds | Bundles generated; npm audit reports zero vulnerabilities |
| MCP protocol | Official Python SDK 1.30.0 server and client over a real stdio child process | Structured responses, errors, ping, capability filtering, Apps submission, elicitation accept/decline/cancel and fallback passed |

The complete suite covers invalid inputs, ignored agent approvals, independent comments, partial decisions, SQLite reopen, idempotency and concurrent submissions, stale revisions, transitive dependency invalidation, policy revocation, cooperative controls, HTTP origins/roles/isolation, explicit timeout, CLI subprocess import, JSON schemas, browser reload, offline JSON/HTML export, malicious embedded text, four view types and native App SDK interaction.

The keyboard journey runs at **320 px** with **150% root text size**, checks absence of horizontal page overflow, submits via keyboard, verifies the stored receipt and checks that submitted fields become disabled. This does not constitute full screen-reader, Safari, Firefox, mobile-device or WCAG certification.

CI has been updated to run the core on Python 3.9–3.14, browser/MCP qualification on 3.12 and minimal installed-wheel smoke verification. Only the local runs above have been observed; intermediate Python versions and remote CI await actual workflow execution.

## Real agent qualification

An authenticated **Codex CLI 0.160.0** executed a read-only synthesis task through `CooperativeAgent` and `CodexTextExecutor`:

1. A local synthetic test operator approved one item, with two constraints and an independent comment.
2. The worker applied a receipt-ID constraint at a cooperative checkpoint.
3. Codex started the installed official MCP server, called `visual_bridge_get_receipt` successfully, and received the durable receipt.
4. The executor required successful completion of that exact tool and literal output evidence.
5. Codex returned `AVB_CONSTRAINTS_PRESERVED`, both constraints and the comment; the worker persisted success evidence.

[Recorded execution evidence](evidence/codex-readonly.json) includes the review/receipt IDs, successful tool status, actual output and CLI-reported token usage: 37,448 input tokens, 29,312 cached input tokens, 165 output tokens. Token accounting is reported by the CLI; a separate model/provider identity is not exposed in this evidence.

An initial probe finished its model turn while the required MCP tool was refused. That probe is **not** considered successful. It exposed a false-success path, now covered by four executor regression tests. The successful rerun used an invocation-scoped configuration permitting only the receipt-read tool:

```toml
[mcp_servers.avb]
enabled_tools = ["visual_bridge_get_receipt"]
[mcp_servers.avb.tools.visual_bridge_get_receipt]
approval_mode = "approve"
```

The CLI retained its read-only sandbox. Credentials remain managed by the installed CLI. This is a runtime integration check with synthetic decisions, **not a human usability study**. It does not qualify arbitrary filesystem edits, long-running parallel workers or externally irreversible operations.

Configuration was checked against the official [Codex noninteractive documentation](https://developers.openai.com/codex/noninteractive) and [MCP configuration documentation](https://developers.openai.com/codex/mcp). The CLI integration is optional; it does not change the core's dependency requirements.

## Client matrix

| Client | Scope actually exercised | Status |
|---|---|---|
| Local Chromium browser | Review → preview → submit → durable receipt → reload; questions, revision and controls | Qualified for tested journeys |
| Official SDK stdio client without Apps | Protocol, structured review, local fallback, distinct elicitation outcomes | Qualified for tested protocol |
| Apps SDK AppBridge reference host in Chromium | iframe App initialization, tool result, human submission, host message, durable HTTP service | Qualified reference integration |
| SDK client advertising Apps | UI-only tool exposure and actual stdio App action submission | Qualified protocol path |
| Codex CLI 0.160.0 | Real MCP receipt retrieval and approved read-only synthesis | Qualified narrow runtime path |
| Claude CLI | Installed, but live probe returned “Not logged in” | Unqualified: authentication unavailable |
| Claude Desktop, Cursor, other commercial native hosts | No running authenticated host exercised | Pending |

The reference-host browser test forwards App actions through the local service; the separate stdio test exercises the actual SDK App action tool. These are complementary technical checks, not a commercial client demonstration. MCP Apps visibility is enforced by the host; advertised capabilities alone are not proof of an independent human author.

## Remaining external gates

- Run the three-task comparative pilot with consenting participants using [PILOT.md](PILOT.md). Collect scope understanding and effort rather than inferring them from approvals. No study records have been fabricated.
- Exercise at least one commercial MCP Apps host and its sandbox/CSP/theme behavior, then record the host version and outcomes.
- English static controls are translated; dynamic status/error messages still require complete localization.
- Observe the updated remote CI matrix before claiming remote qualification.
- Publish only after a separate release decision. Existing actions cannot be undone by the bridge; pause/stop apply at cooperative checkpoints.
