#!/usr/bin/env python3
"""Offline supplier-claim migration CLI. See MIGRATION.md before use."""
import argparse
import base64
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

HERE = Path(__file__).resolve().parent
CLAIM = 'ab_supplier_claim_cycle'
PREFIX = 'ab_supplier_claim_cycle.'
DEPARTMENTS = ('inventory', 'purchasing', 'supplier_accounts', 'bank_accounts')
CASH = ('supplier_accounts', 'secretarial')
BANK = (*DEPARTMENTS, 'secretarial')
MODEL_TABLES = {
    CLAIM: CLAIM, 'ab_supplier_claim_cycle.history': 'ab_supplier_claim_cycle_history',
    'ab_supplier_claim_document': 'ab_supplier_claim_document',
    'ab_supplier_claim_stage_state': 'ab_supplier_claim_stage_state',
    'ab_supplier_claim_workflow': 'ab_supplier_claim_workflow',
    'ab_supplier_claim_workflow_stage': 'ab_supplier_claim_workflow_stage',
    'mail.message': 'mail_message', 'mail.tracking.value': 'mail_tracking_value',
    'ir.attachment': 'ir_attachment',
}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def amount(value, round_to_cents=False):
    text = str(value).strip()
    precision = r'\d*' if round_to_cents else r'\d{0,2}'
    if not re.fullmatch(r'(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.' + precision + r')?', text):
        raise ValueError('Unsupported amount: %r' % value)
    try:
        parsed = Decimal(text.replace(',', ''))
    except InvalidOperation as exc:
        raise ValueError('Invalid amount') from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError('Amount must be positive')
    if round_to_cents:
        parsed = parsed.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if parsed <= 0:
            raise ValueError('Rounded amount must be positive')
    return float(parsed)


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    path.chmod(0o600)


def collect(args):
    target = Path(args.bundle).resolve()
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    blobs = target / 'blobs'
    blobs.mkdir(mode=0o700)
    script = (HERE / 'export_readonly.py').read_bytes()
    command = [args.source_python, '-', args.source_config, args.source_db, args.source_filestore]
    if args.namespace:
        command.append(args.namespace)
    if args.ssh:
        command = ['ssh', '-C', '-o', 'BatchMode=yes', args.ssh,
                   'sudo -n -u ' + shlex.quote(args.source_user) + ' env PYTHONDONTWRITEBYTECODE=1 ' + shlex.join(command)]
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    proc.stdin.write(script)
    proc.stdin.close()
    tables = {}
    meta = None
    end = None

    def binaries(value):
        if isinstance(value, dict) and '$binary' in value:
            content = base64.b64decode(value['$binary'], validate=True)
            sha = digest(content)
            path = blobs / sha
            if not path.exists():
                path.write_bytes(content)
            return {'blob': sha, 'size': len(content)}
        if isinstance(value, dict):
            return {key: binaries(item) for key, item in value.items()}
        if isinstance(value, list):
            return [binaries(item) for item in value]
        return value

    try:
        for line in proc.stdout:
            entry = json.loads(line)
            table, row = entry['table'], binaries(entry['row'])
            if table == 'meta':
                meta = row
            elif table == 'end':
                end = row
            else:
                tables.setdefault(table, []).append(row)
        if proc.wait() or not meta or not end or meta['read_only'] != 'on':
            raise RuntimeError('Incomplete export; source must be read-only')
        for table, count in end['counts'].items():
            tables.setdefault(table, [])
            if len(tables[table]) != count:
                raise ValueError('Export count mismatch: ' + table)
        data = {'meta': meta, 'tables': tables}
        save_json(target / 'data.json', data)
        save_json(target / 'manifest.json', {'format': 1, 'data_sha256': digest((target / 'data.json').read_bytes()),
                  'counts': end['counts'], 'blob_count': len(list(blobs.iterdir()))})
        print(json.dumps({'bundle': str(target), **end}))
    except BaseException:
        proc.kill()
        proc.wait()
        raise


class Bundle:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.manifest = json.loads((self.path / 'manifest.json').read_text())
        raw = (self.path / 'data.json').read_bytes()
        if self.manifest['format'] != 1 or digest(raw) != self.manifest['data_sha256']:
            raise ValueError('Unsupported or damaged bundle')
        data = json.loads(raw)
        self.meta, self.tables = data['meta'], data['tables']
        source_identity = self.meta['uuid'] + '/' + self.meta['database']
        self.namespace = 'claim_transfer_' + digest(source_identity.encode())[:16]
        for table, count in self.manifest['counts'].items():
            if len(self.tables.get(table, [])) != count:
                raise ValueError('Bundle count mismatch: ' + table)
        for table in self.tables.values():
            for row in table:
                self.check_blobs(row)

    def check_blobs(self, value):
        if isinstance(value, dict):
            if 'blob' in value:
                self.blob(value)
            else:
                for item in value.values():
                    self.check_blobs(item)
        elif isinstance(value, list):
            for item in value:
                self.check_blobs(item)

    def blob(self, reference):
        sha = reference['blob']
        if not re.fullmatch('[0-9a-f]{64}', sha):
            raise ValueError('Invalid blob path')
        content = (self.path / 'blobs' / sha).read_bytes()
        if digest(content) != sha or len(content) != reference['size']:
            raise ValueError('Blob checksum/size mismatch: ' + sha)
        return content

    def rows(self, table):
        return self.tables.get(table, [])

    def resolve(self, value):
        if isinstance(value, dict) and 'blob' in value:
            return self.blob(value)
        return False if value is None else value


def legacy_runtime(row):
    """Map legacy department values without treating future 'pending' as active."""
    state = row['state']
    route = CASH if row.get('payment_nature') == 'cash' else BANK
    if state == 'draft':
        return route, 'draft', None, {}
    current = row.get('resume_stage') if state == 'returned_secretarial' else state
    if state == 'returned_secretarial':
        current = row.get('rejection_department') or current
    if state in ('ready_to_close', 'closed'):
        current = 'secretarial'
    if current not in route:
        raise ValueError('No compatible stage for source claim %s' % row['id'])
    index = route.index(current)
    statuses = {}
    for pos, department in enumerate(route):
        decision = row.get(department + '_decision')
        if state == 'closed' or pos < index or decision == 'approved':
            statuses[department] = 'approved'
        elif pos == index:
            statuses[department] = ('rejected' if state == 'returned_secretarial'
                                    else 'deferred' if decision == 'deferred' else 'pending')
        else:
            statuses[department] = 'waiting'
    return route, ('closed' if state == 'closed' else 'returned' if state == 'returned_secretarial' else 'in_progress'), current, statuses


def open_env(args):
    sys.path.insert(0, args.odoo_root)
    import odoo
    from odoo import api
    odoo.tools.config.parse_config(['-c', args.config, '-d', args.database, '--no-http', '--max-cron-threads=0'])
    registry = odoo.modules.registry.Registry(args.database)
    return registry, api


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    export = sub.add_parser('export')
    export.add_argument('--bundle', required=True)
    export.add_argument('--ssh')
    export.add_argument('--namespace', help='Export only claims belonging to this migration namespace')
    export.add_argument('--source-user', default='odoo19s1')
    export.add_argument('--source-python', default='/opt/odoo19s1/venv19/bin/python3')
    export.add_argument('--source-config', default='/opt/odoo19s1/odoo19s1.conf')
    export.add_argument('--source-db', default='hr_db')
    export.add_argument('--source-filestore', default='/opt/odoo19s1/.local/share/Odoo/filestore')
    for command in ('preflight', 'import', 'verify'):
        p = sub.add_parser(command)
        p.add_argument('--bundle', required=True)
        p.add_argument('--config', default='/opt/odoo19/config/hr19.conf')
        p.add_argument('--database', default='hr_db_dev')
        p.add_argument('--odoo-root', default='/opt/odoo19/server')
        p.add_argument('--mappings', help='JSON with users/costcenters/companies/partners overrides keyed by source ID')
        p.add_argument('--amount-policy', choices=('strict', 'round'), default='strict',
                       help='round explicitly permits HALF_UP cents conversion with an audit note')
        p.add_argument('--report', required=True)
        if command == 'import':
            p.add_argument('--replace-claims', action='store_true')
            p.add_argument('--replace-source-snapshot', action='store_true',
                           help='Explicitly discard a previous import of this source; requires --replace-claims')
            p.add_argument('--confirm-database', required=True)
            p.add_argument('--commit', action='store_true', help='Without this option import is rolled back')
    args = parser.parse_args()
    if args.command == 'export':
        collect(args)
        return
    bundle = Bundle(args.bundle)
    registry, api = open_env(args)
    with registry.cursor() as cr:
        cr.execute("SELECT pg_advisory_xact_lock(hashtext('supplier_claim_transfer'))")
        env = api.Environment(cr, 1, {'active_test': False, 'tracking_disable': True,
              'mail_create_nosubscribe': True, 'mail_notrack': True, 'mail_notify_force_send': False})
        runner = Transfer(env, bundle, args)
        report = runner.preflight()
        if report['errors']:
            save_json(Path(args.report), report)
            raise ValueError('Preflight failed; see ' + args.report)
        if args.command == 'import':
            if args.confirm_database != args.database:
                raise ValueError('--confirm-database must exactly match target')
            try:
                report = runner.run()
            except Exception as exc:
                cr.rollback()
                save_json(Path(args.report), {'phase': 'import', 'committed': False,
                          'errors': [str(exc)], 'target': args.database})
                raise
            if args.commit:
                cr.commit()
            else:
                cr.rollback()
            report['committed'] = args.commit
            save_json(Path(args.report), report)
        elif args.command == 'verify':
            try:
                report = runner.verify()
            except Exception as exc:
                save_json(Path(args.report), {'phase': 'verification', 'errors': [str(exc)], 'target': args.database})
                raise
            save_json(Path(args.report), report)
            cr.rollback()
        else:
            save_json(Path(args.report), report)
            cr.rollback()
        print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    # Transfer is imported only for target operations; exporter needs no registry.
    if len(sys.argv) > 1 and sys.argv[1] != 'export':
        from transfer_target import Transfer
    main()
