"""CLI with human-readable exports and machine-readable lifecycle commands."""
from __future__ import annotations

import argparse
import json
import sys
import time
import webbrowser
from pathlib import Path

from .api import LocalServer
from .core import VisualBridge
from .metrics import summarize
from .models import ValidationError
from .sessions import ReviewService
from .templates import render_review
from .watcher import read_decision_file, serve_and_wait, watch_html_file


def _handle_feedback_output(result, output_path=None):
    content = json.dumps(result, indent=2, ensure_ascii=False)
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    else:
        print(content)


def starter(kind):
    item = {'id': 'item-1', 'title': 'Proposition à examiner', 'question': 'Quel choix souhaitez-vous faire ?',
            'description': 'Contexte et problème', 'recommendation': 'Solution proposée',
            'consequences': 'Effet concret de votre décision', 'unknowns': ['Informations à vérifier'],
            'evidence': [{'kind': 'agent_observation', 'source': 'À remplacer par une preuve réelle'}]}
    if kind == 'plan':
        item.update(lot='Lot 1', scope='src/', action={'operation': 'edit', 'scope': 'src/', 'reversible': True})
    elif kind == 'review':
        item.update(file='src/example.py', diff='-previous\n+proposed', checks=['Test de contrat à exécuter'])
    elif kind == 'decision':
        item.update(interaction_kind='clarify', options=['Option A', 'Option B'])
    else:
        item.update(severity='high', verdict='À vérifier')
    return {'title': f'New {kind.title()} Template', 'report_type': kind, 'items': [item]}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='agent-bridge')
    parser.add_argument('--db', help='SQLite review database (or AVB_DB)')
    commands = parser.add_subparsers(dest='command')
    from .installation import CLIENTS
    setup = commands.add_parser('setup', help='Export or install project-scoped MCP configuration')
    setup.add_argument('--project', required=True)
    setup.add_argument('--client', choices=CLIENTS, required=True)
    setup.add_argument('--dry-run', action='store_true')
    setup.add_argument('--server-name', default='visual-bridge')
    setup.add_argument('--output', help='Export to a specific file instead of the client configuration')
    doctor = commands.add_parser('doctor', help='Inspect configuration; never infer provider availability')
    doctor.add_argument('--project', required=True)
    doctor.add_argument('--client', choices=CLIENTS, required=True)
    doctor.add_argument('--server-name', default='visual-bridge')
    doctor.add_argument('--handshake', action='store_true', help='Probe the server with the official SDK, not the commercial client')
    mcp = commands.add_parser('mcp', help='Run the optional official MCP server')
    mcp.add_argument('--transport', choices=['stdio', 'streamable-http'], default='stdio')
    mcp.add_argument('--host', default='127.0.0.1')
    mcp.add_argument('--port', type=int, default=8766)
    mcp.add_argument('--token-file', type=Path)
    opened = commands.add_parser('open', help='Open a detached browser session and return JSON promptly')
    opened.add_argument('review_id')
    opened.add_argument('--lease-seconds', type=float, default=3600)
    opened.add_argument('--open-browser', action='store_true')
    commands.add_parser('browser-stop', help='Close detached browser access for this database, preserving reviews')
    auto = commands.add_parser('auto', help='Generate report and optionally wait for decisions')
    auto.add_argument('input')
    auto.add_argument('-o', '--output')
    auto.add_argument('-t', '--type', choices=['audit', 'plan', 'review', 'decision'])
    auto.add_argument('--open', dest='open', action='store_true', default=True)
    auto.add_argument('--no-open', dest='open', action='store_false')
    modes = auto.add_mutually_exclusive_group()
    modes.add_argument('--serve', action='store_true')
    modes.add_argument('--watch', action='store_true')
    auto.add_argument('--timeout', type=float, default=600)
    auto.add_argument('--feedback-out')
    read = commands.add_parser('read')
    read.add_argument('html_file')
    read.add_argument('--markdown', action='store_true')
    read.add_argument('-o', '--output')
    init = commands.add_parser('init')
    init.add_argument('type', choices=['audit', 'plan', 'review', 'decision'])
    init.add_argument('-o', '--output')
    for name in ('watch', 'serve'):
        cmd = commands.add_parser(name)
        cmd.add_argument('html_file')
        cmd.add_argument('--timeout', type=float, default=600)
        cmd.add_argument('-o', '--output')
        if name == 'serve':
            cmd.add_argument('--port', '-p', type=int, default=0)
            cmd.add_argument('--open', dest='open', action='store_true', default=True)
            cmd.add_argument('--no-open', dest='open', action='store_false')
    create = commands.add_parser('create', help='Create a persistent review and return JSON')
    create.add_argument('input')
    create.add_argument('-o', '--output')
    commands.add_parser('list')
    for name in ('get', 'events', 'cancel', 'metrics', 'resume', 'pilot-report'):
        cmd = commands.add_parser(name)
        cmd.add_argument('review_id')
        if name == 'resume':
            cmd.add_argument('--port', type=int, default=0)
            cmd.add_argument('--no-open', action='store_true')
    receipt = commands.add_parser('receipt')
    receipt.add_argument('receipt_id')
    for name in ('submit', 'revise'):
        cmd = commands.add_parser(name)
        cmd.add_argument('review_id')
        cmd.add_argument('input')
        if name == 'revise':
            cmd.add_argument('--revision', type=int, required=True)
    question = commands.add_parser('question')
    question.add_argument('review_id')
    question.add_argument('item_id')
    question.add_argument('message')
    control = commands.add_parser('control')
    control.add_argument('review_id')
    control.add_argument('action', choices=['pause', 'resume', 'stop', 'priority', 'constraint'])
    control.add_argument('--payload', default='{}')
    settings = commands.add_parser('settings')
    settings.add_argument('project_id')
    settings.add_argument('--input')
    pilot = commands.add_parser('pilot-record')
    pilot.add_argument('review_id')
    pilot.add_argument('input')
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    try:
        if args.command in {'setup', 'doctor'}:
            from .installation import setup, doctor
            result = (setup(args.project, args.client, dry_run=args.dry_run, output=args.output, server_name=args.server_name)
                      if args.command == 'setup' else doctor(args.project, args.client, handshake=args.handshake, server_name=args.server_name))
            _handle_feedback_output(result)
            return 0
        if args.command == 'mcp':
            from .mcp.server import run_mcp_server
            run_mcp_server(args.db, args.transport, args.host, args.port, args.token_file)
            return 0
        if args.command in {'open', 'browser-stop'}:
            from .browser import open_browser_session, stop_browser_sessions
            database = ReviewService(args.db).store.path
            if args.command == 'browser-stop':
                result = stop_browser_sessions(database)
            else:
                result = open_browser_session(database, args.review_id, lease_seconds=args.lease_seconds)
                if args.open_browser:
                    webbrowser.open(result['url'])
            _handle_feedback_output(result)
            return 0
        if args.command == 'init':
            out = Path(args.output or f'sample_{args.type}.json')
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(starter(args.type), indent=2, ensure_ascii=False), encoding='utf-8')
            return 0
        if args.command == 'auto':
            bridge = VisualBridge.from_json_file(args.input, report_type=args.type)
            out = bridge.save_html(args.output or Path(args.input).with_suffix('.html'))
            if args.serve:
                result = serve_and_wait(out, timeout=args.timeout, open_browser=args.open, service=ReviewService(args.db))
                _handle_feedback_output(result, args.feedback_out)
            elif args.watch:
                if args.open:
                    webbrowser.open(out.resolve().as_uri())
                _handle_feedback_output(watch_html_file(out, timeout=args.timeout), args.feedback_out)
            elif args.open:
                webbrowser.open(out.resolve().as_uri())
            return 0
        if args.command == 'read':
            result = read_decision_file(args.html_file)
            if args.markdown:
                from .models import mandate
                print(result.get('mandate_markdown') or mandate(result.get('decisions', []), result.get('pending', [])))
            else:
                _handle_feedback_output(result, args.output)
            return 0
        if args.command in {'watch', 'serve'}:
            result = (watch_html_file(args.html_file, timeout=args.timeout) if args.command == 'watch'
                      else serve_and_wait(args.html_file, port=args.port, open_browser=args.open,
                                          timeout=args.timeout, service=ReviewService(args.db)))
            _handle_feedback_output(result, args.output)
            return 0
        service = ReviewService(args.db)
        command = args.command
        if command == 'create':
            result = service.create_review(json.loads(Path(args.input).read_text(encoding='utf-8')))
            if args.output:
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(render_review(result), encoding='utf-8')
        elif command == 'list':
            result = service.list_reviews()
        elif command == 'get':
            result = service.get_review(args.review_id)
        elif command == 'receipt':
            result = service.get_receipt(args.receipt_id)
        elif command == 'events':
            result = service.events(args.review_id)
        elif command == 'cancel':
            result = service.close_review(args.review_id)
        elif command == 'metrics':
            result = summarize(service, args.review_id)
        elif command == 'pilot-report':
            from .evaluation import pilot_report
            result = pilot_report(service, args.review_id)
        elif command == 'pilot-record':
            from .evaluation import record_observation
            result = record_observation(service, args.review_id, json.loads(Path(args.input).read_text(encoding='utf-8')))
        elif command == 'submit':
            data = read_decision_file(args.input)
            if data.get('review_id') != args.review_id or not data.get('submitted_at'):
                raise ValidationError('Explicit submission for this review required')
            result = service.submit_decisions(args.review_id, data.get('revision'), data.get('decisions'),
                                              data.get('request_key', ''), provenance='imported-artifact-unverified')
        elif command == 'revise':
            result = service.revise_review(args.review_id, json.loads(Path(args.input).read_text(encoding='utf-8')), args.revision)
        elif command == 'question':
            result = service.ask_item_question(args.review_id, args.item_id, args.message)
        elif command == 'control':
            result = service.request_control(args.review_id, args.action, json.loads(args.payload))
        elif command == 'settings':
            result = service.settings(args.project_id, json.loads(Path(args.input).read_text(encoding='utf-8')) if args.input else None)
        elif command == 'resume':
            with LocalServer(service, args.review_id, args.port) as server:
                print(json.dumps({'url': server.url, 'review_id': args.review_id}), flush=True)
                if not args.no_open:
                    webbrowser.open(server.url)
                try:
                    while True:
                        time.sleep(.5)
                except KeyboardInterrupt:
                    return 0
        _handle_feedback_output(result)
        return 0
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
