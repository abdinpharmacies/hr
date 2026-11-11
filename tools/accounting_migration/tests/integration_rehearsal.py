"""Prepare a synthetic export for a dedicated, already initialized fixture database.

Never point this at a real export directory. Run after init-target, then invoke
`migrate.py ... import --rehearsal`. Verification MUST remain blocked because this
small fixture has no cross-branch access cases.
"""
import argparse
import base64
import hashlib
from pathlib import Path
import sqlite3
import sys
import uuid
from passlib.context import CryptContext
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import digest, dumps, loads, private_dir, save_json


def prepare(stage, source_defects=False):
    stage = private_dir(stage)
    marker = loads((stage / 'target.json').read_text())
    if 'fixture' not in marker['database']:
        raise ValueError('Dedicated fixture database required')
    path = stage / 'records.sqlite'
    if path.exists(): raise ValueError('Fixture export already exists')
    schema = loads((stage / 'target-schema.json').read_text())
    pw = CryptContext(schemes=['pbkdf2_sha512']).hash('synthetic-migration-test-password')
    records = {
        'res.company': [{'id': 9001, 'name': 'Synthetic Migration Company', 'parent_id': False, 'resource_calendar_id': 9401}],
        'res.partner': [{'id': 9010, 'name': 'Synthetic Migration User', 'active': True},
                        {'id': 9012, 'name': 'Synthetic Archived Partner', 'active': False, 'phone': False, 'mobile': '01234567890', 'credit_limit': 0, 'partner_gid': 0},
                        {'id': 9013, 'name': 'Synthetic Private Address', 'type': 'private', 'active': True}],
        'res.country': [{'id': 9003, 'name': 'Egypt', 'code': 'EG'}],
        'ir.sequence': [{'id': 9004, 'name': 'Synthetic Sequence', 'code': 'accounting_migration_fixture',
                         'implementation': 'standard', 'number_next': 321, 'number_increment': 3, 'padding': 5}],
        'resource.calendar': [{'id': 9401, 'name': 'Synthetic Schedule', 'company_id': 9001, 'tz': 'Africa/Cairo', 'two_weeks_calendar': False}],
        'resource.calendar.attendance': [{'id': 9402, 'name': 'Monday Morning', 'calendar_id': 9401, 'dayofweek': '0', 'day_period': 'morning', 'hour_from': 8.0, 'hour_to': 12.0}],
        'res.groups': [{'id': 9002}, {'id': 9005}, {'id': 9006}],
        'res.users': [{'id': 9011, 'login': 'synthetic_migration_fixture', 'partner_id': 9010,
                       'company_id': 9001, 'active': True, 'password': pw, 'enable_idle': True, 'idle_time': 7,
                       '_m2m': {'company_ids': [9001]}}],
        'ab_accounting_account_guide': [{'id': 9101, 'name': 'Synthetic Cash', 'code': 'TEST-MIGRATION',
                                         'internal_type': 'contract_deduction', 'internal_group': 'asset', 'calc_balance': False}],
        'ab_accounting_doctype': [{'id': 9102, 'name': 'Synthetic Migration', 'internal_type': 'cash'}],
        'ab_accounting_je_header': [{'id': 9201, 'account_id': 9101, 'doctype_id': 9102,
                                    'is_posted': True, 'posted_date': '2020-01-02', 'active': True}],
        'ab_accounting_je_line': [
            {'id': 9202, 'header_id': 9201, 'account_id': 9101, 'doc_no': 'TEST-001',
             'debit_val': 123.45, 'credit_val': 0.0, 'due_date': '2020-01-02', 'is_confirmed': True},
            {'id': 9203, 'header_id': 9201, 'account_id': 9101, 'doc_no': 'TEST-002',
             'debit_val': 0.0, 'credit_val': 123.45, 'due_date': '2020-01-02', 'is_confirmed': True}],
        'ir.attachment': [{'id': 9301, 'name': 'synthetic-evidence.txt', 'type': 'binary',
                           'res_model': 'ab_accounting_je_header', 'res_id': 9201, 'mimetype': 'text/plain'},
                          {'id': 9302, 'name': 'synthetic-avatar.png', 'type': 'binary',
                           'res_model': 'res.partner', 'res_id': 9010, 'res_field': 'image_1920', 'mimetype': 'image/png'}],
    }
    if source_defects:
        records['res.groups'].append({'id': 9505, 'name': 'All HR History'})
        records['res.groups'].append({'id': 9007})
        records['res.partner'].append({'id': 9009, 'name': 'Synthetic Bootstrap Administrator', 'active': True})
        records['res.users'].insert(0, {'id': 9008, 'login': 'admin', 'partner_id': 9009, 'company_id': 9001,
            'active': True, 'password': pw, 'enable_idle': True, 'idle_time': 10, '_m2m': {'company_ids': [9001]}})
        records.update({
            'ab_accounting_tracking': [{'id': 9501, 'je_line': 9999999, 'field_diff_json': '{}', 'update_counter': 1}],
            'ab_store': [{'id': 9502, 'name': 'Synthetic Inventory Branch', 'code': 'TEST-INV'}],
            'ab_inventory_header': [{'id': 9503, 'model_ref': 'ab_purchase_header', 'res_id': 9999999, 'header_ref': 'P9999999'}],
            'ab_inventory': [{'id': 9504, 'store_id': 9502, 'source_id': False, 'qty': 17,
                              'model_ref': 'ab_purchase_line', 'res_id': 9999998,
                              'header_id': 9503, 'header_ref': 'P9999999', 'status': 'saved'}],
        })
        records.update({
            'ab_uom_type': [{'id': 9511, 'name': 'Each'}],
            'ab_uom': [
                {'id': 9512, 'type_id': 9511, 'unit_no': 1, 'unit_size': 'large'},
                {'id': 9513, 'type_id': 9511, 'unit_no': 2, 'unit_size': 'medium'},
                {'id': 9514, 'type_id': 9511, 'unit_no': 3, 'unit_size': 'small'}],
            'ab_product_card': [{'id': 9515, 'name': 'Synthetic Product'}],
            'ab_product_tag': [{'id': 9516, 'name': '2 Each 3 Each', 'tag_type': 'unit', 'priority': 1}],
            'ab_product': [{'id': 9517, 'product_card_id': 9515, 'code': 'SYNTHETIC-PRODUCT',
                'name': 'Synthetic Product 2 Each 3 Each', 'unit_l_id': 9512, 'unit_m_id': 9513, 'unit_s_id': 9514,
                '_m2m': {'tag_ids': [9516]}}],
            'ab_taxes': [{'id': 9518, 'name': 'Synthetic No Tax', 'percentage': 0, 'apply_on_total': False}],
            'ab_product_source': [{'id': 9519, 'product_id': 9517, 'uom_id': 9512, 'qty': 17.0,
                'price': 9.0, 'purchase_price': 10.0, 'extra_discount_percentage': 0,
                'source_model': 'ab_purchase_line', '_m2m': {'taxes_ids': [9518]}}],
            'ab_supplier': [{'id': 9520, 'code': 'SYNTHETIC-SUPPLIER', 'name': 'Synthetic Supplier'}],
            'ab_purchase_header': [{'id': 9521, 'je_header_id': 9522, 'supplier_id': 9520, 'store_id': 9502,
                'doc_code': 'TEST/LEGACY', 'doc_date': '2020-01-02', 'status': 'saved', 'invoice_type': 'medical', 'eplus_serial': 123456789}],
            'ab_purchase_line': [{'id': 9523, 'header_id': 9521, 'source_id': 9519, 'eplus_serial': 123456790}],
        })
        records['ab_accounting_je_header'].append({'id': 9522, 'account_id': 9101, 'doctype_id': 9102,
            'is_posted': True, 'posted_date': '2020-01-02', 'active': True, 'res_header_ref': 'ab_purchase_header', 'res_header_id': 9521})
        records['ab_inventory'][0]['source_id'] = 9519
        records['ab_inventory_header'].append({'id': 9524, 'model_ref': 'ab_purchase_header', 'res_id': 9521, 'header_ref': 'P9521'})
        records['ab_inventory'].append({'id': 9525, 'store_id': 9502, 'source_id': 9519, 'qty': 6,
            'model_ref': 'ab_purchase_line', 'res_id': 9523, 'header_id': 9524, 'header_ref': 'P9521', 'status': 'saved'})
        records['ir.attachment'][0].update(store_fname='aa/unavailable-fixture-file', checksum='abc', file_size=123)
    db = sqlite3.connect(path)
    db.executescript('''
    CREATE TABLE records(model TEXT,source_id INTEGER,payload TEXT,PRIMARY KEY(model,source_id));
    CREATE TABLE xmlids(model TEXT,source_id INTEGER,xmlid TEXT UNIQUE);
    CREATE TABLE groups(user_id INTEGER,group_id INTEGER);
    CREATE TABLE attachments(source_id INTEGER,sha256 TEXT,size INTEGER);
    CREATE TABLE translations(model TEXT,source_id INTEGER,field TEXT,lang TEXT,value TEXT);
    ''')
    models = {}
    for model, rows in records.items():
        sm = schema[model]
        models[model] = {'table': sm['table'], 'modules': ['ab_accounting'], 'fields': {}}
        for fn, f in sm['fields'].items():
            models[model]['fields'][fn] = {'ttype': f['type'], 'relation': f['relation'],
                                           'translate': f['translate']}
        for row in rows:
            if model not in ('res.groups','res.users'):
                row.update(create_uid=9011, write_uid=9011,
                           create_date='2020-01-02 03:04:05', write_date='2020-01-03 04:05:06')
            db.execute('INSERT INTO records VALUES (?,?,?)', (model, row['id'], dumps(row)))
    db.executemany('INSERT INTO xmlids VALUES (?,?,?)', [
        ('res.company',9001,'base.main_company'), ('res.groups',9002,'base.group_user'),
        ('res.country',9003,'base.eg'), ('res.groups',9005,'outside_scope.group_role'), ('res.groups',9006,'base.group_private_addresses')])
    db.execute('INSERT INTO translations VALUES (?,?,?,?,?)', ('res.country',9003,'name','ar_001','مصر'))
    db.executemany('INSERT INTO groups VALUES (?,?)', [(9011,9002), (9011,9005), (9011,9006)])
    if source_defects:
        db.execute('INSERT INTO groups VALUES (?,?)', (9011,9505))
        db.executemany('INSERT INTO groups VALUES (?,?)', [(9008,9002), (9008,9007)])
        db.executemany('INSERT INTO xmlids VALUES (?,?,?)', [('res.users',9008,'base.user_admin'), ('res.partner',9009,'base.partner_admin'), ('res.groups',9007,'base.group_system')])
    blob = b'Synthetic evidence: accounting migration integration test.\n'
    private_dir(stage / 'blobs')
    (stage / 'blobs' / '9301').write_bytes(blob)
    db.execute('INSERT INTO attachments VALUES (?,?,?)', (9301, hashlib.sha256(blob).hexdigest(),len(blob)))
    avatar = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aL1sAAAAASUVORK5CYII=')
    (stage / 'blobs' / '9302').write_bytes(avatar)
    db.execute('INSERT INTO attachments VALUES (?,?,?)', (9302, hashlib.sha256(avatar).hexdigest(),len(avatar)))
    if source_defects:
        db.execute('DELETE FROM attachments WHERE source_id=9301')
        (stage / 'blobs' / '9301').unlink()
    db.commit(); db.close()
    save_json(stage / 'manifest.json', {'format_version': 1, 'source_db': marker['source'],
        'snapshot_id': str(uuid.uuid4()), 'frozen': False, 'sample_per_model': 1,
        'required_modules': ['base', 'ab_accounting', 'resource', 'auto_logout_idle_user_odoo'], 'synthetic': True, 'complete': not source_defects, 'blockers': [
            'Missing attachment file: ir.attachment:9301',
            'Missing/unsupported related record: ab_accounting_je_line:9999999',
            'Missing/unsupported related record: ab_purchase_line:9999998',
            'Missing/unsupported related record: ab_purchase_header:9999999',
        ] if source_defects else [], 'models': models,
        'roots': ['ab_accounting_je_header','ab_accounting_je_line'] + (['ab_product','ab_product_tag','ab_product_source','ab_purchase_header','ab_purchase_line','ab_inventory','ab_inventory_header'] if source_defects else []),
        'counts': {m: len(rows) for m,rows in records.items()}, 'records_sha256': digest(path)})
    print('Synthetic fixture prepared (no production data).')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('stage', type=Path)
    p.add_argument('--source-defects', action='store_true')
    args = p.parse_args()
    prepare(args.stage, args.source_defects)
