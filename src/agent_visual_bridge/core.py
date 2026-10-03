"""Public SDK: autonomous HTML views and durable review services."""
from __future__ import annotations

import json
import webbrowser
from pathlib import Path

from .detector import ReportType
from .models import ValidationError, normalize
from .parser import parse_html_file
from .sessions import ReviewService
from .templates import render_review
from .watcher import serve_and_wait, watch_html_file


class VisualBridge:
    def __init__(self, title, items, report_type=None, subtitle='', metadata=None):
        self.proposal = normalize({'title': title, 'items': items, 'subtitle': subtitle,
                                   'metadata': metadata or {}},
                                  report_type=report_type.value if isinstance(report_type, ReportType) else report_type)
        self._sync()

    def _sync(self):
        self.title = self.proposal['title']
        self.items = self.proposal['items']
        self.report_type = ReportType(self.proposal['report_type'])
        self.subtitle = self.proposal['subtitle']
        self.metadata = self.proposal['metadata']

    @classmethod
    def from_data(cls, data, title='Agent Visual Report', report_type=None, subtitle=''):
        value = cls.__new__(cls)
        if isinstance(data, dict) and subtitle and not data.get('subtitle'):
            data = {**data, 'subtitle': subtitle}
        value.proposal = normalize(data, title=title, report_type=report_type)
        value._sync()
        return value

    @classmethod
    def from_json_file(cls, json_path, report_type=None):
        return cls.from_data(json.loads(Path(json_path).read_text(encoding='utf-8')), report_type=report_type)

    def render_html(self, server_port=None):
        return render_review(self.proposal)

    def save_html(self, output_path, server_port=None):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render_html(), encoding='utf-8')
        return path

    @staticmethod
    def read_feedback(html_path):
        return parse_html_file(html_path)

    @staticmethod
    def watch_feedback(html_path, timeout=600.0):
        return watch_html_file(html_path, timeout=timeout)

    @classmethod
    def ask_human(cls, items, title, output_html='report.html', mode='serve', timeout=600.0,
                  open_browser=True, report_type=None, database=None):
        if mode not in {'serve', 'watch'}:
            raise ValidationError('mode must be serve or watch')
        bridge = cls.from_data({'items': items}, title=title, report_type=report_type)
        path = bridge.save_html(output_html)
        if mode == 'serve':
            return serve_and_wait(path, open_browser=open_browser, timeout=timeout,
                                  service=ReviewService(database))
        if open_browser:
            webbrowser.open(path.resolve().as_uri())
        return watch_html_file(path, timeout=timeout)
