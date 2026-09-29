# 🌉 Agent Visual Bridge (`agent-visual-bridge`)

[![CI](https://github.com/raillersing/agent-visual-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/raillersing/agent-visual-bridge/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/agent-visual-bridge.svg)](https://pypi.org/project/agent-visual-bridge/)
[![Python versions](https://img.shields.io/pypi/pyversions/agent-visual-bridge.svg)](https://pypi.org/project/agent-visual-bridge/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#zero-dependencies)

**The missing Human-in-the-Loop (HITL) visual arbitration bridge for AI coding agents.**

Stop scrolling through 200 lines of messy terminal Markdown. Transform complex AI agent audits, refactoring roadmaps, code reviews, and architectural trade-offs into **crisp, interactive, local-first visual dashboards** in one command.

```
       ┌─────────────────┐
       │   AI Agent      │  (Claude Code, Codex, Antigravity, Cursor, Windsurf)
       └────────┬────────┘
                │  agent-bridge auto audit.json --serve
                ▼
   ┌─────────────────────────┐
   │   Visual Bridge HTML    │  ◄── 100% Offline, Zero-Dependency Browser UI
   └────────────┬────────────┘
                │
                │  Human clicks, adjusts status & types notes
                │  1-Click "Valider & Envoyer à l'Agent"
                ▼
       ┌─────────────────┐
       │   AI Agent      │  ◄── Receives structured mandate & resumes execution!
       └─────────────────┘
```

---

## ⚡ Why Agent Visual Bridge?

Autonomous coding agents are amazing, but when they need human guidance on:
- **Complex multi-point audits** (e.g. verifying 20 business rules)
- **Multi-phase refactoring plans** (e.g. 6 lots with dependencies and allowed scopes)
- **PR Code Reviews & architectural trade-offs**

...they dump hundreds of lines in your terminal. You lose context, can't easily filter, and end up chatting back and forth for 20 minutes to communicate simple adjustments.

**Agent Visual Bridge solves this instantly:**
1. **Zero-Dependency & 100% Local-First :** Single HTML file with embedded styles and JS. No CDN requests, no telemetry, no tracking. Your code and proprietary business rules never leave your machine.
2. **Smart Auto-Detection :** Automatically classifies input as an `audit`, `plan`, `review`, or `decision` matrix and renders the tailored UI.
3. **Bi-Directional Feedback Loop :**
   - **Ephemeral Server :** An instant local micro-server receives the human's 1-click submission and unblocks the agent synchronously.
   - **File Watcher :** Agent wakes up as soon as the user saves the HTML file on disk.
   - **CLI Auto-Reader :** Parses human decisions from saved HTML into structured JSON / Markdown with zero hassle.
4. **Model Context Protocol (MCP) :** Ready to plug as an MCP tool in Claude Desktop, Cursor, and Windsurf.

---

## 📦 Installation

```bash
pip install agent-visual-bridge
```

Or install in development mode from source:

```bash
git clone https://github.com/raillersing/agent-visual-bridge.git
cd agent-visual-bridge
pip install -e .
```

---

## 🚀 Quickstart

### 1. Command Line Interface (CLI)

#### Create a starter template
```bash
agent-bridge init audit -o audit.json
```

#### Generate interactive dashboard & wait for human review
```bash
agent-bridge auto audit.json --serve
```
*Your browser automatically pops up. Review points, toggle statuses (✅ Validé, ✏️ À ajuster), type instructions, and click **🚀 Valider & Envoyer à l'Agent**. The agent immediately receives your feedback and proceeds.*

#### Parse an already saved HTML file
```bash
agent-bridge read report.html --markdown
```

---

### 2. Python SDK (Agent Native)

Agents can invoke the visual bridge directly within Python:

```python
from agent_visual_bridge import VisualBridge

items = [
    {
        "id": "point-1",
        "title": "Strict Django Permissions",
        "severity": "critical",
        "description": "Ensure has_object_permission is checked on sensitive endpoints."
    },
    {
        "id": "point-2",
        "title": "Database Locking Strategy",
        "severity": "high",
        "description": "Add select_for_update() to prevent race conditions during payment."
    }
]

# Synchronous one-liner: opens browser, waits for human decision, returns result!
feedback = VisualBridge.ask_human(
    items=items,
    title="Security & Concurrency Review",
    mode="serve"  # or "watch"
)

print("Human Decisions:", feedback["decisions"])
```

---

## 🔌 Model Context Protocol (MCP) Integration

Agent Visual Bridge can run as an MCP server for AI clients like **Claude Desktop**, **Cursor**, or **Windsurf**.

Add to your `claude_desktop_config.json` or `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "visual-bridge": {
      "command": "python",
      "args": ["-m", "agent_visual_bridge.mcp.server"]
    }
  }
}
```

This equips your AI assistant with the following tools:
- `visual_bridge_ask_human(title, items, type="auto")`: Launches visual review and pauses until human confirmation.
- `visual_bridge_read_report(html_path)`: Reads human choices from a previously generated report.

---

## 🧩 Templates & Auto-Detection

`agent-visual-bridge` analyzes your input keys and text to automatically pick the right UI layout:

| Type | When Detected | Key Features |
|------|---------------|--------------|
| **Audit** | `severity`, `status`, `verdict`, `compliance` | Severity badges, Pass/Fail counters, filter by risk level |
| **Plan** | `lot`, `phase`, `step`, `dependencies`, `scope` | Worktree lots, dependency flow, scope boundary warnings |
| **Review** | `diff`, `file`, `additions`, `deletions` | Syntax-highlighted diffs, per-file approval checklist |
| **Decision** | `options`, `choices`, `tradeoffs`, `pillar` | Interactive radio choices, architecture comparison matrix |

---

## 🛠️ Development & Contributing

We welcome contributions from the community!

```bash
# Clone the repository
git clone https://github.com/raillersing/agent-visual-bridge.git
cd agent-visual-bridge

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint code
ruff check .
```

---

## 📄 License

This project is open-source software licensed under the [MIT License](LICENSE).
Distributed freely for personal, open-source, and commercial use.
