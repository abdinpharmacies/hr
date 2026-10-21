import ipaddress
import json
import math
import os
from pathlib import Path
import re
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent
ACTIONS = json.loads((ROOT / 'actions.json').read_text())['actions']


def local_url(value):
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        local = host == 'localhost' or ipaddress.ip_address(host).is_loopback
        if (parsed.scheme not in ('http', 'https') or not local
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment
                or parsed.port == 0 or any(char.isspace() for char in value)):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError('Use an HTTP/HTTPS localhost or loopback origin without credentials, path, query, or fragment') from None
    return value.rstrip('/')


def load_suite(path, cases=None, allow_submit=False):
    suite = json.loads(Path(path).read_text())
    if Path(path).name == 'selected-suite.json' and Path(path).resolve().is_relative_to((ROOT / 'reports').resolve()):
        saved = suite
        suite = json.loads((ROOT / 'sales_ui_cases.json').read_text())
        for key in ('records', 'credentials', 'qa_database'):
            if key in saved:
                suite[key] = saved[key]
    if suite.get('schema_version') != 1 or suite.get('defaults', {}).get('execution_mode') != 'preview':
        raise ValueError('Expected schema version 1 with preview execution_mode')
    tolerance = suite['defaults'].get('money_tolerance')
    if not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or not 0 < tolerance <= 0.01:
        raise ValueError('money_tolerance must be positive and at most 0.01')
    identifiers = [case['id'] for case in suite['cases']]
    if (not identifiers or any(not isinstance(value, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', value) for value in identifiers)
            or len(set(identifiers)) != len(identifiers)):
        raise ValueError('Case identifiers must be unique uppercase names with digits or underscores')
    if set(suite['credentials']) != {'login', 'password_env', 'employee_pin_env'}:
        raise ValueError('Credentials must contain only login and password/PIN environment variable names')
    if set(suite['records']['products']) != {'base', 'promo'} or set(suite['records']['contracts']) != {
            'contract25', 'contract0', 'contract100', 'contractPromo'}:
        raise ValueError('Configure the two product aliases and four contract aliases used by this suite')
    if cases:
        missing = set(cases) - set(identifiers)
        if missing:
            raise ValueError('Unknown cases: ' + ', '.join(sorted(missing)))
        suite['cases'] = [case for case in suite['cases'] if case['id'] in cases]
    products = suite['records']['products']
    contracts = suite['records']['contracts']
    for case in suite['cases']:
        names = [step['action'] for step in case['steps']]
        if not names or names[0] != 'new_empty_bill' or names.count('new_empty_bill') != 1:
            raise ValueError(f"{case['id']}: create exactly one new empty bill first")
        if any(name not in ACTIONS for name in names):
            raise ValueError(f"{case['id']}: unregistered action")
        if 'submit' in names:
            index = names.index('submit')
            if not allow_submit:
                raise ValueError('Explicit submit steps require --allow-submit')
            if names.count('submit') != 1 or index == 0 or names[index - 1] != 'prepare_submission':
                raise ValueError('submit must occur once immediately after prepare_submission')
            if names[index + 1:] != ['assert_saved_invoice_if_submitted']:
                raise ValueError('submit must end with assert_saved_invoice_if_submitted')
        elif names[-3:] != ['prepare_submission', 'submit_or_preview', 'assert_saved_invoice_if_submitted']:
            raise ValueError(f"{case['id']}: preview must finish with submission dialog preview and verification")
        for step in case['steps']:
            if 'product' in step and step['product'] not in products:
                raise ValueError('Unknown product alias')
            if 'contract' in step and step['contract'] not in contracts:
                raise ValueError('Unknown contract alias')
            for name, amount in step.get('expected', {}).items() if isinstance(step.get('expected'), dict) else []:
                if name not in ('contract', 'promotion') and (type(amount) not in (int, float) or not math.isfinite(amount) or amount < 0):
                    raise ValueError('Intermediate expected amounts must be finite and nonnegative')
        if case['expected'].get('contract') and case['expected']['contract'] not in contracts:
            raise ValueError('Unknown expected contract')
        for line in case['lines']:
            if line['product'] not in products or not math.isfinite(line['qty']) or line['qty'] <= 0:
                raise ValueError('Invalid scenario line')
        for name, amount in case['expected'].items():
            if name not in ('contract', 'promotion') and (not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount < 0):
                raise ValueError('Expected amounts must be finite and nonnegative')
    return suite


def private_json(path, data):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, default=str)
        stream.flush()
        os.fsync(stream.fileno())


def positive_id(value, label):
    if type(value) is not int or value <= 0:
        raise ValueError(f'Configure a positive QA record ID for {label} in your local suite')
    return value
