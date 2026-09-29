#!/usr/bin/env python3
"""Example demonstrating Python SDK usage of Agent Visual Bridge."""

from agent_visual_bridge import VisualBridge

# 1. Prepare items to review
items = [
    {
        "id": "item-1",
        "title": "Migrate to SQLite for CI tests",
        "description": "Reduces GitHub Actions run time by 65%.",
        "severity": "medium",
    },
    {
        "id": "item-2",
        "title": "Enable CSRF on API routes",
        "description": "Enforce SameSite=Lax and CSRF cookie verification.",
        "severity": "critical",
    },
]

# 2. Initialize bridge (auto-detects 'audit' from severity)
bridge = VisualBridge.from_data(
    {"items": items},
    title="Infrastructure & Security Review",
    subtitle="Review proposed changes before automated deployment",
)

# 3. Save to an offline, zero-dependency HTML file
output_file = bridge.save_html("reports/infra_review.html")
print(f"Generated report: {output_file}")

# 4. Synchronous one-liner for AI Agents:
# Opens browser, runs ephemeral server, and waits for user submit:
# feedback = VisualBridge.ask_human(
#     items=items,
#     title="Human Review",
#     mode="serve"
# )
# print("Received human feedback:", feedback["summary"])
