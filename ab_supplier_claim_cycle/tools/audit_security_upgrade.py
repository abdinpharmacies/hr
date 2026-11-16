#!/usr/bin/env python3
"""Read-only fingerprints for an in-place supplier-claim security upgrade.

Only counts, hashes, security IDs and memberships are written, never record/file
contents or a database backup. PostgreSQL transactions are explicitly read-only.
"""
import argparse
import configparser
import datetime
import hashlib
import json
from pathlib import Path

import psycopg2
from psycopg2 import sql

CORE_ROLES = ('participant', 'user', 'reviewer', 'admin')
ALL_ROLES = CORE_ROLES + ('inventory', 'purchasing', 'supplier_accounts', 'bank_accounts', 'tax')
TABLES = (
    'ab_supplier_claim_cycle', 'ab_supplier_claim_workflow',
    'ab_supplier_claim_workflow_stage', 'ab_supplier_claim_stage_state',
    'ab_supplier_claim_cycle_history', 'ab_supplier_claim_document',
    'ab_supplier_claim_stage_approver_rel', 'ab_supplier_claim_stage_allowed_field_rel',
)


def fingerprint(conn, table, where=None):
    digest = hashlib.sha256()
    count = 0
    with conn.cursor(name='supplier_claim_security_audit') as cur:
        query = sql.SQL('SELECT * FROM {} {} ORDER BY {}').format(
            sql.Identifier(table), sql.SQL('WHERE ' + where) if where else sql.SQL(''),
            sql.SQL('1, 2') if table.endswith('_rel') else sql.SQL('id'))
        cur.itersize = 10
        cur.execute(query)
        for row in cur:
            count += 1
            for value in row:
                if isinstance(value, memoryview):
                    data = value
                    digest.update(b'B')
                else:
                    data = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
                    digest.update(b'J')
                digest.update(str(len(data)).encode() + b':')
                digest.update(data)
            digest.update(b'\n')
    return {'rows': count, 'sha256': digest.hexdigest()}


def capture(config_path, database):
    config = configparser.ConfigParser(interpolation=None)
    config.read(config_path)
    kwargs = {'dbname': database, 'application_name': 'supplier_claim_security_READ_ONLY_audit'}
    for name in ('host', 'port', 'user', 'password'):
        value = config['options'].get('db_' + name)
        if value and value.lower() not in ('none', 'false'):
            kwargs[name] = value
    conn = psycopg2.connect(**kwargs)
    conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
    try:
        business = {table: fingerprint(conn, table) for table in TABLES}
        for table, where in (
            ('mail_message', "model='ab_supplier_claim_cycle'"),
            ('mail_tracking_value', "mail_message_id IN (SELECT id FROM mail_message WHERE model='ab_supplier_claim_cycle')"),
            ('message_attachment_rel', "message_id IN (SELECT id FROM mail_message WHERE model='ab_supplier_claim_cycle')"),
            ('ir_attachment', "(res_model='ab_supplier_claim_cycle') OR id IN (SELECT attachment_id FROM message_attachment_rel WHERE message_id IN (SELECT id FROM mail_message WHERE model='ab_supplier_claim_cycle'))"),
            ('ir_model_data', "module LIKE 'claim_transfer_%'"),
            ('ir_config_parameter', "key LIKE 'claim_transfer_%'"),
        ):
            business[table] = fingerprint(conn, table, where)
        with conn.cursor() as cur:
            cur.execute("""SELECT DISTINCT a.store_fname,a.checksum FROM ir_attachment a
                WHERE a.store_fname IS NOT NULL AND (
                    (a.res_model='ab_supplier_claim_cycle' AND a.res_id IN
                        (SELECT id FROM ab_supplier_claim_cycle))
                    OR a.id IN (SELECT x.attachment_id FROM message_attachment_rel x
                        JOIN mail_message m ON m.id=x.message_id
                        WHERE m.model='ab_supplier_claim_cycle' AND m.res_id IN
                            (SELECT id FROM ab_supplier_claim_cycle)))
                ORDER BY a.store_fname""")
            files = cur.fetchall()
            data_dir = config['options'].get('data_dir')
            if not data_dir or data_dir.lower() in ('false', 'none'):
                data_dir = str(Path.home() / '.local/share/Odoo')
            filestore = Path(data_dir) / 'filestore' / database
            file_digest = hashlib.sha256()
            for filename, checksum in files:
                file_hash = hashlib.sha1()
                with (filestore / filename).open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        file_hash.update(chunk)
                if file_hash.hexdigest() != checksum:
                    raise ValueError('Attachment checksum mismatch: ' + filename)
                file_digest.update((filename + ':' + checksum + '\n').encode())
            business['filestore'] = {'rows': len(files), 'sha256': file_digest.hexdigest()}
            cur.execute("SELECT name,res_id FROM ir_model_data WHERE module='ab_supplier_claim_cycle' AND model='res.groups'")
            groups = dict(cur.fetchall())
            cur.execute("SELECT d.name,r.uid FROM ir_model_data d JOIN res_groups_users_rel r ON r.gid=d.res_id WHERE d.module='ab_supplier_claim_cycle' AND d.model='res.groups' ORDER BY d.name,r.uid")
            members = {name: [] for name in groups}
            for name, uid in cur.fetchall():
                members[name].append(uid)
            cur.execute("SELECT latest_version FROM ir_module_module WHERE name='ab_supplier_claim_cycle'")
            version = cur.fetchone()[0]
        return {'database': database, 'captured_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'version': version, 'business': business, 'groups': groups, 'members': members}
    finally:
        conn.rollback()
        conn.close()


def compare(before, after):
    errors = []
    if before['database'] != after['database']:
        errors.append('Different databases')
    for table, expected in before['business'].items():
        if after['business'].get(table) != expected:
            errors.append('Business data changed: ' + table)
    prefix = 'supplier_claim_group_'
    expected_roles = {prefix + role for role in CORE_ROLES}
    if set(after['groups']) != expected_roles:
        errors.append('Expected exactly four generic roles')
    for name in expected_roles:
        if before['groups'].get(name) != after['groups'].get(name):
            errors.append('Retained group ID changed: ' + name)
        if not set(before['members'].get(name, ())) <= set(after['members'].get(name, ())):
            errors.append('Existing role membership lost: ' + name)
    old_users = set().union(*(set(before['members'].get(prefix + role, ())) for role in ALL_ROLES[4:]))
    if not old_users <= set(after['members'].get(prefix + 'participant', ())):
        errors.append('Department users lost Participant membership')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='/opt/odoo19/config/hr19.conf')
    parser.add_argument('--database', default='hr_db_dev')
    parser.add_argument('--output', required=True)
    parser.add_argument('--compare')
    args = parser.parse_args()
    report = capture(args.config, args.database)
    if args.compare:
        report['errors'] = compare(json.loads(Path(args.compare).read_text()), report)
    output = Path(args.output)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    output.chmod(0o600)
    print(json.dumps({'version': report['version'], 'counts': {k: v['rows'] for k, v in report['business'].items()},
                      'groups': sorted(report['groups']), 'errors': report.get('errors', [])}))
    if report.get('errors'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
