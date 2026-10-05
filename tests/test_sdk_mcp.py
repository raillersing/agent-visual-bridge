"""Real stdio process and official MCP client, including elicitation callbacks."""
import asyncio
import json
import os
import sys

import pytest
pytest.importorskip('mcp')
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp import types
from agent_visual_bridge.browser import stop_browser_sessions


@pytest.fixture(autouse=True)
def close_detached_sessions(tmp_path):
    yield
    for database in tmp_path.glob('*.db'):
        stop_browser_sessions(database)


async def journey(path, action=None):
    async def elicitation(_context, _params):
        return types.ElicitResult(action=action, content={'answer':'Preserve compatibility'} if action=='accept' else None)
    params=StdioServerParameters(command=sys.executable,args=['-m','agent_visual_bridge.mcp.server'],env={**os.environ,'AVB_DB':str(path)})
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write,elicitation_callback=elicitation if action else None) as session:
            await session.initialize()
            tools=await session.list_tools()
            assert 'visual_bridge_get_receipt' in {t.name for t in tools.tools}
            result=await session.call_tool('visual_bridge_create_review',{'proposal':{'title':'Question','items':[{'id':'a','question':'Which contract?', 'interaction_kind':'clarify'}]}})
            assert not result.isError
            review=result.structuredContent
            if 'result' in review:
                review=review['result']
            question=await session.call_tool('visual_bridge_ask_question',{'review_id':review['review_id'],'item_id':'a'})
            assert not question.isError
            data=question.structuredContent
            if 'result' in data:
                data=data['result']
            if not action:
                assert data['fallback']=='local-html'
            elif action=='accept':
                receipt=await session.call_tool('visual_bridge_get_receipt',{'receipt_id':data['receipt_id']})
                assert 'Preserve compatibility' in json.dumps(receipt.structuredContent)
            else:
                assert data['state']==action and data['authorized'] is False
            view=await session.call_tool('visual_bridge_open_review',{'review_id':review['review_id']})
            assert view.structuredContent['review']['review_id']==review['review_id']
            resource=await session.read_resource('ui://agent-visual-bridge/review.html')
            assert 'Chargement' in resource.contents[0].text
            error=await session.call_tool('visual_bridge_get_review',{'review_id':'missing'})
            assert error.isError
            assert (await session.send_ping()) is not None


@pytest.mark.parametrize('action',[None,'accept','decline','cancel'])
def test_official_client_stdio_and_elicitation(tmp_path,action):
    asyncio.run(journey(tmp_path/'mcp.db',action))


def test_apps_capability_controls_ui_tool_visibility(tmp_path):
    class AppsSession(ClientSession):
        async def send_request(self,request,*args,**kwargs):
            value = getattr(request, 'root', request)
            if isinstance(value,types.InitializeRequest):
                value.params.capabilities.extensions={'io.modelcontextprotocol/ui':{}}
            return await super().send_request(request,*args,**kwargs)
    async def run(session_class):
        params=StdioServerParameters(command=sys.executable,args=['-m','agent_visual_bridge.mcp.server'],env={**os.environ,'AVB_DB':str(tmp_path/'caps.db')})
        async with stdio_client(params) as (read,write):
            async with session_class(read,write) as session:
                await session.initialize()
                tools=await session.list_tools()
                names={t.name for t in tools.tools}
                assert ('visual_bridge_app_action' in names)==(session_class is AppsSession)
                if session_class is AppsSession:
                    created=await session.call_tool('visual_bridge_create_review',{'proposal':{'items':[{'id':'a'}]}})
                    review=created.structuredContent
                    result=await session.call_tool('visual_bridge_app_action',{'review_id':review['review_id'],'path':'/api/submit',
                        'body':{'review_id':review['review_id'],'revision':1,'request_key':'one','decisions':[
                            {'id':'a','decision_kind':'approve','fingerprint':review['items'][0]['authorization_fingerprint']}]}})
                    assert not result.isError
                    assert result.structuredContent['data']['state']=='submitted'
                    fallback = await session.call_tool('visual_bridge_open_review', {
                        'review_id': review['review_id'], 'prefer_browser': True})
                    assert fallback.structuredContent['browser']['url_scope'] == 'server-loopback'
    asyncio.run(run(ClientSession))
    asyncio.run(run(AppsSession))


@pytest.mark.parametrize('capability,expected', [(None, False), ({}, True), ({'form': {}}, True),
                                                ({'url': {}}, False), ({'form': {}, 'url': {}}, True)])
def test_form_mode_negotiation(capability, expected):
    from agent_visual_bridge.mcp.sdk import supports_form_elicitation
    assert supports_form_elicitation(types.ClientCapabilities(elicitation=capability)) is expected


def test_mcp_disconnect_and_wait_timeout_preserve_review(tmp_path):
    from agent_visual_bridge.sessions import ReviewService
    from urllib.request import urlopen
    path = tmp_path / 'detached.db'
    async def run():
        params = StdioServerParameters(command=sys.executable, args=['-m', 'agent_visual_bridge', 'mcp'],
            env={**os.environ, 'AVB_DB': str(path), 'PATH': ''})
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                result = await session.call_tool('visual_bridge_ask_human', {'title': 'Detached',
                    'items': [{'id': 'a'}], 'output_path': str(tmp_path/'report.html')})
                assert not result.isError
                opened = result.structuredContent
                error = await session.call_tool('visual_bridge_ask_human', {'title': 'Timeout',
                    'items': [{'id': 'b'}], 'output_path': str(tmp_path/'wait.html'), 'wait': True, 'timeout': .1})
                assert error.isError
                return opened
    opened = asyncio.run(run())
    with urlopen(opened['url'], timeout=3) as response:
        assert response.status == 200
    reviews = ReviewService(path).list_reviews()
    assert len(reviews) == 2 and all(r['state'] == 'awaiting_input' for r in reviews)


@pytest.mark.parametrize('mode', ['url-only', 'refused'])
def test_unsupported_or_broken_elicitation_falls_back_without_decisions(tmp_path, mode):
    called = []
    async def reject(_context, _params):
        called.append(True)
        raise RuntimeError('Client cannot display this request')
    class UrlSession(ClientSession):
        async def send_request(self, request, *args, **kwargs):
            value = getattr(request, 'root', request)
            if isinstance(value, types.InitializeRequest):
                value.params.capabilities.elicitation = types.ElicitationCapability(url=types.UrlElicitationCapability())
            return await super().send_request(request, *args, **kwargs)
    async def run():
        path = tmp_path / 'fallback.db'
        params = StdioServerParameters(command=sys.executable, args=['-m', 'agent_visual_bridge', 'mcp'],
                                       env={**os.environ, 'AVB_DB': str(path)})
        async with stdio_client(params) as streams:
            cls = UrlSession if mode == 'url-only' else ClientSession
            async with cls(*streams, elicitation_callback=reject) as session:
                await session.initialize()
                created = await session.call_tool('visual_bridge_create_review', {'proposal': {
                    'items': [{'id': 'q', 'interaction_kind': 'clarify', 'question': 'Which scope?'}]}})
                review = created.structuredContent
                result = await session.call_tool('visual_bridge_ask_question', {'review_id': review['review_id'], 'item_id': 'q'})
                assert not result.isError
                assert result.structuredContent['fallback'] == 'local-html'
                assert result.structuredContent['authorized'] is False
                current = await session.call_tool('visual_bridge_get_review', {'review_id': review['review_id']})
                assert current.structuredContent['receipts'] == []
    asyncio.run(run())
    assert bool(called) == (mode == 'refused')
