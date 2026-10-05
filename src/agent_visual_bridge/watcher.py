"""Compatibility helpers; only an explicit submission ends the wait."""
from __future__ import annotations

import json
import math
import time
import webbrowser
from pathlib import Path

from .api import LocalServer
from .models import ValidationError
from .parser import extract_proposal, parse_html_file
from .sessions import ReviewService


def watch_html_file(file_path, timeout=600.0, check_interval=1.0):
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(path)
    if not math.isfinite(timeout) or timeout <= 0 or check_interval <= 0:
        raise ValidationError('Positive finite timeout and interval required')
    initial = path.stat().st_mtime_ns
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(min(check_interval, max(0, deadline - time.monotonic())))
        try:
            if path.stat().st_mtime_ns != initial:
                result = parse_html_file(path)
                if result.get('submitted_at') and result.get('decisions'):
                    return result
        except (OSError, ValueError):
            pass
    raise TimeoutError(f'No explicit submission within {timeout}s')


def serve_and_wait(html_path, port=0, open_browser=True, timeout=600.0, service=None):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValidationError('Positive finite timeout required')
    path = Path(html_path)
    proposal = extract_proposal(path.read_text(encoding='utf-8'))
    if proposal is None:
        legacy = parse_html_file(path)
        proposal = {'title': path.stem, 'items': legacy['decisions']}
    service = service or ReviewService()
    review_id = proposal.get('review_id')
    try:
        review = service.get_review(review_id) if review_id else service.create_review(proposal)
    except ValidationError:
        review = service.create_review(proposal)
    if review['state'] == 'submitted':
        return service.get_receipt(review['receipts'][-1])
    if review['state'] == 'published':
        if open_browser:
            webbrowser.open(path.resolve().as_uri())
        return {'state': 'published', 'review': review}
    with LocalServer(service, review['review_id'], port) as server:
        if open_browser:
            webbrowser.open(server.url)
        if not server.submitted.wait(timeout):
            current = service.get_review(review['review_id'])
            if current['state'] != 'submitted':
                service.close_review(review['review_id'], 'expired')
            raise TimeoutError('No human submission before expiration')
        return server.receipt


def read_decision_file(path):
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.suffix == '.json' else parse_html_file(path)
