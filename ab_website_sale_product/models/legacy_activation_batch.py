import csv
import hashlib
import io
import json
import re
import secrets
import shutil
import tempfile
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from ..services.legacy_activation import LegacyCodeSecurity
from ..services.legacy_csv import CORRECTED_CODES, INFO_CODES, csv_events, customer_event, issue


class ActivationBatch(models.Model):
    _name = 'ab_ecommerce_legacy_batch'
    _description = 'Legacy Customer Activation Batch'
    _order = 'id desc'

    name = fields.Char(required=True, default=lambda self: _('Legacy customer activation'))
    website_id = fields.Many2one('website', required=True, default=lambda self: self.env['website'].search([('company_id', 'in', self.env.companies.ids)], limit=1))
    company_id = fields.Many2one(related='website_id.company_id', store=True, index=True)
    owner_id = fields.Many2one('res.users', required=True, readonly=True, default=lambda self: self.env.user)
    source_namespace = fields.Char(required=True, default='eplus')
    source_file = fields.Binary(attachment=True)
    source_filename = fields.Char()
    source_encoding = fields.Selection([
        ('auto', 'Automatic (UTF-8 / UTF-16 BOM)'),
        ('cp1256', 'Windows Arabic (CP1256)'),
    ], default='auto', required=True, string='File Encoding')
    issue_ids = fields.One2many('ab_ecommerce_legacy_import_issue', 'batch_id', readonly=True)
    issue_count = fields.Integer(string='Validation Issues', readonly=True)
    corrected_count = fields.Integer(string='Rows with Safe Corrections', readonly=True)
    total_rows = fields.Integer(string='Records Scanned', readonly=True)
    review_version = fields.Integer(readonly=True)
    eligible_count = fields.Integer(string='Eligible for New Codes', compute='_compute_eligibility')
    eligible_percentage = fields.Float(string='Eligible Percentage', compute='_compute_eligibility', digits=(5, 2))
    existing_count = fields.Integer(string='Existing Customers', compute='_compute_eligibility')
    has_blocking_issues = fields.Boolean(string='File Needs Correction', readonly=True)
    source_digest = fields.Char(readonly=True)
    expires_at = fields.Datetime(required=True, default=lambda self: fields.Datetime.now() + timedelta(days=30))
    state = fields.Selection([('draft', 'Draft'), ('review', 'Review Required'), ('ready', 'Ready'), ('processing', 'Processing'), ('done', 'Completed'), ('cancelled', 'Cancelled')], default='draft', required=True, readonly=True)
    accepted_count = fields.Integer(readonly=True)
    rejected_count = fields.Integer(readonly=True)
    inactive_count = fields.Integer(readonly=True)
    created_count = fields.Integer(readonly=True)
    skipped_count = fields.Integer(readonly=True)
    export_count = fields.Integer(readonly=True)
    last_export_at = fields.Datetime(readonly=True)
    chunk_ids = fields.One2many('ab_ecommerce_legacy_chunk', 'batch_id', readonly=True)

    @api.depends('accepted_count', 'total_rows', 'has_blocking_issues', 'issue_count', 'state', 'review_version')
    def _compute_eligibility(self):
        existing = dict(self.env['ab_ecommerce_legacy_import_issue']._read_group(
            fields.Domain('batch_id', 'in', self.ids) & fields.Domain('import_status', '=', 'existing'),
            ['batch_id'], ['source_row:count_distinct'],
        ))
        for batch in self:
            batch.existing_count = existing.get(batch, 0)
            batch.eligible_count = max(0, batch.accepted_count - batch.existing_count) if not batch.has_blocking_issues and batch.review_version == 2 and batch.state != 'cancelled' else 0
            batch.eligible_percentage = 100 * batch.eligible_count / batch.total_rows if batch.total_rows else 0

    def _check_operator(self):
        user = self.env.user
        if not user.has_group('base.group_system') and not user.has_group('website.group_website_designer'):
            raise AccessError(_('Only Website editors and designers can manage activation batches.'))
        self.check_access('read')
        for batch in self:
            if batch.company_id not in self.env.companies or (batch.owner_id != user and not user.has_group('base.group_system')):
                raise AccessError(_('You can manage only your own activation batches in your allowed companies.'))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            if not self.env.user.has_group('base.group_system') and not self.env.user.has_group('website.group_website_designer'):
                raise AccessError(_('Only Website editors and designers can manage activation batches.'))
            allowed = {'name', 'website_id', 'source_namespace', 'source_file', 'source_filename', 'source_encoding', 'expires_at'}
            if any(set(values) - allowed for values in vals_list):
                raise AccessError(_('Activation processing fields cannot be changed directly.'))
            vals_list = [dict(values, owner_id=self.env.uid, state='draft', accepted_count=0, rejected_count=0, inactive_count=0, created_count=0, skipped_count=0, export_count=0, last_export_at=False, source_digest=False, chunk_ids=[], issue_ids=[], issue_count=0, corrected_count=0, total_rows=0, has_blocking_issues=False, review_version=0) for values in vals_list]
        for values in vals_list:
            self._validate_upload_size(values.get('source_file', self.env.context.get('default_source_file')))
        result = super().create(vals_list)
        result._check_operator()
        return result

    def write(self, values):
        if not self.env.su:
            self._check_operator()
            for batch in self.sorted('id'):
                batch._lock_batch()
            allowed = {'name', 'website_id', 'source_namespace', 'source_file', 'source_filename', 'source_encoding', 'expires_at'}
            if set(values) - allowed or any(batch.state != 'draft' for batch in self):
                raise AccessError(_('Activation processing fields cannot be changed directly.'))
        self._validate_upload_size(values.get('source_file'))
        result = super().write(values)
        if not self.env.su:
            self._check_operator()
        return result

    def unlink(self):
        raise AccessError(_('Cancel activation batches instead of deleting them.'))

    def _lock_batch(self):
        self.ensure_one()
        LegacyCodeSecurity(self.env)._lock(f'legacy-batch:{self.id}')
        self.invalidate_recordset()
        self._check_operator()

    def _validate_expiry(self):
        now = fields.Datetime.now()
        if not self.expires_at or not now < self.expires_at <= now + timedelta(days=90):
            raise ValidationError(_('Choose an expiry in the future, no more than 90 days away.'))

    def _validate_upload_size(self, value):
        if value and len(value) > 4 * ((90 * 1024 * 1024 + 2) // 3):
            raise ValidationError(_('The CSV file must not exceed 90 MB.'))

    @contextmanager
    def _source_stream(self):
        self.ensure_one()
        self._check_operator()
        attachment = self.env['ir.attachment'].sudo().search(
            fields.Domain('res_model', '=', self._name)
            & fields.Domain('res_field', '=', 'source_file')
            & fields.Domain('res_id', '=', self.id), limit=1,
        )
        if not attachment:
            raise ValidationError(_('Upload a customer CSV file first.'))
        if attachment.file_size > 90 * 1024 * 1024:
            raise ValidationError(_('The CSV file must not exceed 90 MB.'))
        if attachment.store_fname:
            with open(attachment._full_path(attachment.store_fname), 'rb') as source:
                yield source
        else:
            with io.BytesIO(attachment.raw or b'') as source:
                yield source

    def _diagnostic_events(self, binary):
        for event in csv_events(binary, self.source_encoding):
            yield customer_event(event, self.source_namespace)

    def _issue_values(self, event, status):
        columns = event.get('columns', [])
        return [{
            **problem, 'batch_id': self.id, 'source_row': event['number'],
            'line_start': event['start'], 'line_end': event['end'],
            'column_number': columns.index(problem['column_name']) + 1 if problem['column_name'] in columns else 0,
            'source_reference': event.get('source_key', ''), 'import_status': status,
        } for problem in event['issues']]

    def _store_preview_records(self, model, values):
        if values:
            records = self.env[model].sudo().create(values)
            records.flush_recordset()
            records.invalidate_recordset()
            values.clear()

    def _existing_import_issues(self, rows):
        customers = self.env['ab_ecommerce_legacy_customer'].sudo().with_context(active_test=False).search(
            fields.Domain('website_id', '=', self.website_id.id)
            & (fields.Domain('source_key', 'in', [row['source_key'] for row in rows])
               | fields.Domain('phone', 'in', [row['phone'] for row in rows]))
        )
        keys, phones = set(customers.mapped('source_key')), set(customers.mapped('phone'))
        problems = []
        for row in rows:
            for column, code, value, matched in (
                (row['source_key'].split(':')[1], 'existing_reference', row.get('original_reference', row['source_key']), row['source_key'] in keys),
                ('mobile_phone', 'existing_phone', row.get('original_phone', row['phone']), row['phone'] in phones),
            ):
                if matched:
                    problems.append({
                        **issue(column, code, value), 'batch_id': self.id,
                        'source_row': row.get('source_row', 0), 'source_reference': row['source_key'],
                        'line_start': row.get('line_start', 0), 'line_end': row.get('line_end', 0),
                        'import_status': 'existing',
                    })
        return problems

    def _append_existing_preview_issues(self, rows, problems):
        existing = self._existing_import_issues(rows)
        source_rows = {problem['source_row'] for problem in existing}
        if source_rows:
            for problem in problems:
                if problem['source_row'] in source_rows:
                    problem['import_status'] = 'existing'
            self.env['ab_ecommerce_legacy_import_issue'].sudo().search(
                fields.Domain('batch_id', '=', self.id) & fields.Domain('source_row', 'in', source_rows)
            ).write({'import_status': 'existing'})
        problems.extend(existing)
        return len(existing)

    def _parse_file(self):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', self.source_namespace or ''):
            raise ValidationError(_('Use letters, numbers, underscores or hyphens for the source namespace.'))
        with self._source_stream() as binary:
            digest = hashlib.sha256()
            while block := binary.read(1024 * 1024):
                digest.update(block)
            binary.seek(0)
            keys, phones = Counter(), Counter()
            blocked = False
            total = 0
            for event in self._diagnostic_events(binary):
                blocked |= event['blocked']
                total = max(total, event['number'])
                phones.update(event['reserved_phones'])
                if not event['inactive']:
                    if event['source_key']:
                        keys[event['source_key']] += 1
                    if event['phone']:
                        phones[event['phone']] += 1
            binary.seek(0)
            accepted = rejected = inactive = corrected = issue_count = 0
            rows, chunks, problems = [], [], []
            for event in self._diagnostic_events(binary):
                if not event['number']:
                    status = 'blocked' if event['blocked'] else 'info'
                elif not event['values']:
                    rejected += 1
                    status = 'blocked' if event['blocked'] else 'excluded'
                else:
                    if not event['inactive']:
                        if event['source_key'] and keys[event['source_key']] > 1:
                            column = event['source_key'].split(':')[1]
                            event['issues'].append(issue(column, 'duplicate_reference', event['values'].get(column)))
                        if event['phone'] and phones[event['phone']] > 1:
                            event['issues'].append(issue('mobile_phone', 'duplicate_phone', event['values'].get('mobile_phone'), event['phone']))
                    errors = [problem for problem in event['issues'] if problem['issue_code'] not in CORRECTED_CODES | INFO_CODES]
                    if event['inactive']:
                        inactive += 1
                        status = 'inactive'
                    elif errors or not event['customer']:
                        rejected += 1
                        status = 'excluded'
                    else:
                        accepted += 1
                        corrected += bool(event['issues'])
                        status = 'blocked' if blocked else 'ready'
                        if not blocked:
                            reference_column = event['source_key'].split(':')[1]
                            rows.append({
                                **event['customer'], 'source_row': event['number'],
                                'line_start': event['start'], 'line_end': event['end'],
                                'original_phone': event['values'].get('mobile_phone', ''),
                                'original_reference': event['values'].get(reference_column, ''),
                            })
                            if len(rows) == 1000:
                                issue_count += self._append_existing_preview_issues(rows, problems)
                                chunks.append({'batch_id': self.id, 'payload': json.dumps(rows)})
                                rows = []
                values = self._issue_values(event, status)
                problems.extend(values)
                issue_count += len(values)
                if len(problems) >= 1000:
                    self._store_preview_records('ab_ecommerce_legacy_import_issue', problems)
                if len(chunks) >= 10:
                    self._store_preview_records('ab_ecommerce_legacy_chunk', chunks)
            if rows:
                issue_count += self._append_existing_preview_issues(rows, problems)
                chunks.append({'batch_id': self.id, 'payload': json.dumps(rows)})
            if blocked:
                problems.append({
                    'batch_id': self.id, 'source_row': 0, 'column_name': '(file)',
                    'issue_code': 'file_blocked', 'import_status': 'blocked',
                })
                issue_count += 1
            self._store_preview_records('ab_ecommerce_legacy_import_issue', problems)
            self._store_preview_records('ab_ecommerce_legacy_chunk', chunks)
            self.sudo().write({
                'issue_count': issue_count, 'corrected_count': corrected,
                'total_rows': total, 'has_blocking_issues': blocked,
            })
            return accepted, rejected, inactive, digest.hexdigest()

    def action_preview(self):
        self._check_operator()
        self._lock_batch()
        if self.state != 'draft':
            raise UserError(_('This batch has already been prepared.'))
        self._validate_expiry()
        try:
            with self.env.cr.savepoint():
                accepted, rejected, inactive, digest = self._parse_file()
        except OSError:
            self.env['ab_ecommerce_legacy_import_issue'].sudo().create({
                'batch_id': self.id, 'column_name': '(file)',
                'issue_code': 'file_unreadable', 'import_status': 'blocked',
            })
            self.sudo().write({'state': 'review', 'has_blocking_issues': True, 'issue_count': 1})
            return True
        self.sudo().write({
            'state': 'ready' if accepted and not self.has_blocking_issues else 'review',
            'accepted_count': accepted, 'rejected_count': rejected,
            'inactive_count': inactive, 'source_digest': digest,
            'review_version': 2,
        })
        return True

    def action_review_issues(self):
        self._check_operator()
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('ab_website_sale_product.action_legacy_import_issues')
        action.update(domain=[('batch_id', '=', self.id)], context={'default_batch_id': self.id})
        return action

    def action_reset_preview(self):
        self._check_operator()
        self._lock_batch()
        if self.state not in ('draft', 'review', 'ready'):
            raise UserError(_('Only unprocessed batches can be reviewed again.'))
        self.sudo().issue_ids.unlink()
        self.sudo().chunk_ids.unlink()
        self.sudo().write({
            'state': 'draft', 'accepted_count': 0, 'rejected_count': 0, 'inactive_count': 0,
            'issue_count': 0, 'corrected_count': 0, 'total_rows': 0,
            'has_blocking_issues': False, 'source_digest': False,
            'review_version': 0,
        })
        return True

    def action_recheck(self):
        self.action_reset_preview()
        return self.action_preview()

    def action_download_review(self):
        self._check_operator()
        self.ensure_one()
        if self.state not in {'ready', 'review'} or self.review_version != 2:
            raise UserError(_('Preview the file again before downloading the customer review.'))
        return {'type': 'ir.actions.act_url', 'url': f'/ab_legacy/review/{self.id}', 'target': 'download'}

    def _review_csv_file(self):
        self._check_operator()
        self._lock_batch()
        self.action_download_review()
        reasons = dict(self.env['ab_ecommerce_legacy_import_issue']._fields['issue_code']._description_selection(self.env))
        statuses = {
            'ready': _('Eligible'), 'corrected': _('Eligible after correction'),
            'excluded': _('Excluded'), 'inactive': _('Inactive'),
            'existing': _('Already Exists'), 'blocked': _('File Needs Correction'),
            'info': _('File information'),
        }
        extra_headers = [
            _('Review: status'), _('Review: problem / correction'), _('Review: issue codes'),
            _('Review: corrected mobile'), _('Review: corrected name'), _('Review: customer reference'),
            _('Review: source record'), _('Review: first file line'), _('Review: last file line'),
            _('Review: original malformed record'),
        ]
        output = tempfile.TemporaryFile(mode='w+b')
        try:
            with tempfile.TemporaryFile(mode='w+', encoding='utf-8', newline='') as eligible, tempfile.TemporaryFile(mode='w+', encoding='utf-8', newline='') as excluded:
                writers = {True: csv.writer(eligible), False: csv.writer(excluded)}
                original_columns = []
                bucket = -1
                problems = defaultdict(list)
                with self._source_stream() as binary:
                    digest = hashlib.sha256()
                    while block := binary.read(1024 * 1024):
                        digest.update(block)
                    if digest.hexdigest() != self.source_digest:
                        raise UserError(_('The source file changed. Preview it again before downloading.'))
                    binary.seek(0)
                    for event in self._diagnostic_events(binary):
                        original_columns = event['original_columns']
                        current = event['number'] // 1000
                        if current != bucket:
                            bucket = current
                            records = self.env['ab_ecommerce_legacy_import_issue'].search(
                                fields.Domain('batch_id', '=', self.id)
                                & fields.Domain('source_row', '>=', bucket * 1000)
                                & fields.Domain('source_row', '<', (bucket + 1) * 1000),
                                order='source_row,id',
                            )
                            problems = defaultdict(list)
                            for problem in records.read(['source_row', 'column_name', 'issue_code', 'import_status']):
                                problems[problem['source_row']].append(problem)
                            records.invalidate_recordset()
                        row_problems = problems[event['number']]
                        row_statuses = {problem['import_status'] for problem in row_problems}
                        if not event['number']:
                            status = 'blocked' if self.has_blocking_issues else 'info'
                        elif self.has_blocking_issues or 'blocked' in row_statuses:
                            status = 'blocked'
                        elif 'existing' in row_statuses:
                            status = 'existing'
                        elif 'inactive' in row_statuses:
                            status = 'inactive'
                        elif 'excluded' in row_statuses or not event['customer']:
                            status = 'excluded'
                        else:
                            status = 'corrected' if row_problems else 'ready'
                        valid = status in {'ready', 'corrected'}
                        source_values = event.get('source_values', [])
                        original = (source_values + [''] * len(original_columns))[:len(original_columns)]
                        raw = event.get('raw_record', '') if event['number'] else ''
                        customer = event['customer'] or {}
                        row = [*original, statuses[status],
                               ' | '.join(f"{problem['column_name']}: {reasons[problem['issue_code']]}" for problem in row_problems),
                               ' | '.join(dict.fromkeys(problem['issue_code'] for problem in row_problems)),
                               customer.get('phone', ''), customer.get('name', ''), event['source_key'],
                               event['number'], event['start'], event['end'], raw]
                        writers[valid].writerow([self._review_cell(value) for value in row])
                text = io.TextIOWrapper(output, encoding='utf-8-sig', newline='')
                try:
                    csv.writer(text).writerow([self._review_cell(value) for value in original_columns + extra_headers])
                    for section in (eligible, excluded):
                        section.seek(0)
                        shutil.copyfileobj(section, text, 64 * 1024)
                    text.flush()
                finally:
                    text.detach()
            output.seek(0)
            return output
        except Exception:
            output.close()
            raise

    def _review_cell(self, value):
        value = str(value)
        if re.fullmatch(r'\+[0-9]+', value):
            return value
        if value.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')):
            return "'" + value
        return value

    def action_generate_codes(self):
        self._check_operator()
        self.ensure_one()
        if self.state not in {'ready', 'processing'} or self.has_blocking_issues or self.review_version != 2:
            raise UserError(_('Prepare the customer preview before creating codes.'))
        self._validate_expiry()
        return {'type': 'ir.actions.client', 'tag': 'ab_legacy_process_batch', 'params': {'batch_id': self.id}}

    def action_process_next(self):
        self._check_operator()
        self._lock_batch()
        if self.state == 'done':
            return {'done': True, 'processed': self.created_count + self.skipped_count, 'total': self.accepted_count}
        if self.state not in {'ready', 'processing'} or self.has_blocking_issues or self.review_version != 2:
            raise UserError(_('This batch cannot be processed.'))
        self._validate_expiry()
        service = LegacyCodeSecurity(self.env)
        service._lock(f'legacy-import-website:{self.website_id.id}')
        chunk = self.env['ab_ecommerce_legacy_chunk'].sudo().search([('batch_id', '=', self.id), ('processed', '=', False)], order='id', limit=1)
        if not chunk:
            self.sudo().write({'state': 'done', 'source_file': False})
            return {'done': True, 'processed': self.created_count + self.skipped_count, 'total': self.accepted_count}
        rows = json.loads(chunk.payload)
        customers = self.env['ab_ecommerce_legacy_customer'].sudo().with_context(active_test=False)
        existing = customers.search(fields.Domain('website_id', '=', self.website_id.id) & (fields.Domain('source_key', 'in', [row['source_key'] for row in rows]) | fields.Domain('phone', 'in', [row['phone'] for row in rows])))
        existing_keys = set(existing.mapped('source_key'))
        existing_phones = set(existing.mapped('phone'))
        new_rows = [row for row in rows if row['source_key'] not in existing_keys and row['phone'] not in existing_phones]
        exported = []
        values = []
        for row in new_rows:
            code = f'{secrets.randbelow(10 ** 12):012d}'
            digest = service._digest(f"legacy-code:{self.website_id.id}:{row['source_key']}:{code}")
            values.append(dict({key: row[key] for key in ('source_key', 'phone', 'name', 'source_store')}, website_id=self.website_id.id, batch_id=self.id, expires_at=self.expires_at, code_hash=digest))
            exported.append([row['source_key'], row['phone'], code, fields.Datetime.to_string(self.expires_at)])
        created = customers.create(values)
        imported_rows = [row['source_row'] for row in new_rows if row.get('source_row')]
        self.env['ab_ecommerce_legacy_import_issue'].sudo().search(
            fields.Domain('batch_id', '=', self.id) & fields.Domain('source_row', 'in', imported_rows)
        ).write({'import_status': 'imported'})
        skipped_rows = [row for row in rows if row['source_key'] in existing_keys or row['phone'] in existing_phones]
        existing_issues = self.env['ab_ecommerce_legacy_import_issue'].sudo().search(
            fields.Domain('batch_id', '=', self.id)
            & fields.Domain('source_row', 'in', [row.get('source_row', 0) for row in skipped_rows])
        )
        existing_issues.write({'import_status': 'existing'})
        reported = {(record.source_row, record.issue_code) for record in existing_issues}
        skipped_problems = [problem for problem in self._existing_import_issues(skipped_rows)
                            if (problem['source_row'], problem['issue_code']) not in reported]
        added_issues = len(skipped_problems)
        self._store_preview_records('ab_ecommerce_legacy_import_issue', skipped_problems)
        encrypted = service._cipher().encrypt(json.dumps(exported).encode()).decode()
        chunk.write({'payload': False, 'encrypted_export': encrypted, 'processed': True})
        self.sudo().write({'state': 'processing', 'created_count': self.created_count + len(created), 'skipped_count': self.skipped_count + len(rows) - len(created), 'issue_count': self.issue_count + added_issues})
        done = not self.env['ab_ecommerce_legacy_chunk'].sudo().search_count([('batch_id', '=', self.id), ('processed', '=', False)], limit=1)
        if done:
            self.sudo().write({'state': 'done', 'source_file': False})
        return {'done': done, 'processed': self.created_count + self.skipped_count, 'total': self.accepted_count}

    def action_download(self):
        self._check_operator()
        self.ensure_one()
        if self.state != 'done' or self.expires_at <= fields.Datetime.now():
            raise UserError(_('Only completed, unexpired batches can be exported.'))
        return {'type': 'ir.actions.act_url', 'url': f'/ab_legacy/exports/{self.id}', 'target': 'download'}

    def _export_csv(self):
        self._check_operator()
        self._lock_batch()
        self.action_download()
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(['customer_reference', 'mobile_phone', 'activation_code', 'expires_at_utc', 'message'])
        cipher = LegacyCodeSecurity(self.env)._cipher()
        for chunk in self.env['ab_ecommerce_legacy_chunk'].sudo().search([('batch_id', '=', self.id)], order='id'):
            for row in json.loads(cipher.decrypt(chunk.encrypted_export.encode())):
                message = _('Your Abdin Pharmacies activation code is %s. Use it once on our website. Do not share it.', row[2])
                writer.writerow([*row, message])
        self.env['ab_ecommerce_legacy_export'].sudo().create({'batch_id': self.id, 'user_id': self.env.uid})
        self.sudo().write({'export_count': self.export_count + 1, 'last_export_at': fields.Datetime.now()})
        return output.getvalue()

    def action_cancel(self):
        self._check_operator()
        self._lock_batch()
        if self.state == 'cancelled':
            return True
        service = LegacyCodeSecurity(self.env)
        service._lock(f'legacy-import-website:{self.website_id.id}')
        chunks = self.env['ab_ecommerce_legacy_chunk'].sudo().search([('batch_id', '=', self.id)])
        self.sudo().write({'state': 'cancelled', 'source_file': False})
        cipher = service._cipher()
        for chunk in chunks.filtered('encrypted_export'):
            keys = [row[0] for row in json.loads(cipher.decrypt(chunk.encrypted_export.encode()))]
            self.env['ab_ecommerce_legacy_customer'].sudo().search(fields.Domain('website_id', '=', self.website_id.id) & fields.Domain('source_key', 'in', keys) & fields.Domain('partner_id', '=', False)).write({'code_hash': False})
        chunks.write({'payload': False, 'encrypted_export': False})
        return True


class ActivationChunk(models.Model):
    _name = 'ab_ecommerce_legacy_chunk'
    _description = 'Activation Processing Chunk'

    batch_id = fields.Many2one('ab_ecommerce_legacy_batch', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one(related='batch_id.company_id', store=True)
    payload = fields.Text(groups='base.group_system')
    encrypted_export = fields.Text(groups='base.group_system')
    processed = fields.Boolean(default=False)


class ActivationExport(models.Model):
    _name = 'ab_ecommerce_legacy_export'
    _description = 'Activation Export Audit'
    _order = 'id desc'

    batch_id = fields.Many2one('ab_ecommerce_legacy_batch', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one(related='batch_id.company_id', store=True)
    user_id = fields.Many2one('res.users', required=True, readonly=True)
    exported_at = fields.Datetime(default=fields.Datetime.now, required=True, readonly=True)
