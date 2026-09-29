"""Core VisualBridge class providing high-level agent-developer orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agent_visual_bridge.detector import ReportType, detect_report_type
from agent_visual_bridge.parser import parse_html_file
from agent_visual_bridge.templates import render_html_report
from agent_visual_bridge.watcher import serve_and_wait, watch_html_file


class VisualBridge:
    """The central orchestrator for Agent Visual Bridge."""

    def __init__(
        self,
        title: str,
        items: List[Dict[str, Any]],
        report_type: Optional[ReportType] = None,
        subtitle: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.title = title
        self.items = items
        self.subtitle = subtitle
        self.metadata = metadata or {}
        self.report_type = report_type or detect_report_type(
            data={"items": items},
            title=title,
            description=subtitle,
        )

    @classmethod
    def from_data(
        cls,
        data: Union[Dict[str, Any], List[Any]],
        title: str = "Agent Visual Report",
        report_type: Optional[str] = None,
        subtitle: str = "",
    ) -> VisualBridge:
        """Create a VisualBridge instance by auto-detecting the data shape."""

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = (
                data.get("items")
                or data.get("points")
                or data.get("tasks")
                or data.get("checks")
                or data.get("lots")
                or []
            )
            title = data.get("title") or title
            subtitle = data.get("subtitle") or data.get("description") or subtitle
        else:
            items = []

        detected_type = detect_report_type(
            data=data,
            title=title,
            description=subtitle,
            explicit_type=report_type,
        )

        return cls(
            title=title,
            items=items,
            report_type=detected_type,
            subtitle=subtitle,
        )

    @classmethod
    def from_json_file(
        cls,
        json_path: Union[str, Path],
        report_type: Optional[str] = None,
    ) -> VisualBridge:
        """Load items from a JSON file and initialize a VisualBridge."""
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_data(raw, report_type=report_type)

    def render_html(self, server_port: Optional[int] = None) -> str:
        """Render the self-contained zero-dependency HTML string."""
        return render_html_report(
            title=self.title,
            report_type=self.report_type,
            items=self.items,
            subtitle=self.subtitle,
            metadata=self.metadata,
            server_port=server_port,
        )

    def save_html(
        self,
        output_path: Union[str, Path],
        server_port: Optional[int] = None,
    ) -> Path:
        """Render and write the report to an HTML file on disk."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = self.render_html(server_port=server_port)
        path.write_text(content, encoding="utf-8")
        return path

    @staticmethod
    def read_feedback(html_path: Union[str, Path]) -> Dict[str, Any]:
        """Read and parse decisions from a saved HTML file."""
        return parse_html_file(html_path)

    @staticmethod
    def watch_feedback(
        html_path: Union[str, Path],
        timeout: float = 600.0,
    ) -> Dict[str, Any]:
        """Wait until the user saves changes to the HTML file."""
        return watch_html_file(html_path, timeout=timeout)

    @classmethod
    def ask_human(
        cls,
        items: List[Dict[str, Any]],
        title: str,
        output_html: Union[str, Path] = "report.html",
        mode: str = "serve",
        timeout: float = 600.0,
        open_browser: bool = True,
    ) -> Dict[str, Any]:
        """All-in-one synchronous call for AI agents:

        1. Generates HTML report.
        2. Opens browser.
        3. Waits for human validation (via ephemeral server or file save).
        4. Returns human decisions and instructions.
        """
        bridge = cls.from_data({"items": items}, title=title)
        out_path = bridge.save_html(output_html)

        if mode == "serve":
            return serve_and_wait(
                out_path,
                open_browser=open_browser,
                timeout=timeout,
            )
        else:
            return watch_html_file(out_path, timeout=timeout)
