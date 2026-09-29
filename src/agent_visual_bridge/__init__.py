"""Agent Visual Bridge.

Universal, local-first, zero-dependency visual arbitration bridge
between AI coding agents and human developers.
"""

from agent_visual_bridge.core import VisualBridge
from agent_visual_bridge.detector import ReportType, detect_report_type
from agent_visual_bridge.parser import parse_html_file, parse_html_report
from agent_visual_bridge.watcher import serve_and_wait, watch_html_file

__version__ = "0.1.0"
__all__ = [
    "VisualBridge",
    "ReportType",
    "detect_report_type",
    "parse_html_file",
    "parse_html_report",
    "watch_html_file",
    "serve_and_wait",
]
