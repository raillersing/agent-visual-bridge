# Qualification

## 0.3.0.dev2 — 2026-10-05, implementation qualified; external gate PARTIAL

| Layer | Observed result |
|---|---|
| ERP-installed package, implementation `6455d5a`, complete suite | **102 passed**, no skips, 130.83 seconds; separate temporary databases |
| Latest request metadata `4e480a8`, subprocess/session/lifecycle tests | **33 passed**, 2.00 seconds; installed ERP package + real HTTP **36 passed**, 10.99 seconds |
| Real MCP Streamable HTTP client and sockets | **3 passed**; authentication, Host/Origin, sessions, reconnect and durable receipts |
| Python 3.9 minimal core at HTTP implementation | **69 passed, 4 optional skips** |
| ERP migration and preservation | Existing SQLite counts 1 review / 0 receipts / 1 revision / 1 event unchanged; immutable hashes preserved; 137 pre-existing files unchanged |
| Installed minimal wheel, Python 3.9, Codex absent from PATH | HTML, persistence, receipt, assets, schemas, setup and detached browser passed; no optional dependencies |
| Backup restoration | Disposable SQLite restoration passed integrity check and immutable comparisons; active database preserved |
| Hermes 0.18.2 real agent/inference | Failed before a successful MCP read; configured local provider endpoint unreachable |
| OpenCode 1.18.34 real CLI/inference | Configured Ollama Cloud returned APIError Unauthorized; no successful MCP read |
| Commercial Apps / human pilot | **Not qualified / 0 participants**; checklist and observation protocol prepared |
| ACP | Boundary study only; no runtime adapter |

[Sanitized current evidence](evidence/qualification-20261005.json) records implementation revisions, failure categories and synthetic technical scope. The final preservation reread confirmed the same database; one pre-existing ERP report changed concurrently after the initial 137-file check and was left untouched. Credentials and raw provider logs are excluded. The successful JSON subprocess worker is a real second execution engine; it is not a qualified second LLM product. Provider authentication remains managed by the chosen clients.

The milestone stays **PARTIAL** until two non-Codex clients finish the [external journey](CLIENT_PILOT_CHECKLIST.md). Stable package publication is not claimed. Older evidence below is retained as historical snapshots.

## 0.3.0.dev1 — 2026-10-03, local implementation, external qualification PARTIAL

Delivered locally: detached browser supervisor, nonblocking MCP workflow, form-mode capability checks, explicit fallback, nine client configuration exporters, JSONC preservation, optional TOML editing, CLI diagnostics and neutral instructions. The Codex executor is isolated with compatible imports. HTTP transport and a second execution engine are not delivered.

Final local evidence:

| Layer | Result |
|---|---|
| Complete Python 3.12 suite with browser/MCP extras | **87 passed**, no skips, 61.02 seconds |
| Python 3.9.25 / 3.14.4 core, explicit browser/MCP/schema exclusions | **59 passed, 2 skips** each: optional TOML and SDK handshake |
| Static checks | Ruff, `git diff --check`, JavaScript syntax and local documentation links passed |
| Installed wheel, Python 3.9, no optional dependencies | HTML, persistence, receipt, packaged assets/schemas, Gemini configuration and detached browser passed |
| Official SDK stdio | URL-only clients never receive forms; refused elicitation falls back without a decision; disconnect and wait timeout preserve awaiting reviews; explicit browser fallback from an Apps-capable host |
| Detached process + HTTP | Originating process exits; browser still accessible; submission and SQLite receipt reread; concurrent cold starts reuse one supervisor; failed startup child is terminated; access expiry preserves pending review |
| Installer | Nine formats/fragments; dry-run, idempotence, unrelated comments/configuration preservation, backups, conflict refusal and relocation |
| Windows | Portability job added to CI; no Windows runtime result claimed |

### Real clients in an isolated scratch project

| Client | Observed outcome | Qualification |
|---|---|---|
| Claude Code 2.1.261 | Read-only MCP probe returned `Not logged in` | Authentication unavailable; no completed runtime journey |
| Gemini CLI 0.46.0 | `IneligibleTierError` on the configured Code Assist authentication path | Authentication refused for this setup; no completed runtime journey |
| Hermes 0.18.2 | Real `hermes mcp test visual-bridge` connected and discovered the tools | Configuration and discovery verified; no LLM inference or submitted review qualified |
| Cursor, VS Code, OpenCode, Cline, Antigravity | Exporters available, no running client exercised | Configuration-only; native capabilities unknown |

[Sanitized observed client evidence](evidence/agnostic-clients.json) records versions, results and timings. Raw local logs are excluded; no credentials are copied into evidence. No simulated result is presented as successful model execution or a human study. Provider settings and global trust were preserved.

The v0.3 milestone remains PARTIAL until two non-Codex clients complete the real journey. Commercial Apps, human pilot and ERP migration remain pending. The results above describe the local qualification snapshot of 2026-10-03; subsequent commits, pull requests and CI results are tracked in GitHub. No package publication is claimed.

## 0.2.0 — historical evidence

The local qualification below was recorded on 2026-10-02. Version 0.2 was subsequently merged through [PR #1](https://github.com/raillersing/agent-visual-bridge/pull/1); its [post-merge CI](https://github.com/raillersing/agent-visual-bridge/actions/runs/37101221287) passed on 2026-10-03. These delivery results do not qualify the new 0.3 changes.

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

The v0.2 CI ran the core on Python 3.9–3.14, browser/MCP qualification on 3.12 and minimal installed-wheel smoke verification. The remote run is linked above; the measurements in this historical table are the original local runs.

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
- In v0.3, browser lifecycle messages were translated; agent-authored content and canonical receipt text preserve their original language. Native hosts still need qualification.
- Observe remote CI for the new v0.3 code, including the Windows portability job, before claiming remote qualification.
- Publish only after a separate release decision. Existing actions cannot be undone by the bridge; pause/stop apply at cooperative checkpoints.
