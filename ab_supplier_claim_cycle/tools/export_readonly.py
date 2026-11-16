"""Read-only SQL/filestore exporter. May be streamed to python over SSH stdin.

No Odoo registry is opened and no file is written on the source host.
"""
import base64
import configparser
import datetime
import decimal
import hashlib
import json
import os
import sys

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor


def encode(value):
    if isinstance(value, memoryview):
        return {'$binary': base64.b64encode(value).decode()}
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat(sep=' ') if isinstance(value, datetime.datetime) else value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    raise TypeError(type(value).__name__)


def emit(table, row):
    print(json.dumps({'table': table, 'row': row}, default=encode, ensure_ascii=False), flush=True)


def main():
    config_path, database, filestore = sys.argv[1:4]
    config = configparser.ConfigParser(interpolation=None)
    config.read(config_path)
    opts = config['options']
    kwargs = {'dbname': database, 'application_name': 'supplier_claim_READ_ONLY_export'}
    for field in ('host', 'port', 'user', 'password'):
        value = opts.get('db_' + field)
        if value and value.lower() not in ('false', 'none'):
            kwargs[field] = value
    conn = psycopg2.connect(**kwargs)
    conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
    cur = conn.cursor(cursor_factory=RealDictCursor)

    def query(query_text, args=()):
        cur.execute(query_text, args)
        return [dict(row) for row in cur.fetchall()]

    def exists(table):
        return bool(query('SELECT to_regclass(%s) AS present', (table,))[0]['present'])

    def rows(table, condition=sql.SQL('TRUE'), args=()):
        if not exists(table):
            return []
        return query(sql.SQL('SELECT * FROM {} WHERE {} ORDER BY id').format(
            sql.Identifier(table), condition), args)

    uuid = query("SELECT value FROM ir_config_parameter WHERE key='database.uuid'")[0]['value']
    version = query("SELECT latest_version FROM ir_module_module WHERE name='ab_supplier_claim_cycle'")[0]['latest_version']
    namespace = sys.argv[4] if len(sys.argv) > 4 else None
    provenance = query('SELECT value FROM ir_config_parameter WHERE key=%s', (namespace + '.identities',)) if namespace else []
    origin = json.loads(provenance[0]['value']) if provenance else None
    emit('meta', {'format': 1, 'database': database, 'uuid': uuid,
                  'module_version': version, 'snapshot': query('SELECT transaction_timestamp() AS t')[0]['t'],
                  'origin': origin,
                  'read_only': query('SHOW transaction_read_only')[0]['transaction_read_only']})
    if namespace:
        claims = rows('ab_supplier_claim_cycle', sql.SQL(
            "id IN (SELECT res_id FROM ir_model_data WHERE module=%s AND model='ab_supplier_claim_cycle')"), (namespace,))
    else:
        claims = rows('ab_supplier_claim_cycle')
    if not claims:
        raise ValueError('No claims selected; refusing an empty migration bundle')
    ids = [r['id'] for r in claims]
    exported = {}
    exported['ab_supplier_claim_cycle'] = claims
    for table in ('ab_supplier_claim_cycle_history', 'ab_supplier_claim_document', 'ab_supplier_claim_stage_state'):
        exported[table] = rows(table, sql.SQL('claim_id = ANY(%s)'), (ids,))
    workflow_ids = list({r['workflow_id'] for r in claims if r.get('workflow_id')})
    if namespace:
        workflow_ids = list(set(workflow_ids) | {r['res_id'] for r in query(
            "SELECT res_id FROM ir_model_data WHERE module=%s AND model='ab_supplier_claim_workflow'", (namespace,))})
    exported['ab_supplier_claim_workflow'] = rows('ab_supplier_claim_workflow', sql.SQL('id = ANY(%s)'), (workflow_ids,))
    exported['ab_supplier_claim_workflow_stage'] = rows('ab_supplier_claim_workflow_stage', sql.SQL('workflow_id = ANY(%s)'), (workflow_ids,))
    stage_ids = [r['id'] for r in exported['ab_supplier_claim_workflow_stage']]
    for table in ('ab_supplier_claim_stage_approver_rel', 'ab_supplier_claim_stage_allowed_field_rel'):
        if exists(table):
            exported[table] = query(sql.SQL('SELECT * FROM {} WHERE stage_id = ANY(%s)').format(sql.Identifier(table)), (stage_ids,))
    exported['mail_message'] = rows('mail_message', sql.SQL("model = 'ab_supplier_claim_cycle' AND res_id = ANY(%s)"), (ids,))
    message_ids = [r['id'] for r in exported['mail_message']]
    exported['mail_tracking_value'] = rows('mail_tracking_value', sql.SQL('mail_message_id = ANY(%s)'), (message_ids,))
    for table, col in (('message_attachment_rel', 'message_id'), ('mail_message_res_partner_rel', 'mail_message_id')):
        exported[table] = query(sql.SQL('SELECT * FROM {} WHERE {} = ANY(%s)').format(sql.Identifier(table), sql.Identifier(col)), (message_ids,))
    attachment_ids = [r['attachment_id'] for r in exported['message_attachment_rel']]
    exported['ir_attachment'] = rows('ir_attachment', sql.SQL(
        "(res_model = 'ab_supplier_claim_cycle' AND res_id = ANY(%s)) OR id = ANY(%s)"), (ids, attachment_ids))
    exported['ab_costcenter'] = query('SELECT id,code,name,active FROM ab_costcenter WHERE id = ANY(%s)', (list({r['supplier_id'] for r in claims}),))
    exported['res_users'] = query('SELECT id,login,partner_id,active,share FROM res_users ORDER BY id')
    exported['res_company'] = query('SELECT c.id,c.name,p.vat FROM res_company c JOIN res_partner p ON p.id=c.partner_id ORDER BY c.id')
    exported['groups'] = query("""SELECT d.name,r.uid FROM ir_model_data d
        JOIN res_groups_users_rel r ON r.gid=d.res_id
        WHERE d.module='ab_supplier_claim_cycle' AND d.model='res.groups' ORDER BY d.name,r.uid""")
    if namespace and origin:
        relevant = {r['uid'] for r in origin.get('groups', [])}
        relevant.update(r['user_id'] for r in exported.get('ab_supplier_claim_stage_approver_rel', []))
        exported['groups'] = [r for r in exported['groups'] if r['uid'] in relevant]
    partner_ids = {r['partner_id'] for r in exported['res_users']}
    partner_ids.update(r['author_id'] for r in exported['mail_message'] if r.get('author_id'))
    partner_ids.update(r['res_partner_id'] for r in exported['mail_message_res_partner_rel'])
    exported['res_partner'] = query('SELECT id,name,email,ref FROM res_partner WHERE id = ANY(%s)', (list(partner_ids),))
    field_ids = {r['field_id'] for r in exported['mail_tracking_value'] if r.get('field_id')}
    field_ids.update(r['field_id'] for r in exported.get('ab_supplier_claim_stage_allowed_field_rel', []))
    exported['ir_model_fields'] = query('SELECT id,model,name,ttype FROM ir_model_fields WHERE id = ANY(%s)', (list(field_ids),))
    subtype_ids = list({r['subtype_id'] for r in exported['mail_message'] if r.get('subtype_id')})
    exported['subtypes'] = query("SELECT res_id,module,name FROM ir_model_data WHERE model='mail.message.subtype' AND res_id = ANY(%s)", (subtype_ids,))
    for table, records in exported.items():
        for row in records:
            if table == 'ir_attachment':
                if row.get('store_fname'):
                    root = os.path.realpath(os.path.join(filestore, database))
                    path = os.path.realpath(os.path.join(root, row['store_fname']))
                    if not path.startswith(root + os.sep):
                        raise ValueError('Unsafe attachment path')
                    with open(path, 'rb') as stream:
                        content = stream.read()
                else:
                    content = bytes(row.get('db_datas') or b'')
                if row['type'] == 'binary':
                    if row.get('checksum') and hashlib.sha1(content).hexdigest() != row['checksum']:
                        raise ValueError('Attachment checksum mismatch: %s' % row['id'])
                    row['_raw'] = memoryview(content)
                row.pop('db_datas', None)
            emit(table, row)
    emit('end', {'counts': {table: len(records) for table, records in exported.items()}})
    conn.rollback()
    conn.close()


if __name__ == '__main__':
    main()
