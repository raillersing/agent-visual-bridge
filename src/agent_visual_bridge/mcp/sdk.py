"""Official SDK adapter, optional elicitation and MCP Apps with textual fallback."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import uuid4
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, Field

from ..metrics import record
from ..models import ValidationError
from ..parser import parse_html_file
from ..sessions import ReviewService
from ..templates import render_review, render_app_resource
from ..api import LocalServer

UI_URI = 'ui://agent-visual-bridge/review.html'


class HumanAnswer(BaseModel):
    answer: str = Field(description='Your answer to the question')


def create_server(database=None):
    service = ReviewService(database)
    mcp = FastMCP('agent-visual-bridge')

    @mcp.tool()
    def visual_bridge_create_review(proposal: dict) -> dict[str, Any]:
        """Create a durable review; information/clarification/authorization stay distinct."""
        return service.create_review(proposal)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True))
    def visual_bridge_get_review(review_id: str) -> dict[str, Any]:
        """Get proposal, exact human decisions, current revision and receipt identifiers."""
        return service.get_review(review_id)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True))
    def visual_bridge_get_receipt(receipt_id: str) -> dict[str, Any]:
        """Retrieve the human receipt and all constraints before executing actions."""
        return service.get_receipt(receipt_id)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True))
    def visual_bridge_events(review_id: str, after: int = 0) -> dict[str, Any]:
        """Read human questions, requested controls and review events without blocking."""
        return {'events': service.events(review_id, after)}

    @mcp.tool()
    def visual_bridge_revise_review(review_id: str, proposal: dict, revision: int) -> dict[str, Any]:
        """Present a revised proposal; changed authorization boundaries invalidate decisions."""
        return service.revise_review(review_id, proposal, revision)

    @mcp.tool()
    def visual_bridge_reply(review_id: str, item_id: str, message: str,
                           category: str = 'explanation', question_seq: int = None) -> dict[str, Any]:
        """Reply to a human question, stating fact, hypothesis, missing information or integration."""
        return service.publish_item_reply(review_id, item_id, message, category=category, question_seq=question_seq)

    @mcp.tool()
    def visual_bridge_register_agent(review_id: str, agent_id: str, capabilities: list[str]) -> dict[str, Any]:
        """Declare actual cooperative controls. Do not advertise capabilities your host lacks."""
        return service.register_agent(review_id, agent_id, capabilities)

    @mcp.tool()
    def visual_bridge_acknowledge_control(review_id: str, control_id: str, state: str, reason: str = '') -> dict[str, Any]:
        """Confirm a control only after your execution engine has acknowledged/applied it."""
        return service.acknowledge_control(review_id, control_id, state, reason)

    @mcp.tool()
    def visual_bridge_publish_progress(review_id: str, item_id: str, state: str,
                                       message: str = '', evidence: list = None, revision: int = None) -> dict[str, Any]:
        """Publish action state and concrete verification evidence, including unknown outcomes."""
        return service.publish_progress(review_id, item_id, state, message, evidence, revision)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True))
    def visual_bridge_read_report(html_path: str) -> dict[str, Any]:
        """Read saved artifact; imported provenance does not authenticate its human author."""
        return parse_html_file(html_path)

    @mcp.tool()
    async def visual_bridge_ask_human(title: str, items: list[dict], ctx: Context,
                                      type: str = 'auto', output_path: str = 'reports/human-review.html',
                                      timeout: float = 600) -> dict[str, Any]:
        """Open a local review and await explicit human submission; timeout is an error."""
        import math
        import webbrowser
        if not math.isfinite(timeout) or not 0 < timeout <= 86400:
            raise ValidationError('timeout must be between 0 and 86400 seconds')
        review = service.create_review({'title': title, 'items': items, 'report_type': type})
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_review(review), encoding='utf-8')
        if review['state'] == 'published':
            await asyncio.to_thread(webbrowser.open, out.resolve().as_uri())
            return {'state': 'published', 'review': review}
        local = LocalServer(service, review['review_id']).start()
        try:
            await asyncio.to_thread(webbrowser.open, local.url)
            deadline = asyncio.get_running_loop().time() + timeout
            while not local.submitted.is_set():
                if asyncio.get_running_loop().time() >= deadline:
                    service.close_review(review['review_id'], 'expired')
                    raise TimeoutError('No explicit human submission')
                await asyncio.sleep(.1)
            return local.receipt
        finally:
            await asyncio.to_thread(local.close)

    @mcp.tool()
    async def visual_bridge_ask_question(review_id: str, item_id: str, ctx: Context) -> dict[str, Any]:
        """Elicit one clarification when supported; otherwise return the question for manual review."""
        review = service.get_review(review_id)
        item = next((i for i in review['items'] if i['id'] == item_id), None)
        if not item or item['interaction_kind'] != 'clarify':
            raise ValidationError('Elicitation is limited to clarification items')
        capabilities = ctx.request_context.session.client_params.capabilities
        if capabilities.elicitation is None:
            return {'state': 'awaiting_input', 'question': item['question'], 'fallback': 'local-html',
                    'review_id': review_id}
        result = await ctx.elicit(item['question'], HumanAnswer)
        if result.action != 'accept':
            return {'state': result.action, 'review_id': review_id, 'authorized': False}
        return service.submit_decisions(review_id, review['revision'], [{
            'id': item_id, 'fingerprint': item['authorization_fingerprint'], 'decision_kind': 'answer',
            'answer': result.data.answer}], uuid4().hex, provenance='mcp-elicitation-host')

    @mcp.resource(UI_URI, mime_type='text/html;profile=mcp-app',
                  meta={'ui': {'csp': {'connectDomains': [], 'resourceDomains': []}}})
    def review_app() -> str:
        return render_app_resource()

    @mcp.tool(meta={'ui': {'resourceUri': UI_URI}})
    def visual_bridge_open_review(review_id: str) -> CallToolResult:
        """Display an interactive review in MCP Apps hosts, with a structured/textual fallback."""
        review = service.get_review(review_id)
        return CallToolResult(content=[TextContent(type='text', text=json.dumps(review, ensure_ascii=False))],
                              structuredContent={'review': review},
                              _meta={'review_html': render_review(review, {'app': True}, service.settings(review['project_id']))})

    @mcp.tool(meta={'ui': {'visibility': ['app']}})
    def visual_bridge_app_action(review_id: str, path: str, ctx: Context, body: dict = None) -> CallToolResult:
        """UI-only human interaction. Host must enforce MCP Apps tool visibility."""
        if not supports_apps(ctx.request_context.session.client_params.capabilities):
            raise ValidationError('MCP Apps capability required for UI-only operations')
        data = body or {}
        review = service.get_review(review_id)
        if path.startswith('/api/events'):
            from urllib.parse import parse_qs, urlsplit
            value = service.events(review_id, int(parse_qs(urlsplit(path).query).get('after', ['0'])[0]))
        elif path == '/api/review':
            value = review
        elif path == '/api/submit':
            if data.get('review_id') != review_id:
                raise ValidationError('Wrong review')
            value = service.submit_decisions(review_id, data.get('revision'), data.get('decisions'),
                                            data.get('request_key', ''), provenance='mcp-app-host')
        elif path == '/api/question':
            value = service.ask_item_question(review_id, data.get('item_id'), data.get('message'))
        elif path == '/api/control':
            value = service.request_control(review_id, data.get('command'), data.get('payload'))
        elif path == '/api/revision-request':
            value = service.request_revision(review_id, data.get('revision'), data.get('item_id'), data.get('changes'))
        elif path == '/api/settings':
            value = service.settings(review['project_id'], data)
        elif path == '/api/metric':
            record(service, review_id, data.get('event'), data.get('view_id', 'default'))
            value = {'recorded': True}
        else:
            raise ValidationError('Unknown UI operation')
        return CallToolResult(content=[TextContent(type='text', text=json.dumps(value, ensure_ascii=False))],
                              structuredContent={'data': value})

    @mcp._mcp_server.list_tools()
    async def negotiated_tools():
        tools = await mcp.list_tools()
        capabilities = mcp.get_context().request_context.session.client_params.capabilities
        if supports_apps(capabilities):
            return tools
        result = []
        for tool in tools:
            if tool.name == 'visual_bridge_app_action':
                continue
            if tool.meta and 'ui' in tool.meta:
                tool = tool.model_copy(update={'meta': {k: v for k, v in tool.meta.items() if k != 'ui'}})
            result.append(tool)
        return result

    return mcp


def supports_apps(capabilities):
    extensions = getattr(capabilities, 'extensions', {}) or {}
    return 'io.modelcontextprotocol/ui' in extensions
