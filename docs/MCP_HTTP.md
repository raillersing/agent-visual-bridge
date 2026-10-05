# Local MCP Streamable HTTP

The optional MCP SDK now exposes a second transport. Stdio remains the default. This endpoint is distinct from the detached browser review service.

Create a private local token file, outside version control, using the project virtual environment:

```bash
python -c "import os,secrets; from pathlib import Path; p=Path('.agent-visual-bridge/mcp-http.token'); p.parent.mkdir(parents=True,exist_ok=True); fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); os.write(fd,secrets.token_urlsafe(48).encode()); os.close(fd)"
agent-bridge --db .agent-visual-bridge/reviews.sqlite3 mcp \
  --transport streamable-http --host 127.0.0.1 --port 8766 \
  --token-file .agent-visual-bridge/mcp-http.token
```

Connect the MCP client to `http://127.0.0.1:8766/mcp` with `Authorization: Bearer <file contents>`. Keep the token in the client's secret storage or a private environment setting; do not put it in URLs, CLI arguments, committed configuration or screenshots. Configuration export and `doctor --handshake` currently qualify stdio only. HTTP client configuration must be explicit; no exporter silently moves an existing installation to HTTP.

The implementation rejects public binds, incorrect Host headers, duplicate headers, foreign Origin headers and requests without the token. Tokens are 32–512 ASCII characters. POSIX token files must be regular, non-symlink files with private permissions. Windows deployments must protect the file with appropriate user ACLs; POSIX mode checks do not establish Windows ACL privacy.

A server has at most 64 protocol sessions; idle sessions expire after 300 seconds. Requests are limited to 1 MiB. SDK protocol sessions and durable SQLite reviews are separate. Reinitialize after an expired/unknown session (HTTP 404). A disconnect or protocol-session DELETE does not delete decisions or prove cancellation of execution. Restarting the server loses protocol sessions and preserves durable review data. Existing execution claims still require reconciliation.

The bearer token identifies access to one trusted local server. This is a local shared capability, **not OAuth**, per-user authorization, a tenant boundary or public remote hosting. Rotate it by stopping this server, replacing the private file and restarting. No tunnel, public listener or TLS termination is configured automatically.

Security and lifecycle follow the official [MCP transport specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports). Real SDK-over-socket tests verify unauthorized requests, Host/Origin rejection, unknown-session 404, initialization, tool reads, session deletion/reconnection and receipt persistence. Commercial HTTP client interfaces remain separately unqualified.
