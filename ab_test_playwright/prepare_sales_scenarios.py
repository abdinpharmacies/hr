#!/usr/bin/env python3
"""Apply the bounded contract/promotion fixture configuration from the UI suite."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from psycopg2 import sql
from prepare_test_data import connect, preparation_database, select_rows

ROOT = Path(__file__).resolve().parent
CONTRACT_FIELDS = {
    'name', 'active', 'paid_percentage', 'paid_amount', 'max_bill_value',
    'discount_percentage_rule', 'allow_total_invoice_discount', 'allow_promotions',
    'total_invoice_discount_source', 'local_product_discount',
    'imported_product_discount', 'local_made_product_discount',
    'special_import_product_discount', 'investment_product_discount', 'other_product_discount',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, default=ROOT / 'sales_ui_cases.json')
    parser.add_argument('--config', default=str(ROOT.parent / 'odoo19-POS.conf'))
    parser.add_argument('--db', help='Database name; prompted when omitted')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    args.db = preparation_database(parser, args.db)
    suite = json.loads(args.suite.read_text())
    contracts = suite['fixtures']['contracts']
    promo = suite['fixtures']['promotion']
    if sorted(c['id'] for c in contracts) != [1, 2, 3, 4] or promo['id'] != 2:
        raise ValueError('Only the agreed contract/promotion IDs may be changed')
    for contract in contracts:
        if set(contract['values']) - CONTRACT_FIELDS:
            raise ValueError('Unexpected contract field')
    if set(promo['values']) != {'rule_date_from', 'rule_date_to'}:
        raise ValueError('Only promotion dates may be changed')
    changes = []
    conn = connect(args.config, args.db)
    try:
        conn.set_session(readonly=not args.apply, isolation_level='SERIALIZABLE')
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '30s'")
            for table, entries in [('ab_contract', contracts), ('ab_promo_program', [promo])]:
                for entry in entries:
                    columns = list(dict.fromkeys(['id', 'name'] + list(entry['values']) + list(entry.get('required_values', {}))))
                    row = select_rows(cursor, table, columns, [entry['id']], args.apply)[0]
                    if not row['name'].startswith('[TEST] '):
                        raise ValueError(f'{table} {entry["id"]} is not marked as test data')
                    for field, value in entry.get('required_values', {}).items():
                        if row[field] != value:
                            raise ValueError(f'{table}.{field} differs from suite precondition')
                    for column, after in entry['values'].items():
                        changes.append({'table': table, 'id': entry['id'], 'column': column,
                                        'before': row[column], 'after': after})
            cursor.execute('SELECT product_id FROM ab_promo_program_explicit_product_rel WHERE promo_id=2')
            members = {r[0] for r in cursor.fetchall()}
            if not set(promo['required_product_ids']) <= members or set(promo['excluded_test_product_ids']) & members:
                raise ValueError('Promotion membership does not match suite')
            cursor.execute('SELECT id FROM ab_contract_product_origin WHERE contract_id = ANY(%s) AND product_card_id = ANY(%s)', ([1, 2, 3, 4], [74542, 94123]))
            if cursor.fetchall():
                raise ValueError('Product-specific contract overrides conflict with origin discount cases')
            if not args.apply:
                print('Read-only preview: configure contracts 1–4 and remove promotion 2 date restrictions.')
                print(f'{sum(c["before"] != c["after"] for c in changes)} fields would change.')
                conn.rollback()
                return
            backup_dir = ROOT / 'backups'
            backup_dir.mkdir(mode=0o700, exist_ok=True)
            os.chmod(backup_dir, 0o700)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup = backup_dir / f'before-sales-scenarios-{stamp}.json'
            fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as stream:
                json.dump({'database': args.db, 'changes': changes}, stream, indent=2, default=str)
                stream.flush()
                os.fsync(stream.fileno())
            for change in changes:
                if change['before'] == change['after']:
                    continue
                cursor.execute(sql.SQL('UPDATE {} SET {}=%s WHERE id=%s AND {} IS NOT DISTINCT FROM %s').format(
                    sql.Identifier(change['table']), sql.Identifier(change['column']), sql.Identifier(change['column'])),
                    (change['after'], change['id'], change['before']))
                if cursor.rowcount != 1:
                    raise ValueError('Unexpected update count')
            for change in changes:
                row = select_rows(cursor, change['table'], ['id', change['column']], [change['id']])[0]
                if row[change['column']] != change['after']:
                    raise ValueError('Post-update verification failed')
            conn.commit()
            print(f'Fixture configuration committed and verified. Backup: {backup}')
    finally:
        conn.rollback()
        conn.close()


if __name__ == '__main__':
    main()
