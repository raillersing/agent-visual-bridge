"""Agent Visual Bridge.

Universal, local-first, zero-dependency visual arbitration bridge
between AI coding agents and human developers.
"""

from agent_visual_bridge.core import VisualBridge
from agent_visual_bridge.detector import ReportType, detect_report_type
from agent_visual_bridge.parser import parse_html_file, parse_html_report
from agent_visual_bridge.watcher import serve_and_wait, watch_html_file
from agent_visual_bridge.sessions import ReviewService
from agent_visual_bridge.adapters import CooperativeAgent, CodexTextExecutor
from agent_visual_bridge.execution import ExecutionRequest, ExecutionResult
from agent_visual_bridge.executors.process import JsonProcessExecutor
from agent_visual_bridge.models import ValidationError, ConflictError

__version__ = "0.3.0.dev3"
__all__ = [
    "ReportType",
    "VisualBridge",
    "detect_report_type",
    "parse_html_file",
    "parse_html_report",
    "serve_and_wait",
    "ReviewService",
    "CooperativeAgent",
    "CodexTextExecutor",
    "JsonProcessExecutor",
    "ExecutionRequest",
    "ExecutionResult",
    "ValidationError",
    "ConflictError",
    "watch_html_file",
]
