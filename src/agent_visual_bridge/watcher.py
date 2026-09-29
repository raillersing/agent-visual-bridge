"""Watcher and Ephemeral Server for real-time bidirectional feedback loop.

Provides:
- watch_html_file: Polls file mtime and wakes up when saved by user.
- serve_and_wait: Runs an ephemeral lightweight HTTP server that waits for 1-click submit.
"""

from __future__ import annotations

import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Union

from agent_visual_bridge.parser import parse_html_file


def watch_html_file(
    file_path: Union[str, Path],
    timeout: float = 600.0,
    check_interval: float = 1.0,
) -> Dict[str, Any]:
    """Watch an HTML file on disk and return parsed decisions as soon as it is modified.

    Raises:
        TimeoutError: If the file is not modified before the timeout.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Cannot watch non-existent file: {path}")

    initial_mtime = path.stat().st_mtime
    start_time = time.time()

    while time.time() - start_time < timeout:
        time.sleep(check_interval)
        try:
            current_mtime = path.stat().st_mtime
            if current_mtime > initial_mtime:
                # Give a tiny buffer for write completion
                time.sleep(0.2)
                return parse_html_file(path)
        except OSError:
            pass

    raise TimeoutError(f"Watcher timed out after {timeout} seconds waiting for {path.name}")


class _FeedbackReceiverHandler(BaseHTTPRequestHandler):
    """Ephemeral HTTP handler that captures user feedback and shuts down."""

    html_content: str = ""
    received_data: Optional[Dict[str, Any]] = None
    server_shutdown_event: Optional[threading.Event] = None

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress standard HTTP server access logs."""
        pass

    def do_GET(self) -> None:
        """Serve the visual bridge HTML report."""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(self.html_content.encode("utf-8"))

    def do_POST(self) -> None:
        """Receive feedback JSON payload from page."""
        if self.path == "/api/submit":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")

            try:
                data = json.loads(body)
                _FeedbackReceiverHandler.received_data = data

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "received"}).encode("utf-8"))

                # Signal server to shut down
                if self.server_shutdown_event:
                    threading.Thread(target=self.server_shutdown_event.set).start()
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def serve_and_wait(
    html_path: Union[str, Path],
    port: int = 0,
    open_browser: bool = True,
    timeout: float = 600.0,
) -> Dict[str, Any]:
    """Serve HTML file on an ephemeral port and block until the user submits feedback.

    Args:
        html_path: Path to the HTML file to serve.
        port: Port to listen on (0 chooses an available ephemeral port).
        open_browser: Automatically open the browser.
        timeout: Maximum seconds to wait before raising TimeoutError.

    Returns:
        Dict containing user decisions and markdown instructions.
    """
    path = Path(html_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    raw_html = path.read_text(encoding="utf-8")

    shutdown_event = threading.Event()
    _FeedbackReceiverHandler.received_data = None
    _FeedbackReceiverHandler.server_shutdown_event = shutdown_event

    server = HTTPServer(("127.0.0.1", port), _FeedbackReceiverHandler)
    actual_port = server.server_port

    # Inject the ephemeral server port into the HTML if needed
    injected_html = raw_html.replace("SERVER_PORT = null", f"SERVER_PORT = {actual_port}")
    _FeedbackReceiverHandler.html_content = injected_html

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    url = f"http://localhost:{actual_port}"
    if open_browser:
        webbrowser.open(url)

    # Wait for either user submission or timeout
    is_submitted = shutdown_event.wait(timeout=timeout)
    server.shutdown()
    server.server_close()

    if not is_submitted or _FeedbackReceiverHandler.received_data is None:
        # Check if the user saved the file directly on disk instead
        return parse_html_file(path)

    return _FeedbackReceiverHandler.received_data
