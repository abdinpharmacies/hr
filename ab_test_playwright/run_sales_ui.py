#!/usr/bin/env python3
"""Run JSON sales cases through the POS, with optional explicit submission."""
import argparse
from datetime import datetime, timezone
import getpass
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

from prepare_test_data import connect, select_rows

ROOT = Path(__file__).resolve().parent


def connection_settings(parser, args):
    for field, label, flag in (('url', 'Odoo URL', '--url'), ('db', 'Database name', '--db')):
        value = getattr(args, field)
        if value is None:
            if not sys.stdin.isatty():
                parser.error(f'Specify {flag} when running unattended')
            try:
                value = input(f'{label}: ')
            except EOFError:
                parser.error(f'{label} is required')
        if not value.strip():
            parser.error(f'{label} must not be empty')
        setattr(args, field, value)
    try:
        target = urlsplit(args.url)
        hostname = target.hostname
        local = hostname == 'localhost'
        if not local:
            local = ipaddress.ip_address(hostname).is_loopback
        if (target.scheme not in ('http', 'https') or not local
                or target.username is not None or target.password is not None
                or target.path not in ('', '/') or target.query or target.fragment
                or any(char.isspace() for char in args.url)):
            raise ValueError
        if target.port is not None and target.port == 0:
            raise ValueError
    except (ValueError, TypeError):
        parser.error('Odoo URL must be an HTTP/HTTPS localhost or loopback origin, without credentials, path, query or fragment')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--list-actions', action='store_true', help='List registered JSON step actions and exit')
    p.add_argument('--suite', type=Path, default=ROOT / 'sales_ui_cases.json')
    p.add_argument('--config', default=str(ROOT.parent / 'odoo19-POS.conf'))
    p.add_argument('--db', help='Database name; prompted when omitted')
    p.add_argument('--url', help='Local Odoo HTTP/HTTPS URL; prompted when omitted')
    p.add_argument('--case', action='append', dest='cases')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--headed', action='store_true')
    mode.add_argument('--headless', action='store_true')
    args = p.parse_args()
    actions = json.loads((ROOT / 'actions.json').read_text())['actions']
    if args.list_actions:
        print('\n'.join(actions))
        return 0
    suite = json.loads(args.suite.read_text())
    if suite.get('schema_version') != 1 or suite['defaults']['execution_mode'] != 'preview':
        p.error('This runner supports schema version 1 in preview mode only')
    if args.cases:
        unknown = set(args.cases) - {c['id'] for c in suite['cases']}
        if unknown:
            p.error('Unknown case IDs: ' + ', '.join(sorted(unknown)))
        suite['cases'] = [c for c in suite['cases'] if c['id'] in args.cases]
    for case in suite['cases']:
        names = [step.get('action') for step in case['steps']]
        unknown = [name for name in names if name not in actions]
        if unknown:
            p.error(f"{case['id']}: unregistered actions: {unknown}")
        if 'submit' in names:
            index = names.index('submit')
            if names.count('submit') != 1 or index == 0 or names[index-1] != 'prepare_submission':
                p.error(f"{case['id']}: submit must occur once immediately after prepare_submission")
            if names[index+1:] != ['assert_saved_invoice_if_submitted']:
                p.error(f"{case['id']}: submit must be followed by assert_saved_invoice_if_submitted as the final step")
    connection_settings(p, args)
    if not args.headed and not args.headless:
        if not sys.stdin.isatty():
            p.error('Specify --headed or --headless when running unattended')
        choice = input('Browser mode: [1] Visible / [2] Headless (default 2): ').strip()
        if choice not in ('', '1', '2'):
            p.error('Choose 1 or 2')
        args.headed = choice == '1'
    password = os.environ.get('AB_TEST_PASSWORD') or getpass.getpass('Odoo password: ')
    pin = os.environ.get('AB_TEST_PIN') or getpass.getpass('Employee PIN: ')
    metadata = {}
    with connect(args.config, args.db) as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            records = suite['records']
            user = select_rows(cur, 'res_users', ['id', 'login', 'active'], [records['user_id']])[0]
            if not user['active'] or user['login'] != suite['credentials']['login']:
                raise ValueError('Login identity changed')
            profile = select_rows(cur, 'ab_employee_access', ['id', 'employee_id', 'pos_allow_login'], [records['employee_access_id']])[0]
            if profile['employee_id'] != records['employee_id']:
                raise ValueError('Employee profile identity changed')
            if not profile['pos_allow_login']:
                raise ValueError(f"Employee access profile {profile['id']} has POS login disabled; enable Pos Allow Login in Odoo or select an authorized test profile")
            for key, table, ids in [('store', 'ab_store', [records['store_id']]),
                                    ('employee', 'ab_hr_employee', [records['employee_id']]),
                                    ('customer', 'ab_customer', [records['customer_id']]),
                                    ('contracts', 'ab_contract', records['contract_ids']),
                                    ('promotion', 'ab_promo_program', [records['promotion_id']])]:
                rows = select_rows(cur, table, ['id', 'name'], ids)
                if any(not row['name'].startswith('[TEST] ') for row in rows):
                    raise ValueError(f'{key} is not marked as test data')
                metadata[key] = rows if key == 'contracts' else rows[0]
            for product in records['products']:
                row = select_rows(cur, 'ab_product', ['id', 'code', 'eplus_serial', 'default_price'], [product['id']])[0]
                if row['code'] != product['code'] or row['eplus_serial'] != product['eplus_serial'] or float(row['default_price']) != product['unit_price']:
                    raise ValueError('Product identity/price drift; review expected values')
                cur.execute('SELECT pc.origin FROM ab_product p JOIN ab_product_card pc ON pc.id=p.product_card_id WHERE p.id=%s', (product['id'],))
                if cur.fetchone()[0] != product['origin']:
                    raise ValueError('Product origin changed; review contract expectations')
            store = select_rows(cur, 'ab_store', ['id', 'code', 'eplus_serial'], [records['store_id']])[0]
            customer = select_rows(cur, 'ab_customer', ['id', 'code'], [records['customer_id']])[0]
            if store['code'] != records['store_code'] or store['eplus_serial'] != records['store_eplus_serial'] or customer['code'] != records['customer_code']:
                raise ValueError('Store/customer identity drift')
            for contract in suite['fixtures']['contracts']:
                row = select_rows(cur, 'ab_contract', ['id'] + list(contract['values']), [contract['id']])[0]
                if any(row[k] != v for k, v in contract['values'].items()):
                    raise ValueError('Contract setup differs; run prepare_sales_scenarios.py first')
            promo = suite['fixtures']['promotion']
            expected = {**promo['required_values'], **promo['values']}
            row = select_rows(cur, 'ab_promo_program', ['id'] + list(expected), [promo['id']])[0]
            if any(row[k] != v for k, v in expected.items()):
                raise ValueError('Promotion setup differs; run prepare_sales_scenarios.py first')
            cur.execute('SELECT product_id FROM ab_promo_program_explicit_product_rel WHERE promo_id=%s', (promo['id'],))
            members = {row[0] for row in cur.fetchall()}
            if not set(promo['required_product_ids']) <= members or set(promo['excluded_test_product_ids']) & members:
                raise ValueError('Promotion product membership changed')
            cur.execute("SELECT res_id FROM ir_model_data WHERE module='ab_sales' AND name='ab_sales_pos_action'")
            metadata['action_id'] = cur.fetchone()[0]
        conn.rollback()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = Path('/opt/playwright/artifacts/replica_addons/sales_suite') / stamp
    output.mkdir(parents=True, mode=0o700)
    payload = {'suite': suite, 'metadata': metadata, 'password': password, 'pin': pin,
               'database': args.db, 'url': args.url, 'headed': args.headed, 'output': str(output)}
    env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH='/opt/playwright/browsers')
    for key in ('AB_TEST_PASSWORD', 'AB_TEST_PIN'):
        env.pop(key, None)
    result = subprocess.run(['node', str(ROOT / 'sales_ui_runner.mjs')], input=json.dumps(payload), text=True, env=env)
    print(f'Report: {output / "results.json"}')
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
