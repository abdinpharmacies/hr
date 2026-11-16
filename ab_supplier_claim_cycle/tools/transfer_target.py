"""Private offline ORM adapter; never imported by the addon or exposed over RPC."""
import base64
from collections import Counter
from decimal import Decimal
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

from claim_transfer import BANK, CASH, CLAIM, DEPARTMENTS, MODEL_TABLES, PREFIX, amount, legacy_runtime


def utc_datetime(value):
    if not value:
        return False
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


class Transfer:
    def __init__(self, env, bundle, args):
        self.env, self.bundle, self.args = env, bundle, args
        self.overrides = json.loads(Path(args.mappings).read_text()) if args.mappings else {}
        self.maps = {kind: {} for kind in ('users', 'partners', 'costcenters', 'companies', 'fields', 'subtypes')}
        self.ids = {}
        self.errors = []
        self.operations = 0
        self.round_amounts = getattr(args, 'amount_policy', 'strict') == 'round'
        self.rounding = []
        self.legacy = bundle.meta['module_version'].startswith('19.0.4.')
        self.marker = bundle.namespace + '.bundle_sha256'

    def claim_amount(self, row):
        return amount(row['amount_of_check'] if self.legacy else row['claim_amount'], self.round_amounts)

    def source_summary(self):
        return {key: value for key, value in self.bundle.meta.items() if key != 'origin'}

    def refname(self, table, source_id):
        return table + '__' + str(source_id)

    def reference(self, table, source_id):
        if not source_id:
            return False
        key = (table, source_id)
        if key not in self.ids:
            reference = self.env['ir.model.data'].search([
                ('module', '=', self.bundle.namespace), ('name', '=', self.refname(table, source_id))])
            if len(reference) != 1:
                raise ValueError('Missing source reference %s/%s' % key)
            self.ids[key] = reference.res_id
        return self.ids[key]

    def register(self, table, source_id, record):
        self.ids[(table, source_id)] = record.id
        self.env['ir.model.data'].create({'module': self.bundle.namespace,
            'name': self.refname(table, source_id), 'model': record._name,
            'res_id': record.id, 'noupdate': True})
        return record

    def mapped(self, kind, source_id):
        return self.maps[kind][source_id] if source_id else False

    def match(self, kind, row, model, domain, required=True):
        override = self.overrides.get(kind, {}).get(str(row['id']))
        if override is not None:
            # Overrides are target IDs, deliberately explicit and validated.
            records = self.env[model].browse(int(override)).exists()
        else:
            records = self.env[model].search(domain)
        if len(records) == 1:
            self.maps[kind][row['id']] = records.id
        elif required:
            self.errors.append('%s source %s: expected one match, found %s' % (kind, row['id'], len(records)))

    def preflight(self):
        if not self.bundle.rows(CLAIM):
            self.errors.append('Bundle has no claims; refusing empty replacement')
        if self.env['ir.module.module'].search([('name', '=', CLAIM), ('state', '=', 'installed')]).latest_version != '19.0.7.0.0':
            self.errors.append('Target must have dynamic supplier claim module 19.0.7.0.0 installed')
        if not self.env.ref(PREFIX + 'invoice_view_form_department_notes', raise_if_not_found=False):
            self.errors.append('Update the target module from current code first: department notes view is missing')
        if not self.legacy and not self.bundle.meta['module_version'].startswith('19.0.7.'):
            self.errors.append('Unsupported source module version')
        required_users = set()
        for table in self.bundle.tables.values():
            for row in table:
                for name in ('user_id', 'create_uid', 'write_uid'):
                    if row.get(name):
                        required_users.add(row[name])
        required_users.update(row['uid'] for row in self.bundle.rows('groups'))
        required_users.update(row['user_id'] for row in self.bundle.rows('ab_supplier_claim_stage_approver_rel'))
        users = self.bundle.rows('res_users')
        origin = self.bundle.meta.get('origin') or {}
        origin_target = (origin.get('database') == self.env.cr.dbname and
            origin.get('uuid') == self.env['ir.config_parameter'].get_param('database.uuid'))
        for row in users:
            login = origin.get('users', {}).get(str(row['id']), row['login']) if origin_target else row['login']
            self.match('users', row, 'res.users', [('login', '=', login)], row['id'] in required_users)
            if row['id'] in self.maps['users']:
                self.maps['partners'][row['partner_id']] = self.env['res.users'].browse(self.maps['users'][row['id']]).partner_id.id
        required_partners = {row['author_id'] for row in self.bundle.rows('mail_message') if row.get('author_id')}
        required_partners.update(row['res_partner_id'] for row in self.bundle.rows('mail_message_res_partner_rel'))
        for row in self.bundle.rows('res_partner'):
            if row['id'] not in self.maps['partners'] and row['id'] in required_partners:
                domain = [('email', '=ilike', row['email'])] if row.get('email') else [('ref', '=', row['ref'])] if row.get('ref') else [('id', '=', 0)]
                self.match('partners', row, 'res.partner', domain)
        for row in self.bundle.rows('ab_costcenter'):
            self.match('costcenters', row, 'ab_costcenter', [('code', '=', row['code'])])
        for row in self.bundle.rows('res_company'):
            self.match('companies', row, 'res.company', [('vat', '=', row['vat'])] if row.get('vat') else [('name', '=', row['name'])])
        if self.legacy and len(self.bundle.rows('res_company')) != 1:
            self.errors.append('Legacy claims lack company_id; source must have exactly one company')
        for row in self.bundle.rows('ir_model_fields'):
            name = 'claim_amount' if self.legacy and row['name'] == 'amount_of_check' else row['name']
            self.match('fields', row, 'ir.model.fields', [('model', '=', row['model']), ('name', '=', name)])
        for row in self.bundle.rows('subtypes'):
            record = self.env.ref(row['module'] + '.' + row['name'], raise_if_not_found=False)
            if record:
                self.maps['subtypes'][row['res_id']] = record.id
        for row in self.bundle.rows('mail_message'):
            if row.get('subtype_id') and row['subtype_id'] not in self.maps['subtypes']:
                self.errors.append('Missing subtype %s' % row['subtype_id'])
            if row.get('parent_id') and row['parent_id'] not in {r['id'] for r in self.bundle.rows('mail_message')}:
                self.errors.append('Message %s has parent outside exported claims' % row['id'])
        refs = []
        for row in self.bundle.rows(CLAIM):
            try:
                converted = self.claim_amount(row)
                original = str(row['amount_of_check'] if self.legacy else row['claim_amount'])
                difference = Decimal(str(converted)) - Decimal(original.replace(',', ''))
                if difference:
                    self.rounding.append({'source_id': row['id'], 'reference': row.get('claim_reference'),
                        'original': original, 'converted': str(converted), 'difference': str(difference)})
                if self.legacy:
                    legacy_runtime(row)
                if row.get('claim_reference'):
                    refs.append(row['claim_reference'].strip().upper())
            except (ValueError, KeyError) as exc:
                self.errors.append('Claim %s: %s' % (row['id'], exc))
        if len(set(refs)) != len(refs):
            self.errors.append('Claim references collide after normalization')
        if self.legacy:
            for department in (*DEPARTMENTS, 'user'):
                member_ids = [row['uid'] for row in self.bundle.rows('groups') if row['name'] == 'supplier_claim_group_' + department]
                active = [self.env['res.users'].browse(self.maps['users'][uid]) for uid in member_ids if uid in self.maps['users']]
                if not any(user.active and not user.share for user in active):
                    self.errors.append('No active internal approvers for ' + department)
        for model, table in MODEL_TABLES.items():
            for row in self.bundle.rows(table):
                for name, value in row.items():
                    field = self.env[model]._fields.get(name)
                    if not field or not value or field.type != 'selection' or self.legacy and model == CLAIM and name == 'state':
                        continue
                    if value not in dict(field._description_selection(self.env)):
                        self.errors.append('%s/%s: unsupported %s=%s' % (table, row['id'], name, value))
        return {'phase': 'preflight', 'source': self.source_summary(), 'errors': self.errors,
                'counts': self.bundle.manifest['counts'], 'target': self.env.cr.dbname,
                'rounding_adjustments': self.rounding,
                'mapped': {key: len(value) for key, value in self.maps.items()}}

    def raw_create(self, model, values):
        """Offline maintenance only: bypass business actions, keep core ORM checks."""
        from odoo import models
        record = models.Model.create(self.env[model], [values])
        self.checkpoint()
        return record

    def checkpoint(self):
        # Binary evidence can exceed a gigabyte; do not retain every file in cache.
        self.operations += 1
        if self.operations % 25 == 0:
            self.env.flush_all()
            self.env.invalidate_all()

    def values(self, model, row, exclude=()):
        result = {}
        fields = self.env[model]._fields
        for name, value in row.items():
            field = fields.get(name)
            if (name == 'id' or name in exclude or not field or not field.store
                    or field.compute or field.related or field.type in ('one2many', 'many2many')):
                continue
            if field.type == 'many2one':
                if name in ('create_uid', 'write_uid', 'user_id'):
                    result[name] = self.mapped('users', value)
                else:
                    continue
            elif field.type == 'datetime':
                result[name] = utc_datetime(value)
            else:
                if field.translate and isinstance(value, dict) and 'blob' not in value:
                    result[name] = value.get('en_US') or next(iter(value.values()))
                else:
                    result[name] = self.bundle.resolve(value)
        return result

    def message_body(self, value):
        if not value:
            return value
        def document(match):
            return match[1] + str(self.reference('ab_supplier_claim_document', int(match[2]))) + match[3]
        value = re.sub(r'(/web/content/ab_supplier_claim_document/)(\d+)(/content)', document, value)
        attachment_ids = {r['id'] for r in self.bundle.rows('ir_attachment')}
        def attachment(match):
            old = int(match[2])
            return match[1] + str(self.reference('ir_attachment', old) if old in attachment_ids else old)
        return re.sub(r'(/web/(?:content|image)/)(\d+)', attachment, value)

    def cleanup(self):
        """Targeted SQL maintenance: module intentionally forbids audit deletion."""
        env = self.env
        claims = env[CLAIM].search([])
        messages = env['mail.message'].search([('model', '=', CLAIM), ('res_id', 'in', claims.ids)])
        # Unlink messages using mail's cleanup once immutable audit links are cleared.
        env.cr.execute('UPDATE mail_message SET supplier_claim_history_id=NULL, supplier_claim_document_id=NULL WHERE id=ANY(%s)', (messages.ids,))
        env.invalidate_all()
        attachments = env['ir.attachment'].search([('res_model', '=', CLAIM), ('res_id', 'in', claims.ids)])
        messages.unlink()
        attachments.unlink()
        env['mail.followers'].search([('res_model', '=', CLAIM), ('res_id', 'in', claims.ids)]).unlink()
        env['mail.activity'].search([('res_model', '=', CLAIM), ('res_id', 'in', claims.ids)]).unlink()
        env.flush_all()
        env.cr.execute('UPDATE ab_supplier_claim_cycle SET rejection_stage_state_id=NULL WHERE id=ANY(%s)', (claims.ids,))
        for table in ('ab_supplier_claim_cycle_history', 'ab_supplier_claim_document', 'ab_supplier_claim_stage_state'):
            from odoo.tools import SQL
            env.cr.execute(SQL('DELETE FROM %s WHERE claim_id = ANY(%s)', SQL.identifier(table), claims.ids))
        env.cr.execute('DELETE FROM ab_supplier_claim_cycle WHERE id=ANY(%s)', (claims.ids,))
        env.cr.execute('DELETE FROM ab_supplier_claim_workflow_stage')
        env.cr.execute('DELETE FROM ab_supplier_claim_workflow')
        env['ir.model.data'].search([('module', '=like', 'claim_transfer_%')]).filtered(
            lambda row: row.module.startswith('claim_transfer_')).unlink()
        env['ir.config_parameter'].search([('key', '=like', 'claim_transfer_%')]).filtered(
            lambda row: row.key.startswith('claim_transfer_')).unlink()
        env.invalidate_all()

    def roles(self):
        for row in self.bundle.rows('groups'):
            group = self.env.ref(PREFIX + row['name'], raise_if_not_found=False)
            if group:
                self.env['res.users'].browse(self.mapped('users', row['uid'])).write({'group_ids': [(4, group.id)]})

    def workflows(self):
        from odoo import Command
        self.stages = {}
        if self.legacy:
            for key, route, domain in (
                    ('cash', CASH, "[('payment_nature', '=', 'cash')]"),
                    ('bank', BANK, "[('payment_nature', 'in', ['check', 'bank_transfer'])]")):
                lines = []
                for seq, department in enumerate(route, 1):
                    role = 'user' if department == 'secretarial' else department
                    user_ids = [self.mapped('users', r['uid']) for r in self.bundle.rows('groups')
                                if r['name'] == 'supplier_claim_group_' + role]
                    users = self.env['res.users'].browse(user_ids).filtered(lambda u: u.active and not u.share)
                    users.write({'group_ids': [Command.link(self.env.ref(PREFIX + 'supplier_claim_group_participant').id)]})
                    names = ['secretarial_notes', 'supplier_cheque_attachment', 'attachment'] if department == 'secretarial' else [department + '_notes', department + '_followup_date']
                    if department == 'supplier_accounts':
                        names += ['supplier_cheque_attachment']
                    elif department == 'bank_accounts':
                        names += ['bank_cheque_attachment']
                    fields = self.env['ir.model.fields'].search([('model', '=', CLAIM), ('name', 'in', names)])
                    lines.append(Command.create({'name': 'Secretarial Closure' if department == 'secretarial' else department.replace('_', ' ').title(),
                                 'sequence': seq * 10, 'approver_ids': [Command.set(users.ids)], 'allowed_field_ids': [Command.set(fields.ids)]}))
                workflow = self.env['ab_supplier_claim_workflow'].create({'name': 'Legacy Compatible ' + key.title(),
                    'claim_domain': domain, 'priority': 10, 'workflow_stage_ids': lines})
                workflow.action_publish()
                self.register('legacy_workflow', key, workflow)
                self.stages[key] = dict(zip(route, workflow.workflow_stage_ids.sorted('sequence')))
        else:
            for row in self.bundle.rows('ab_supplier_claim_workflow'):
                record = self.raw_create('ab_supplier_claim_workflow', self.values('ab_supplier_claim_workflow', row))
                self.register('ab_supplier_claim_workflow', row['id'], record)
            for row in self.bundle.rows('ab_supplier_claim_workflow_stage'):
                values = self.values('ab_supplier_claim_workflow_stage', row)
                values['workflow_id'] = self.reference('ab_supplier_claim_workflow', row['workflow_id'])
                values['approver_ids'] = [Command.set([self.mapped('users', r['user_id']) for r in self.bundle.rows('ab_supplier_claim_stage_approver_rel') if r['stage_id'] == row['id']])]
                values['allowed_field_ids'] = [Command.set([self.mapped('fields', r['field_id']) for r in self.bundle.rows('ab_supplier_claim_stage_allowed_field_rel') if r['stage_id'] == row['id']])]
                record = self.raw_create('ab_supplier_claim_workflow_stage', values)
                record._validate_for_publication()
                self.register('ab_supplier_claim_workflow_stage', row['id'], record)

    def claims(self):
        for row in self.bundle.rows(CLAIM):
            values = self.values(CLAIM, row, ('state', 'claim_amount', 'current_sequence'))
            values['supplier_id'] = self.mapped('costcenters', row['supplier_id'])
            values['company_id'] = (self.mapped('companies', row['company_id']) if row.get('company_id') else self.mapped('companies', self.bundle.rows('res_company')[0]['id']))
            values['claim_amount'] = self.claim_amount(row)
            values['claim_reference'] = (row.get('claim_reference') or '').strip().upper() or False
            if self.legacy:
                if row.get('cheque_attachment'):
                    values['supplier_cheque_attachment'] = self.bundle.resolve(row['cheque_attachment'])
                    values['supplier_cheque_filename'] = row.get('cheque_filename') or False
                route, state, current, statuses = legacy_runtime(row)
                key = 'cash' if route == CASH else 'bank'
                values.update(state=state, current_sequence=0 if state in ('draft', 'closed') else self.stages[key][current].sequence)
                if row.get('payment_nature'):
                    values['workflow_id'] = self.reference('legacy_workflow', key)
                values['document_revision'] = 1
            else:
                values.update(state=row['state'], current_sequence=row['current_sequence'],
                              workflow_id=self.reference('ab_supplier_claim_workflow', row.get('workflow_id')))
            record = self.raw_create(CLAIM, values)
            self.register(CLAIM, row['id'], record)
            if self.legacy and state != 'draft':
                for department in route:
                    status = statuses[department]
                    events = [r for r in self.bundle.rows('ab_supplier_claim_cycle_history') if r['claim_id'] == row['id'] and (r.get('department') == department or department == 'secretarial' and r['event'] == 'closed')]
                    matching = [r for r in events if (r.get('decision') == status or department == 'secretarial' and r['event'] == 'closed')]
                    event = max(matching, key=lambda r: r['id']) if matching else None
                    stage_values = {'claim_id': record.id, 'stage_id': self.stages[key][department].id, 'status': status,
                        'user_id': self.mapped('users', event['user_id']) if event else False,
                        'decision_at': utc_datetime(event['occurred_at']) if event else False,
                        'reason': (event.get('reason') if event else row.get('rejection_reason') if status == 'rejected' else False) or False,
                        'followup_date': row.get(department + '_followup_date') if status == 'deferred' else False}
                    if status == 'approved' and not event:
                        stage_values['reason'] = 'Imported completion from legacy state/decision; original decision event unavailable.'
                    stage = self.raw_create('ab_supplier_claim_stage_state', stage_values)
                    self.register('legacy_stage_' + department, row['id'], stage)
                    if status == 'rejected':
                        record._workflow_write({'rejection_stage_state_id': stage.id})
        if not self.legacy:
            for row in self.bundle.rows('ab_supplier_claim_stage_state'):
                values = self.values('ab_supplier_claim_stage_state', row)
                values.update(claim_id=self.reference(CLAIM, row['claim_id']), stage_id=self.reference('ab_supplier_claim_workflow_stage', row['stage_id']))
                self.register('ab_supplier_claim_stage_state', row['id'], self.raw_create('ab_supplier_claim_stage_state', values))
            for row in self.bundle.rows(CLAIM):
                if row.get('rejection_stage_state_id'):
                    self.env[CLAIM].browse(self.reference(CLAIM, row['id']))._workflow_write({'rejection_stage_state_id': self.reference('ab_supplier_claim_stage_state', row['rejection_stage_state_id'])})

    def history_documents(self):
        for model in ('ab_supplier_claim_cycle.history', 'ab_supplier_claim_document'):
            table = MODEL_TABLES[model]
            for row in self.bundle.rows(table):
                values = self.values(model, row)
                values['claim_id'] = self.reference(CLAIM, row['claim_id'])
                if row.get('stage_state_id'):
                    values['stage_state_id'] = self.reference('ab_supplier_claim_stage_state', row['stage_state_id'])
                self.register(table, row['id'], self.raw_create(model, values))
        if self.legacy:
            for row in self.bundle.rows(CLAIM):
                for old, kind, filename in (('attachment', 'attachment', None), ('cheque_attachment', 'supplier_cheque', 'cheque_filename'), ('bank_cheque_attachment', 'bank_cheque', 'bank_cheque_filename')):
                    if row.get(old):
                        # Source has only current inline documents, no revision evidence.
                        values = {'claim_id': self.reference(CLAIM, row['id']), 'kind': kind,
                            'content': self.bundle.resolve(row[old]), 'filename': row.get(filename) if filename else 'legacy-attachment',
                            'revision': 1, 'reason': 'Legacy current document imported; original upload time unavailable',
                            'user_id': self.mapped('users', row.get('write_uid') or row['create_uid']),
                            'occurred_at': datetime.now(timezone.utc).replace(tzinfo=None)}
                        record = self.raw_create('ab_supplier_claim_document', values)
                        self.register('legacy_document_' + kind, row['id'], record)
        for adjustment in self.rounding:
            row = next(r for r in self.bundle.rows(CLAIM) if r['id'] == adjustment['source_id'])
            entry = self.raw_create('ab_supplier_claim_cycle.history', {
                'claim_id': self.reference(CLAIM, row['id']), 'event': 'migration_exception',
                'review_round': row['review_round'], 'user_id': self.env.uid,
                'occurred_at': datetime.now(timezone.utc).replace(tzinfo=None),
                'reason': 'Migration rounded original legacy amount %s to %s using decimal HALF_UP; difference %s.' % (
                    adjustment['original'], adjustment['converted'], adjustment['difference'])})
            self.register('migration_amount_note', row['id'], entry)

    def messages_attachments(self):
        from odoo import Command, models
        for row in self.bundle.rows('ir_attachment'):
            values = self.values('ir.attachment', row, ('access_token', 'store_fname', 'checksum', 'file_size', 'index_content', 'public'))
            values['res_model'] = CLAIM
            # A chatter-only attachment may have an unrelated/zero res_id.
            linked = [r['message_id'] for r in self.bundle.rows('message_attachment_rel') if r['attachment_id'] == row['id']]
            source_claim = row['res_id'] if row.get('res_model') == CLAIM else next((m['res_id'] for m in self.bundle.rows('mail_message') if m['id'] in linked), None)
            if source_claim is None:
                raise ValueError('Attachment has no exported claim')
            values['res_id'] = self.reference(CLAIM, source_claim)
            values['company_id'] = self.mapped('companies', row.get('company_id'))
            if row['type'] == 'binary':
                values['raw'] = self.bundle.blob(row['_raw'])
            record = self.env['ir.attachment'].create(values)
            self.register('ir_attachment', row['id'], record)
            self.checkpoint()
        for row in self.bundle.rows('mail_message'):
            values = self.values('mail.message', row, ('parent_id',))
            if 'body' in values:
                values['body'] = self.message_body(values['body'])
            values.update(model=CLAIM, res_id=self.reference(CLAIM, row['res_id']),
                          author_id=self.mapped('partners', row.get('author_id')),
                          subtype_id=self.mapped('subtypes', row.get('subtype_id')))
            values['attachment_ids'] = [Command.set([self.reference('ir_attachment', r['attachment_id']) for r in self.bundle.rows('message_attachment_rel') if r['message_id'] == row['id']])]
            values['partner_ids'] = [Command.set([self.mapped('partners', r['res_partner_id']) for r in self.bundle.rows('mail_message_res_partner_rel') if r['mail_message_id'] == row['id']])]
            for field, table in (('supplier_claim_history_id', 'ab_supplier_claim_cycle_history'), ('supplier_claim_document_id', 'ab_supplier_claim_document')):
                if row.get(field):
                    values[field] = self.reference(table, row[field])
            self.register('mail_message', row['id'], self.raw_create('mail.message', values))
        for row in self.bundle.rows('mail_message'):
            if row.get('parent_id'):
                models.Model.write(self.env['mail.message'].browse(self.reference('mail_message', row['id'])), {'parent_id': self.reference('mail_message', row['parent_id'])})
        for row in self.bundle.rows('mail_tracking_value'):
            values = self.values('mail.tracking.value', row)
            values['mail_message_id'] = self.reference('mail_message', row['mail_message_id'])
            values['field_id'] = self.mapped('fields', row.get('field_id'))
            self.register('mail_tracking_value', row['id'], self.raw_create('mail.tracking.value', values))
        # Legacy source did not have audit-linked chatter. Generate only missing links.
        for model, table in (('ab_supplier_claim_cycle.history', 'ab_supplier_claim_cycle_history'), ('ab_supplier_claim_document', 'ab_supplier_claim_document')):
            refs = self.env['ir.model.data'].search([('module', '=', self.bundle.namespace), ('model', '=', model)])
            self.env[model].browse(refs.mapped('res_id'))._sync_claim_chatter()

    def run(self):
        self.env.cr.execute('LOCK TABLE ab_supplier_claim_cycle IN ACCESS EXCLUSIVE MODE')
        existing = self.env['ir.config_parameter'].get_param(self.marker)
        replace_source = getattr(self.args, 'replace_source_snapshot', False)
        if replace_source and not self.args.replace_claims:
            raise ValueError('--replace-source-snapshot requires --replace-claims')
        if existing:
            if replace_source:
                self.cleanup()
            elif existing != self.bundle.manifest['data_sha256']:
                raise ValueError('Different bundle for existing source; resolve explicitly before reimport')
            else:
                return {**self.verify(), 'unchanged': True}
        if self.env[CLAIM].search_count([]) or self.env['ab_supplier_claim_workflow'].search_count([]):
            if not self.args.replace_claims:
                raise ValueError('Target is not clean; --replace-claims is required')
            self.cleanup()
        print('Import phase: roles and workflows', file=sys.stderr, flush=True)
        self.roles()
        self.workflows()
        print('Import phase: claims and stage states', file=sys.stderr, flush=True)
        self.claims()
        print('Import phase: history and document snapshots', file=sys.stderr, flush=True)
        self.history_documents()
        print('Import phase: attachments and chatter', file=sys.stderr, flush=True)
        self.messages_attachments()
        print('Import phase: original timestamps and reconciliation', file=sys.stderr, flush=True)
        self.restore_log_access()
        self.env.flush_all()
        self.env['ir.config_parameter'].set_param(self.marker, self.bundle.manifest['data_sha256'])
        origin = self.bundle.meta.get('origin') or {}
        users = {str(self.maps['users'][row['id']]):
                 origin.get('users', {}).get(str(row['id']), row['login'])
                 for row in self.bundle.rows('res_users') if row['id'] in self.maps['users']}
        self.env['ir.config_parameter'].set_param(self.bundle.namespace + '.identities', json.dumps({
            'database': origin.get('database', self.bundle.meta['database']),
            'uuid': origin.get('uuid', self.bundle.meta['uuid']), 'users': users,
            'groups': [{'name': row['name'], 'uid': self.mapped('users', row['uid'])}
                       for row in self.bundle.rows('groups')]}))
        return self.verify()

    def restore_log_access(self):
        # Odoo 19 deliberately discards supplied log-access values in create/write.
        # This offline, target-only SQL restores evidence after all ORM operations.
        from odoo.tools import SQL
        from psycopg2.extras import Json
        self.env.flush_all()
        for model, table in MODEL_TABLES.items():
            for row in self.bundle.rows(table):
                values = {name: (self.mapped('users', row[name]) if name.endswith('_uid') else row[name])
                          for name in ('create_uid', 'write_uid', 'create_date', 'write_date')
                          if row.get(name) is not None}
                values.update({name: Json(value) for name, value in row.items()
                               if name in self.env[model]._fields
                               and self.env[model]._fields[name].translate and isinstance(value, dict)})
                if values:
                    assignments = SQL(', ').join(SQL('%s = %s', SQL.identifier(name), value)
                                                 for name, value in values.items())
                    self.env.cr.execute(SQL('UPDATE %s SET %s WHERE id = %s',
                        SQL.identifier(table), assignments, self.reference(table, row['id'])))
        self.env.invalidate_all()

    def verify(self):
        failures = []
        totals = Decimal('0')
        source_states = Counter()
        for row in self.bundle.rows(CLAIM):
            record = self.env[CLAIM].browse(self.reference(CLAIM, row['id'])).exists()
            expected = self.claim_amount(row)
            state = legacy_runtime(row)[1] if self.legacy else row['state']
            if not record or record.state != state or record.active != row['active'] or record.claim_amount != expected:
                failures.append('Claim values differ: %s' % row['id'])
                continue
            if record.supplier_id.id != self.mapped('costcenters', row['supplier_id']) or record.user_id.id != self.mapped('users', row.get('user_id')):
                failures.append('Claim relationships differ: %s' % row['id'])
            self.compare_values(record, self.values(CLAIM, row, ('state', 'claim_amount', 'current_sequence')), failures, CLAIM, row['id'])
            for old, new in (('attachment', 'attachment'), ('cheque_attachment' if self.legacy else 'supplier_cheque_attachment', 'supplier_cheque_attachment'), ('bank_cheque_attachment', 'bank_cheque_attachment'), ('tax_review_attachment', 'tax_review_attachment'), ('payment_request_attachment', 'payment_request_attachment')):
                if row.get(old) and record[new] != self.bundle.resolve(row[old]):
                    failures.append('Claim binary differs: %s/%s' % (row['id'], old))
            if self.legacy:
                route, _, current, statuses = legacy_runtime(row)
                actual = {key: self.env['ab_supplier_claim_stage_state'].browse(self.reference('legacy_stage_' + key, row['id'])).status for key in statuses}
                if actual != statuses:
                    failures.append('Stage statuses differ: %s' % row['id'])
                expected_sequence = 0 if state in ('draft', 'closed') else (route.index(current) + 1) * 10
                if record.current_sequence != expected_sequence:
                    failures.append('Current sequence differs: %s' % row['id'])
            elif record.current_sequence != row['current_sequence']:
                failures.append('Current sequence differs: %s' % row['id'])
            source_states[row['state']] += 1
            totals += Decimal(str(expected))
            self.checkpoint()
        checked = Counter()
        for model, table in MODEL_TABLES.items():
            if model == CLAIM:
                continue
            for row in self.bundle.rows(table):
                record = self.env[model].browse(self.reference(table, row['id'])).exists()
                if not record:
                    failures.append('Missing %s/%s' % (table, row['id']))
                    continue
                checked[table] += 1
                if model == 'ir.attachment':
                    if row['type'] == 'binary' and hashlib.sha256(record.raw or b'').hexdigest() != row['_raw']['blob']:
                        failures.append('Attachment bytes differ: %s' % row['id'])
                values = self.values(model, row, ('state', 'claim_amount', 'current_sequence') if model == CLAIM else ())
                if model == 'ir.attachment':
                    for name in ('access_token', 'store_fname', 'checksum', 'file_size', 'index_content', 'public', 'res_model', 'res_id'):
                        values.pop(name, None)
                if model == 'mail.message':
                    values['res_id'] = self.reference(CLAIM, row['res_id'])
                    values['body'] = self.message_body(values.get('body'))
                    expected_attachments = {self.reference('ir_attachment', r['attachment_id']) for r in self.bundle.rows('message_attachment_rel') if r['message_id'] == row['id']}
                    if set(record.attachment_ids.ids) != expected_attachments:
                        failures.append('Message attachments differ: %s' % row['id'])
                relations = {
                    'ab_supplier_claim_cycle.history': {'claim_id': (CLAIM, 'claim_id'), 'stage_state_id': ('ab_supplier_claim_stage_state', 'stage_state_id')},
                    'ab_supplier_claim_document': {'claim_id': (CLAIM, 'claim_id')},
                    'ab_supplier_claim_stage_state': {'claim_id': (CLAIM, 'claim_id'), 'stage_id': ('ab_supplier_claim_workflow_stage', 'stage_id')},
                    'ab_supplier_claim_workflow_stage': {'workflow_id': ('ab_supplier_claim_workflow', 'workflow_id')},
                    'mail.message': {'parent_id': ('mail_message', 'parent_id'),
                        'supplier_claim_history_id': ('ab_supplier_claim_cycle_history', 'supplier_claim_history_id'),
                        'supplier_claim_document_id': ('ab_supplier_claim_document', 'supplier_claim_document_id')},
                    'mail.tracking.value': {'mail_message_id': ('mail_message', 'mail_message_id')},
                }.get(model, {})
                values.update({name: self.reference(target_table, row.get(source_field))
                               for name, (target_table, source_field) in relations.items() if source_field in row})
                if model == 'mail.message':
                    values.update(author_id=self.mapped('partners', row.get('author_id')), subtype_id=self.mapped('subtypes', row.get('subtype_id')))
                if model == 'mail.tracking.value':
                    values['field_id'] = self.mapped('fields', row.get('field_id'))
                if model == 'ab_supplier_claim_workflow_stage':
                    for relation, map_kind, records in (('approver_ids', 'users', 'ab_supplier_claim_stage_approver_rel'), ('allowed_field_ids', 'fields', 'ab_supplier_claim_stage_allowed_field_rel')):
                        key = 'user_id' if map_kind == 'users' else 'field_id'
                        expected = {self.mapped(map_kind, r[key]) for r in self.bundle.rows(records) if r['stage_id'] == row['id']}
                        if set(record[relation].ids) != expected:
                            failures.append('Stage configuration differs: %s/%s' % (row['id'], relation))
                self.compare_values(record, values, failures, table, row['id'])
                self.checkpoint()
        report = {'phase': 'verification', 'target': self.env.cr.dbname, 'source': self.source_summary(),
                  'claims': len(self.bundle.rows(CLAIM)), 'source_states': dict(source_states),
                  'claim_amount_total': str(totals), 'checked': dict(checked), 'errors': failures}
        report['rounding_adjustments'] = self.rounding
        report['rounding_difference_total'] = str(sum((Decimal(r['difference']) for r in self.rounding), Decimal('0')))
        claim_ids = [self.reference(CLAIM, row['id']) for row in self.bundle.rows(CLAIM)]
        counts = {model: self.env[model].search_count([('claim_id', 'in', claim_ids)])
                  for model in ('ab_supplier_claim_cycle.history', 'ab_supplier_claim_document', 'ab_supplier_claim_stage_state')}
        counts['mail.message'] = self.env['mail.message'].search_count([('model', '=', CLAIM), ('res_id', 'in', claim_ids)])
        counts['ir.attachment'] = self.env['ir.attachment'].search_count([('res_model', '=', CLAIM), ('res_id', 'in', claim_ids)])
        expected_history = len(self.bundle.rows('ab_supplier_claim_cycle_history')) + len(self.rounding)
        expected_documents = len(self.bundle.rows('ab_supplier_claim_document'))
        expected_stages = len(self.bundle.rows('ab_supplier_claim_stage_state'))
        if self.legacy:
            expected_documents += sum(bool(row.get(name)) for row in self.bundle.rows(CLAIM)
                                      for name in ('attachment', 'cheque_attachment', 'bank_cheque_attachment'))
            expected_stages += sum(len(legacy_runtime(row)[0]) for row in self.bundle.rows(CLAIM) if row['state'] != 'draft')
        linked = sum(bool(row.get(name)) for row in self.bundle.rows('mail_message')
                     for name in ('supplier_claim_history_id', 'supplier_claim_document_id'))
        expected_counts = {'ab_supplier_claim_cycle.history': expected_history,
            'ab_supplier_claim_document': expected_documents, 'ab_supplier_claim_stage_state': expected_stages,
            'mail.message': len(self.bundle.rows('mail_message')) + expected_history + expected_documents - linked,
            'ir.attachment': len(self.bundle.rows('ir_attachment'))}
        if counts != expected_counts:
            failures.append('Aggregate target counts differ: expected %s, actual %s' % (expected_counts, counts))
        report['target_counts'] = counts
        if failures:
            raise ValueError('Verification failed: ' + json.dumps(failures[:30]))
        return report

    def compare_values(self, record, values, failures, table, source_id):
        for name, expected in values.items():
            actual = record[name]
            field = record._fields[name]
            if field.type == 'many2one':
                actual = actual.id or False
            elif field.type in ('date', 'datetime', 'html'):
                actual = str(actual) if actual else False
                expected = str(expected) if expected else False
            if actual != expected and not (not actual and not expected):
                failures.append('%s/%s/%s differs' % (table, source_id, name))
