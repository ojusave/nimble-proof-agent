#!/usr/bin/env python3
"""Start the browser app, or run the agent from the terminal."""
import argparse
import json
from pathlib import Path
from proof.agent import Agent, markdown
from proof.demo import DemoWeb, DemoModel, QUESTION
from proof.providers import ProviderError
from proof.hosted import NimbleAgent
from proof.server import load_env, serve


def main():
    parser = argparse.ArgumentParser(description='Proof — research with receipts')
    sub = parser.add_subparsers(dest='command', required=True)
    web = sub.add_parser('serve', help='Open the local browser app')
    web.add_argument('--port', type=int, default=8765)
    run = sub.add_parser('run', help='Run a research question')
    run.add_argument('question', nargs='?')
    run.add_argument('--demo', action='store_true', help='Use synthetic offline fixtures')
    run.add_argument('--output', type=Path, help='Save a Markdown brief')
    run.add_argument('--json', action='store_true', help='Print full evidence and trace as JSON')
    args = parser.parse_args()
    load_env()
    if args.command == 'serve':
        return serve(args.port)
    if not args.demo and not args.question:
        parser.error('Provide a question or use --demo.')
    try:
        agent = Agent(DemoWeb(), DemoModel()) if args.demo else NimbleAgent()
        result = agent.run(QUESTION if args.demo else args.question)
        result['mode'] = 'synthetic offline demo' if args.demo else 'live'
        report = markdown(result)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report)
        print(json.dumps(result, indent=2) if args.json else report)
    except (ValueError, ProviderError) as error:
        parser.exit(1, 'Error: %s\n' % error)


if __name__ == '__main__':
    main()
