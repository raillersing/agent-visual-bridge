from agent_visual_bridge.mcp.server import handle_rpc_call


def test_mcp_initialize():
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }
    resp = handle_rpc_call(msg)
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "agent-visual-bridge"


def test_mcp_tools_list():
    msg = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    resp = handle_rpc_call(msg)
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "visual_bridge_ask_human" in tool_names
    assert "visual_bridge_read_report" in tool_names
