"""Project-scoped MCP exports. No provider credentials or automatic tool grants."""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

CLIENTS = {
    'claude-code': ('.mcp.json', 'mcpServers'),
    'cursor': ('.cursor/mcp.json', 'mcpServers'),
    'vscode': ('.vscode/mcp.json', 'servers'),
    'gemini-cli': ('.gemini/settings.json', 'mcpServers'),
    'opencode': ('opencode.json', 'mcp'),
    'antigravity': ('.agents/mcp_config.json', 'mcpServers'),
    'codex': ('.codex/config.toml', 'mcp_servers'),
    'cline': (None, 'mcpServers'),
    'hermes': (None, 'mcp_servers'),
}


class _Node:
    def __init__(self, start, end, value, members=None):
        self.start, self.end, self.value, self.members = start, end, value, members


class _JSONC:
    """Parse JSON with comments/trailing commas, preserving source offsets."""
    def __init__(self, source):
        self.source, self.position = source, 0

    def skip(self):
        while self.position < len(self.source):
            if self.source[self.position].isspace():
                self.position += 1
            elif self.source.startswith('//', self.position):
                end = self.source.find('\n', self.position)
                self.position = len(self.source) if end < 0 else end
            elif self.source.startswith('/*', self.position):
                end = self.source.find('*/', self.position + 2)
                if end < 0:
                    raise ValueError('Unterminated configuration comment')
                self.position = end + 2
            else:
                break

    def parse(self):
        self.skip()
        start = self.position
        if self.source[start:start + 1] in ('{', '['):
            object_ = self.source[start] == '{'
            closing = '}' if object_ else ']'
            value, members = ({}, {}) if object_ else ([], None)
            self.position += 1
            self.skip()
            while self.source[self.position:self.position + 1] != closing:
                if object_:
                    key = self.parse().value
                    self.skip()
                    if not isinstance(key, str) or key in value or self.source[self.position:self.position + 1] != ':':
                        raise ValueError('Invalid or duplicate configuration key')
                    self.position += 1
                    node = self.parse()
                    value[key], members[key] = node.value, node
                else:
                    value.append(self.parse().value)
                self.skip()
                if self.source[self.position:self.position + 1] == closing:
                    break
                if self.source[self.position:self.position + 1] != ',':
                    raise ValueError('Invalid configuration separator')
                self.position += 1
                self.skip()
            self.position += 1
            return _Node(start, self.position, value, members)
        value, length = json.JSONDecoder().raw_decode(self.source[start:])
        self.position += length
        return _Node(start, self.position, value)

    def document(self):
        node = self.parse()
        self.skip()
        if self.position != len(self.source) or not isinstance(node.value, dict):
            raise ValueError('Expected one configuration object')
        return node


def _put(source, node, key, value):
    encoded = json.dumps(value, indent=2, ensure_ascii=False)
    if key in node.members:
        child = node.members[key]
        return source[:child.start] + encoded + source[child.end:]
    # Insert before existing members: no need to disturb trailing comments/commas.
    entry = '\n' + json.dumps(key) + ': ' + encoded + (',' if node.members else '') + '\n'
    return source[:node.start + 1] + entry + source[node.start + 1:]


def _owned(entry):
    if not isinstance(entry, dict):
        return False
    command = entry.get('command', '')
    args = entry.get('args', [])
    tokens = command if isinstance(command, list) else [command, *args]
    return any(isinstance(t, str) and (t in {'agent_visual_bridge', 'agent_visual_bridge.mcp.server'}
               or Path(t).name in {'agent-bridge', 'agent-bridge.exe', 'avb', 'avb.exe'}) for t in tokens)


def configuration(project, client, *, wsl_distro=None):
    root = Path(project).resolve()
    if not root.is_dir():
        raise ValueError('Project directory does not exist')
    if client not in CLIENTS:
        raise ValueError('Unknown client')
    project_id = re.sub(r'[^a-zA-Z0-9_.:-]', '-', root.name)[:120] or 'project'
    env = {'AVB_DB': str(root / '.agent-visual-bridge/reviews.sqlite3'), 'AVB_PROJECT_ID': project_id}
    args = ['-m', 'agent_visual_bridge', 'mcp']
    command = sys.executable
    if wsl_distro is not None:
        if (sys.platform != 'linux' or not isinstance(wsl_distro, str)
                or not wsl_distro.strip() or len(wsl_distro) > 200
                or any(c in wsl_distro for c in '\0\r\n')):
            raise ValueError('WSL export requires Linux and an explicit valid distribution name')
        command = 'wsl.exe'
        args = ['--distribution', wsl_distro, '--cd', str(root), '--exec',
                '/usr/bin/env', *[f'{k}={v}' for k, v in env.items()], sys.executable, *args]
    entry = {'command': command, 'args': args, 'env': env}
    if client == 'opencode':
        entry = {'type': 'local', 'command': [command, *args], 'environment': env}
    elif client == 'codex':
        entry = {**entry, 'startup_timeout_sec': 30, 'tool_timeout_sec': 60}
        if wsl_distro is None:
            entry['cwd'] = str(root)
    return root, entry


def setup(project, client, *, dry_run=False, output=None, server_name='visual-bridge', wsl_distro=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', server_name):
        raise ValueError('Invalid MCP server name')
    root, entry = configuration(project, client, wsl_distro=wsl_distro)
    filename, table = CLIENTS[client]
    if client == 'hermes':
        # JSON is valid YAML; export a fragment, never mutate the global file.
        content = json.dumps({table: {server_name: entry}}, indent=2) + '\n'
    elif client == 'codex':
        content = f'[mcp_servers.{server_name}]\n' + '\n'.join(
            f'{key} = {json.dumps(value)}' for key, value in entry.items() if key != 'env')
        content += f'\n[mcp_servers.{server_name}.env]\n' + '\n'.join(
            f'{key} = {json.dumps(value)}' for key, value in entry['env'].items()) + '\n'
    else:
        content = json.dumps({table: {server_name: entry}}, indent=2) + '\n'
    destination = Path(output).resolve() if output else root / filename if filename else None
    result = {'client': client, 'project': str(root), 'path': str(destination) if destination else None,
              'dry_run': dry_run, 'configuration': content, 'qualification': 'configuration-only'}
    if destination is None:
        result['state'] = 'manual-import-required'
        return result
    previous = destination.read_text(encoding='utf-8') if destination.exists() else None
    if previous is not None and previous != content:
        if client == 'codex':
            # Lossless TOML edit requires the optional installer dependency.
            try:
                import tomlkit
            except ImportError as exc:
                raise ValueError('Editing existing TOML requires pip install "agent-visual-bridge[setup]"; use --output to export a new fragment') from exc
            document = tomlkit.parse(previous)
            servers = document.setdefault(table, {})
            existing = servers.get(server_name)
            if existing is not None and existing != entry and not _owned(existing):
                raise ValueError('visual-bridge entry belongs to another command; inspect manually')
            if isinstance(existing, dict) and all(existing.get(k) == v for k, v in entry.items()):
                content = previous
            else:
                servers[server_name] = {**(existing or {}), **entry}
                content = tomlkit.dumps(document)
        elif client == 'hermes':
            raise ValueError('Export Hermes to a new file, then import the fragment explicitly')
        else:
            document = _JSONC(previous).document()
            servers = document.members.get(table)
            if servers is not None:
                if not isinstance(servers.value, dict):
                    raise ValueError('MCP configuration must be an object')
                existing = servers.value.get(server_name)
                if existing is not None and existing != entry and not _owned(existing):
                    raise ValueError('visual-bridge entry belongs to another command; inspect manually')
                content = previous if isinstance(existing, dict) and all(existing.get(k) == v for k, v in entry.items()) else _put(previous, servers, server_name, {**(existing or {}), **entry})
            else:
                content = _put(previous, document, table, {server_name: entry})
            _JSONC(content).document()
    # Report the bridge fragment only: unrelated entries may contain secrets.
    result['state'] = 'unchanged' if previous == content else 'preview' if dry_run else 'written'
    if dry_run or previous == content:
        return result
    destination.parent.mkdir(parents=True, exist_ok=True)
    if previous is not None:
        backup = destination.with_name(destination.name + '.avb-backup-' + __import__('uuid').uuid4().hex[:8])
        shutil.copy2(destination, backup)
        result['backup'] = str(backup)
    descriptor, temporary = tempfile.mkstemp(dir=destination.parent, prefix='.avb-')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(content)
        # Detect concurrent edits before replacement.
        if (destination.read_text(encoding='utf-8') if destination.exists() else None) != previous:
            raise ValueError('Configuration changed concurrently; retry after inspection')
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return result


def doctor(project, client, *, handshake=False, server_name='visual-bridge', wsl_distro=None):
    root, entry = configuration(project, client, wsl_distro=wsl_distro)
    filename, table = CLIENTS[client]
    from importlib.util import find_spec
    result = {'project': str(root), 'client': client, 'python': sys.executable,
              'mcp_installed': find_spec('mcp') is not None,
              'database_exists': (root / '.agent-visual-bridge/reviews.sqlite3').exists(),
              'configuration_exists': bool(filename and (root / filename).exists()),
              'qualification': 'not-runtime-qualified', 'transport': 'stdio',
              'inference': 'not-tested', 'host_capabilities': 'unknown',
              'execution_host': 'wsl' if wsl_distro else 'native', 'wsl_distribution': wsl_distro}
    binaries = {'claude-code': 'claude', 'gemini-cli': 'gemini', 'vscode': 'code'}
    result['client_executable'] = shutil.which(binaries.get(client, client))
    result['url_scope'] = 'server-loopback; configure port forwarding explicitly for remote use'
    if result['configuration_exists']:
        source = (root / filename).read_text(encoding='utf-8')
        if client == 'codex':
            try:
                import tomlkit
            except ImportError as exc:
                raise ValueError('TOML diagnostics require agent-visual-bridge[setup]') from exc
            configured = tomlkit.parse(source).get(table, {}).get(server_name)
        else:
            configured = _JSONC(source).document().value.get(table, {}).get(server_name)
        result['configuration_matches'] = isinstance(configured, dict) and all(configured.get(k) == v for k, v in entry.items())
    if handshake:
        if result.get('configuration_matches') is False:
            raise ValueError('Configuration differs from the selected launcher; inspect it before handshake')
        if not result['mcp_installed']:
            raise ValueError('Handshake requires agent-visual-bridge[mcp]')
        import asyncio
        result['handshake'] = asyncio.run(_handshake(root, entry))
    return result


async def _handshake(root, entry):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import asyncio
    # Probe this package without creating a business review or invoking a model.
    async def probe():
        environment = {**os.environ, **entry.get('env', entry.get('environment', {}))}
        command = entry['command']
        args = entry.get('args', [])
        if isinstance(command, list):
            command, args = command[0], command[1:]
        async with stdio_client(StdioServerParameters(command=command,
                args=args, env=environment, cwd=str(root))) as streams:
            async with ClientSession(*streams) as session:
                initialized = await session.initialize()
                tools = await session.list_tools()
                return {'state': 'sdk-protocol-verified', 'protocol': initialized.protocolVersion,
                        'server': initialized.serverInfo.model_dump(), 'tools': [t.name for t in tools.tools],
                        'commercial_client': 'not-tested'}
    return await asyncio.wait_for(probe(), timeout=30)
