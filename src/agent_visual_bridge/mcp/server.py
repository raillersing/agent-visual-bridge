"""Compatibility dispatcher for embedders; executable uses the official SDK."""
from __future__ import annotations

import json

from ..core import VisualBridge
from ..parser import parse_html_file

TOOLS = [
    {'name': 'visual_bridge_ask_human', 'description': 'Request explicit human review',
     'inputSchema': {'type': 'object', 'properties': {'title': {'type': 'string'},
       'items': {'type': 'array', 'items': {'type': 'object'}}, 'type': {'type': 'string'},
       'output_path': {'type': 'string'}, 'timeout': {'type': 'number'}}, 'required': ['title', 'items']}},
    {'name': 'visual_bridge_read_report', 'description': 'Read an imported report (unverified provenance)',
     'inputSchema': {'type': 'object', 'properties': {'html_path': {'type': 'string'}}, 'required': ['html_path']}},
]


def handle_rpc_call(msg):
    if 'id' not in msg:
        return None
    response = {'jsonrpc': '2.0', 'id': msg['id']}
    method = msg.get('method')
    if method == 'initialize':
        response['result'] = {'protocolVersion': '2024-11-05', 'capabilities': {'tools': {}},
                              'serverInfo': {'name': 'agent-visual-bridge', 'version': '0.3.0.dev3'}}
    elif method == 'tools/list':
        response['result'] = {'tools': TOOLS}
    elif method == 'ping':
        response['result'] = {}
    elif method == 'tools/call':
        args = msg.get('params', {}).get('arguments', {})
        name = msg.get('params', {}).get('name')
        try:
            if name == 'visual_bridge_read_report':
                data = parse_html_file(args['html_path'])
            elif name == 'visual_bridge_ask_human':
                data = VisualBridge.ask_human(items=args['items'], title=args['title'],
                    output_html=args.get('output_path', 'reports/human-review.html'),
                    report_type=args.get('type'), timeout=float(args.get('timeout', 600)))
            else:
                raise ValueError('Unknown tool')
            response['result'] = {'content': [{'type': 'text', 'text': json.dumps(data, ensure_ascii=False)}]}
        except (ValueError, OSError, TimeoutError, KeyError) as exc:
            response['result'] = {'isError': True, 'content': [{'type': 'text', 'text': str(exc)}]}
    else:
        response['error'] = {'code': -32601, 'message': 'Method not found'}
    return response


def run_mcp_server(database=None, transport="stdio", host="127.0.0.1", port=8766, token_file=None):
    try:
        from .sdk import create_server
    except ImportError as exc:
        raise SystemExit('MCP needs Python >=3.10 and pip install "agent-visual-bridge[mcp]"') from exc
    if transport == 'streamable-http':
        from .http import run_http
        run_http(database, host, port, token_file)
    elif transport == 'stdio':
        if token_file is not None:
            raise SystemExit('--token-file applies only to Streamable HTTP')
        create_server(database).run(transport='stdio')
    else:
        raise SystemExit('Unsupported MCP transport')


if __name__ == '__main__':
    run_mcp_server()
