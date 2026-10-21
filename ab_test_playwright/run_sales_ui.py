import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from common import ACTIONS, ROOT, load_suite, local_url, private_json
from terminal_setup import SetupCancelled, ask, read_credentials, resolve_suite


def main():
    parser = argparse.ArgumentParser(description='Run standalone Callcenter Playwright scenarios; preview is the default')
    parser.add_argument('--suite', type=Path, default=ROOT / 'sales_ui_cases.json')
    parser.add_argument('--config', type=Path, default=ROOT.parent / 'odoo19-callcenter.conf')
    parser.add_argument('--db')
    parser.add_argument('--url')
    parser.add_argument('--login')
    parser.add_argument('--case', action='append')
    parser.add_argument('--allow-submit', action='store_true')
    parser.add_argument('--validate', action='store_true')
    parser.add_argument('--list-actions', action='store_true')
    parser.add_argument('--list-cases', action='store_true')
    parser.add_argument('--output', type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--headed', action='store_true')
    modes.add_argument('--headless', action='store_true')
    args = parser.parse_args()
    if args.list_actions:
        print('\n'.join(ACTIONS))
        return 0
    try:
        suite = load_suite(args.suite, args.case, args.allow_submit)
    except (ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    if args.list_cases:
        print('\n'.join(case['id'] for case in suite['cases']))
        return 0
    if args.validate:
        print(f"Validated {len(suite['cases'])} cases and {len(ACTIONS)} registered actions; no connection made")
        return 0
    interactive = sys.stdin.isatty()
    args.url = local_url(args.url) if args.url else ask('Odoo URL (--url)', validate=local_url, interactive=interactive)
    args.db = args.db or ask('QA database name (--db)', interactive=interactive)
    if not args.config.is_file():
        parser.error('Selected Odoo configuration does not exist')
    if not args.headed and not args.headless:
        if not interactive:
            raise ValueError('Choose --headed or --headless when unattended')
        def browser_mode(value):
            if value not in ('1', '2'):
                raise ValueError('Choose 1 or 2')
            return value
        answer = ask('Browser mode: [1] Visible / [2] Headless', '2', browser_mode)
        args.headed = answer == '1'
    if args.login:
        suite['credentials']['login'] = args.login
    from qa_orm import configured_records, environment, inspect
    posting = any(step['action'] == 'submit' for case in suite['cases'] for step in case['steps'])
    while True:
        with environment(args.config, args.db) as env:
            suite = resolve_suite(env, suite, args.db, interactive)
            configured_records(suite)
            try:
                metadata = inspect(env, suite, require_test_context=posting)
            except ValueError as error:
                if not interactive:
                    raise
                print('Fixture check:', error)
                answer = ask('Review record selections and try again? y/n', 'y')
                if answer.lower() != 'y':
                    return 1
                continue
        break
    output = args.output or ROOT / 'reports' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    private_json(output / 'selected-suite.json', suite)
    private_json(output / 'metadata.json', metadata)
    secrets = read_credentials(suite, interactive)
    configuration = {'suite': suite, 'metadata': metadata,
                     'database': args.db, 'url': args.url, 'headed': args.headed,
                     'output': str(output.resolve()), 'allowSubmit': args.allow_submit, **secrets}
    process_environment = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH='/opt/playwright/browsers', PYTHONDONTWRITEBYTECODE='1')
    for key in (suite['credentials']['password_env'], suite['credentials']['employee_pin_env']):
        process_environment.pop(key, None)
    process = subprocess.run(['node', str(ROOT / 'sales_ui_runner.mjs')], input=json.dumps(configuration),
                             text=True, env=process_environment, capture_output=True)
    for text in [process.stdout, process.stderr]:
        for secret in secrets.values():
            text = text.replace(secret, '[REDACTED]')
        print(text, end='')
    print('Reports:', output)
    return process.returncode


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (SetupCancelled, KeyboardInterrupt, EOFError):
        print('Setup cancelled; no test run started')
        raise SystemExit(130) from None
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from None
