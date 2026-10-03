"""A completed model turn must not mask a required tool failure."""
import json
from types import SimpleNamespace

import pytest

from agent_visual_bridge import CodexTextExecutor


@pytest.mark.parametrize('status,error,is_error', [('failed', None, False), ('completed', 'refused', False), ('completed', None, True)])
def test_required_tool_failure(monkeypatch, tmp_path, status, error, is_error):
    events = [{'type': 'item.completed', 'item': {'type': 'mcp_tool_call', 'tool': 'get_receipt',
               'status': status, 'error': error, 'result': {'isError': is_error}}},
              {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'Done'}},
              {'type': 'turn.completed', 'usage': {'output_tokens': 1}}]
    monkeypatch.setattr('subprocess.run', lambda *a, **k: SimpleNamespace(returncode=0, stdout='\n'.join(map(json.dumps, events))))
    with pytest.raises(RuntimeError, match='Required tool did not succeed'):
        CodexTextExecutor(tmp_path)({'action': {'required_tools': ['get_receipt']}}, [])


def test_no_required_tool_called_is_failure(monkeypatch, tmp_path):
    events = [{'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'Tool unavailable'}},
              {'type': 'turn.completed'}]
    monkeypatch.setattr('subprocess.run', lambda *a, **k: SimpleNamespace(returncode=0, stdout='\n'.join(map(json.dumps, events))))
    with pytest.raises(RuntimeError, match='Required tool did not succeed'):
        CodexTextExecutor(tmp_path)({'action': {'required_tools': ['get_receipt']}}, [])
