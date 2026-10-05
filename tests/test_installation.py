"""Configuration preservation, portability and truthful diagnostic boundaries."""
import json
import sys

import pytest

from agent_visual_bridge.cli import main
from agent_visual_bridge.installation import CLIENTS, _JSONC, configuration, doctor, setup


@pytest.mark.parametrize('client', CLIENTS)
def test_export_without_codex_and_no_provider_credentials(tmp_path, monkeypatch, client):
    monkeypatch.setenv('PATH', '')
    result = setup(tmp_path, client, dry_run=True)
    assert not list(tmp_path.iterdir())
    assert result['qualification'] == 'configuration-only'
    assert 'autoApprove' not in result['configuration']
    assert 'api_key' not in result['configuration']
    assert sys.executable in result['configuration'].replace('\\\\', '\\')
    if client not in {'cline', 'hermes'}:
        installed = setup(tmp_path, client)
        assert setup(tmp_path, client)['state'] == 'unchanged'
        assert installed['path']


def test_jsonc_preserves_unrelated_comments_and_detects_conflict(tmp_path):
    path = tmp_path / '.vscode/mcp.json'
    path.parent.mkdir()
    source = '''{
  // preserve the workspace comment
  "servers": {
    "other": {"command": "other-server"}, // preserve this too
  },
  "inputs": [],
}
'''
    path.write_text(source)
    result = setup(tmp_path, 'vscode')
    installed = path.read_text()
    assert '// preserve the workspace comment' in installed
    assert '"other": {"command": "other-server"}, // preserve this too' in installed
    assert _JSONC(installed).document().value['inputs'] == []
    assert open(result['backup']).read() == source
    assert setup(tmp_path, 'vscode')['state'] == 'unchanged'
    path.write_text('{"servers":{"visual-bridge":{"command":"unrelated"}}}')
    with pytest.raises(ValueError, match='another command'):
        setup(tmp_path, 'vscode')
    assert 'unrelated' in path.read_text()


def test_project_move_updates_only_owned_entry(tmp_path):
    original = tmp_path / 'old project'
    original.mkdir()
    setup(original, 'gemini-cli')
    moved = tmp_path / 'new project'
    original.rename(moved)
    setup(moved, 'gemini-cli')
    entry = json.loads((moved / '.gemini/settings.json').read_text())['mcpServers']['visual-bridge']
    assert entry['env']['AVB_DB'].startswith(str(moved))
    assert 'AVB_PROJECT_ID' in entry['env']


def test_opencode_format_and_doctor_do_not_claim_inference(tmp_path, capsys):
    assert main(['setup', '--project', str(tmp_path), '--client', 'opencode']) == 0
    capsys.readouterr()
    _, entry = configuration(tmp_path, 'opencode')
    assert isinstance(entry['command'], list) and entry['type'] == 'local'
    assert 'environment' in entry and 'mcp' in json.loads((tmp_path / 'opencode.json').read_text())
    report = doctor(tmp_path, 'opencode')
    assert report['configuration_matches']
    assert report['host_capabilities'] == 'unknown' and report['inference'] == 'not-tested'


def test_toml_preserves_foreign_settings(tmp_path):
    pytest.importorskip('tomlkit')
    path = tmp_path / '.codex/config.toml'
    path.parent.mkdir()
    original = '# keep this\nmodel = "user-model"\n[mcp_servers.other]\ncommand = "other"\n'
    path.write_text(original)
    setup(tmp_path, 'codex')
    assert path.read_text().startswith(original)
    assert doctor(tmp_path, 'codex')['configuration_matches']


def test_invalid_jsonc_never_overwritten(tmp_path):
    path = tmp_path / '.mcp.json'
    path.write_text('{"mcpServers":{')
    with pytest.raises(ValueError):
        setup(tmp_path, 'claude-code')
    assert path.read_text() == '{"mcpServers":{'


def test_doctor_handshake_is_server_proof_only(tmp_path):
    pytest.importorskip('mcp')
    setup(tmp_path, 'gemini-cli')
    report = doctor(tmp_path, 'gemini-cli', handshake=True)
    assert report['handshake']['state'] == 'sdk-protocol-verified'
    from agent_visual_bridge import __version__
    assert report['handshake']['server']['version'] == __version__
    assert report['handshake']['commercial_client'] == 'not-tested'
    assert 'visual_bridge_open_review' in report['handshake']['tools']
    assert report['inference'] == 'not-tested'


def test_named_server_migration_preserves_existing_permissions(tmp_path):
    pytest.importorskip('tomlkit')
    path = tmp_path / '.codex/config.toml'
    path.parent.mkdir()
    path.write_text('[mcp_servers.agent_visual_bridge]\ncommand = "/old/scripts/agent-bridge"\nargs = ["mcp"]\n'
                    '[mcp_servers.agent_visual_bridge.tools.visual_bridge_get_review]\napproval_mode = "approve"\n', encoding='utf-8')
    setup(tmp_path, 'codex', server_name='agent_visual_bridge')
    assert 'approval_mode = "approve"' in path.read_text()
    assert 'mcp_servers.visual-bridge' not in path.read_text()
    assert setup(tmp_path, 'codex', server_name='agent_visual_bridge')['state'] == 'unchanged'
    assert doctor(tmp_path, 'codex', server_name='agent_visual_bridge')['configuration_matches']


def test_windows_client_to_wsl_export(tmp_path):
    if sys.platform != 'linux':
        pytest.skip('WSL profiles are generated inside Linux')
    project = tmp_path / 'project with spaces'
    project.mkdir()
    for client in ['opencode', 'antigravity', 'codex']:
        result = setup(project, client, wsl_distro='Ubuntu')
        _, entry = configuration(project, client, wsl_distro='Ubuntu')
        command = entry['command']
        argv = command if isinstance(command, list) else [command, *entry['args']]
        assert argv[:5] == ['wsl.exe', '--distribution', 'Ubuntu', '--cd', str(project)]
        assert 'AVB_DB=' + str(project / '.agent-visual-bridge/reviews.sqlite3') in argv
        assert sys.executable in argv and argv[-3:] == ['-m', 'agent_visual_bridge', 'mcp']
        assert 'cwd' not in entry
        from importlib.util import find_spec
        if client != 'codex' or find_spec('tomlkit') is not None:
            assert doctor(project, client, wsl_distro='Ubuntu')['configuration_matches']
        assert setup(project, client, wsl_distro='Ubuntu')['state'] == 'unchanged'
        assert result['qualification'] == 'configuration-only'
    with pytest.raises(ValueError):
        setup(project, 'opencode', wsl_distro='Ubuntu\nother')


def test_diagnostic_probes_selected_launcher_without_fallback(tmp_path):
    pytest.importorskip('mcp')
    import asyncio
    from agent_visual_bridge.installation import _handshake
    # A nonexistent selected launcher must fail even with a working local Python.
    with pytest.raises(OSError):
        asyncio.run(_handshake(tmp_path, {'command': str(tmp_path / 'missing-launcher'), 'args': []}))


def test_handshake_refuses_mismatched_project_config(tmp_path):
    setup(tmp_path, 'opencode')
    path = tmp_path / 'opencode.json'
    config = json.loads(path.read_text())
    config['mcp']['visual-bridge']['command'][0] = 'different-python'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='differs from the selected launcher'):
        doctor(tmp_path, 'opencode', handshake=True)
