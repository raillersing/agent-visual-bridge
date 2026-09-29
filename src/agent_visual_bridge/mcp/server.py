"""Model Context Protocol (MCP) Server for Agent Visual Bridge.

Provides stdio JSON-RPC 2.0 interface for AI assistants (Claude, Cursor, Windsurf)
to request visual human feedback and read decisions.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict

from agent_visual_bridge.core import VisualBridge
from agent_visual_bridge.parser import parse_html_file


TOOLS = [
    {
        "name": "visual_bridge_ask_human",
        "description": "Open an interactive visual report in the human user's browser, wait for their decisions and remarks, and return structured feedback.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title of the review or audit"},
                "items": {
                    "type": "array",
                    "description": "List of items, points, or tasks for the human to review",
                    "items": {"type": "object"},
                },
                "type": {
                    "type": "string",
                    "enum": ["auto", "audit", "plan", "review", "decision"],
                    "default": "auto",
                    "description": "Report type (or auto to detect)",
                },
                "output_path": {
                    "type": "string",
                    "default": "reports/human-review.html",
                    "description": "File path where HTML will be generated",
                },
                "timeout": {
                    "type": "number",
                    "default": 600,
                    "description": "Maximum time in seconds to wait for user submission",
                },
            },
            "required": ["title", "items"],
        },
    },
    {
        "name": "visual_bridge_read_report",
        "description": "Read an already saved Visual Bridge HTML file and extract user remarks and decisions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "html_path": {"type": "string", "description": "Path to the saved HTML file"}
            },
            "required": ["html_path"],
        },
    },
]


def handle_rpc_call(msg: Dict[str, Any]) -> Dict[str, Any]:
    """Handle standard MCP JSON-RPC messages."""
    msg_id = msg.get("id")
    method = msg.get("method")
    params = msg.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "agent-visual-bridge", "version": "0.1.0"},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "visual_bridge_read_report":
            path = arguments.get("html_path")
            try:
                data = parse_html_file(path)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": data["mandate_markdown"]},
                            {"type": "text", "text": json.dumps(data, indent=2)},
                        ]
                    },
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "isError": True,
                    "result": {"content": [{"type": "text", "text": f"Error: {e}"}]},
                }

        elif tool_name == "visual_bridge_ask_human":
            title = arguments.get("title", "Review Request")
            items = arguments.get("items", [])
            output_path = arguments.get("output_path", "reports/human-review.html")
            timeout = float(arguments.get("timeout", 600))

            try:
                result = VisualBridge.ask_human(
                    items=items,
                    title=title,
                    output_html=output_path,
                    mode="serve",
                    timeout=timeout,
                    open_browser=True,
                )
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result.get("markdown") or json.dumps(result, indent=2),
                            }
                        ]
                    },
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "isError": True,
                    "result": {"content": [{"type": "text", "text": f"Error: {e}"}]},
                }

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def run_mcp_server() -> None:
    """Run MCP server over stdio."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = handle_rpc_call(req)
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"MCP Server error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    run_mcp_server()
