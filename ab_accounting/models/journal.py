import hashlib
import json
import math
import uuid

from psycopg2 import IntegrityError
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError, ConcurrencyError
from odoo.tools.float_utils import float_compare


def amount(value):
    """Validate before Float's storage conversion can round an invalid submission."""
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValidationError(_('Amounts must be finite numbers with at most two decimal places.'))
    try:
        value = float(value)
    except OverflowError:
        raise ValidationError(_("Amounts must be finite numbers with at most two decimal places.")) from None
    if not math.isfinite(value) or abs(value) >= 10**14 or abs(value - round(value, 2)) > min(1e-7, max(1e-10, math.ulp(value) * 2)):
        raise ValidationError(_('Amounts must be finite numbers with at most two decimal places.'))
    return value


LINE_INPUT = {'account_id', 'partner_id', 'costcenter_id', 'explain', 'doc_no', 'due_date', 'debit_val', 'credit_val'}
AUDIT = {'state', 'is_posted', 'posting_number', 'posted_by', 'posted_at', 'posted_date', 'request_fingerprint', 'reversal_of_id', 'is_frozen', 'reviewed_by', 'reviewed_at'}
IDENTITY = {'origin_database', 'operation_identity'}


class Header(models.Model):
    _name = 'ab_accounting_je_header'
    _inherit = ['ab_accounting_scope', 'mail.thread']
    _description = 'Journal'
    _order = 'accounting_date desc, posting_number desc, id desc'
    _rec_name = 'posting_number'
    _rec_names_search = ['posting_number', 'reference', 'operation_identity']

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    branch_id = fields.Many2one('ab_store', required=True, ondelete='restrict', index=True)
    store_id = fields.Many2one(related='branch_id', store=True, readonly=True)
    accounting_date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    account_id = fields.Many2one('ab_accounting_account_guide', string='Counterpart Account', ondelete='restrict')
    doctype_id = fields.Many2one('ab_accounting_doctype', string='Document Type', required=True, ondelete='restrict')
    reference = fields.Char()
    line_ids = fields.One2many('ab_accounting_je_line', 'header_id', string='Journal Items', copy=True)
    state = fields.Selection([('draft', 'Draft'), ('posted', 'Posted')], default='draft', required=True, readonly=True, tracking=True, index=True)
    is_posted = fields.Boolean(compute='_compute_posted', store=True, readonly=True)
    posting_number = fields.Char(default='/', readonly=True, copy=False, index=True)
    posted_by = fields.Many2one('res.users', readonly=True, copy=False)
    posted_at = fields.Datetime(readonly=True, copy=False)
    posted_date = fields.Date(readonly=True, copy=False)
    origin_database = fields.Char(required=True, default=lambda self: self.env.cr.dbname, copy=False, readonly=True)
    operation_identity = fields.Char(required=True, default=lambda self: 'manual:' + str(uuid.uuid4()), copy=False, readonly=True)
    request_fingerprint = fields.Char(readonly=True, copy=False)
    source_model = fields.Char(copy=False)
    source_res_id = fields.Integer(string='Source Record ID', copy=False)
    source_reference = fields.Char(copy=False)
    event_type = fields.Char(default='manual', required=True, copy=False)
    original_event_reference = fields.Char(copy=False)
    reversal_of_id = fields.Many2one('ab_accounting_je_header', readonly=True, copy=False, ondelete='restrict')
    reversal_ids = fields.One2many('ab_accounting_je_header', 'reversal_of_id', readonly=True)
    reversal_reason = fields.Char(copy=False)
    opening_run_id = fields.Many2one('ab_accounting_opening_run', ondelete='restrict', copy=False, index=True)
    active = fields.Boolean(default=True)
    is_frozen = fields.Boolean(readonly=True, copy=False, tracking=True)
    reviewed_by = fields.Many2one('res.users', readonly=True, copy=False)
    reviewed_at = fields.Datetime(readonly=True, copy=False)
    review_note = fields.Text(copy=False)
    total_debit_val = fields.Float(string='Total Debit', compute='_compute_totals', digits=(16, 2), compute_sudo=False)
    total_credit_val = fields.Float(string='Total Credit', compute='_compute_totals', digits=(16, 2), compute_sudo=False)
    total_net_val = fields.Float(compute='_compute_totals', digits=(16, 2), compute_sudo=False, string='Difference')
    _identity_unique = models.Constraint('UNIQUE(origin_database, operation_identity)', 'The operation identity has already been used.')
    _reversal_unique = models.Constraint('UNIQUE(reversal_of_id)', 'A journal can have only one full reversal.')
    _number_unique = models.Constraint("EXCLUDE (posting_number WITH =) WHERE (state = 'posted')", 'Posting numbers must be unique.')

    @api.depends('state')
    def _compute_posted(self):
        for rec in self:
            rec.is_posted = rec.state == 'posted'

    @api.depends('line_ids.debit_val', 'line_ids.credit_val')
    def _compute_totals(self):
        for rec in self:
            rec.total_debit_val = math.fsum(rec.line_ids.mapped('debit_val'))
            rec.total_credit_val = math.fsum(rec.line_ids.mapped('credit_val'))
            rec.total_net_val = rec.total_debit_val - rec.total_credit_val

    def _lock(self):
        if self:
            self.flush_recordset()
            self.env.cr.execute('SELECT id FROM ab_accounting_je_header WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(self.ids)])
            self.invalidate_recordset()

    def _check_edit(self):
        self._require_poster()
        self.check_access('write')
        for rec in self:
            rec._check_scope(rec.company_id, rec.branch_id)
            if rec.state == 'posted' or rec.is_frozen:
                raise UserError(_('Posted or frozen journals cannot be financially changed.'))
            if not rec._bypass() and rec.create_uid != self.env.user:
                raise AccessError(_('Only the creator can edit or post this draft.'))
            if rec.opening_run_id.state == 'closed':
                raise UserError(_('The opening run is closed.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._require_poster()
        clean = []
        for original in vals_list:
            if AUDIT & original.keys() or {'store_id', 'reversal_ids', 'create_uid', 'write_uid'} & original.keys():
                raise UserError(_('Posting and review audit fields are controlled by workflow actions.'))
            vals = dict(original)
            # Explicit defaults defeat RPC default_* context injection.
            vals.update(state='draft', posting_number='/', is_frozen=False, posted_by=False, posted_at=False, posted_date=False, request_fingerprint=False, reversal_of_id=False, reviewed_by=False, reviewed_at=False)
            vals.setdefault('origin_database', self.env.cr.dbname)
            vals.setdefault('operation_identity', 'manual:' + str(uuid.uuid4()))
            clean.append(vals)
        with self.env.cr.savepoint():
            self._serialize_stores(self.env['ab_store'].browse(sorted({v.get('branch_id', self.env.context.get('default_branch_id')) for v in clean} - {None, False})))
            records = super().create(clean)
            records._validate_scope()
            return records

    def write(self, vals):
        branches = self.branch_id
        if vals.get('branch_id'):
            branches |= self.env['ab_store'].browse(vals['branch_id'])
        self._serialize_stores(branches)
        self._lock()
        if AUDIT & vals.keys() or IDENTITY & vals.keys() or {'store_id', 'reversal_ids', 'create_uid', 'write_uid'} & vals.keys():
            raise UserError(_('Posting and review audit fields are controlled by workflow actions.'))
        if set(vals) <= {'review_note'}:
            self._check_reviewer()
        else:
            self._check_edit()
        with self.env.cr.savepoint():
            result = super().write(vals)
            if set(vals) - {'review_note'}:
                self._validate_scope()
            return result

    def unlink(self):
        self._serialize_stores(self.branch_id)
        self._lock()
        self._check_edit()
        return super().unlink()

    def _validate_scope(self):
        for rec in self:
            rec._check_scope(rec.company_id, rec.branch_id)
            if bool(rec.source_model) != bool(rec.source_res_id) or rec.source_res_id < 0:
                raise ValidationError(_("A local source link requires both a model and a record identifier."))
            if rec.event_type not in {"manual", "opening", "reversal"} and not rec.source_reference:
                raise ValidationError(_("Required posting request values cannot be empty."))
            if not rec.doctype_id.active or rec.doctype_id.company_id != rec.company_id:
                raise ValidationError(_('The document type must be active and belong to the journal company.'))
            if rec.account_id and rec.account_id.company_id != rec.company_id:
                raise ValidationError(_('The account must belong to the journal company.'))
            if rec.account_id and not rec._bypass() and rec.account_id.id not in self.env.user._accounting_accounts('post'):
                raise AccessError(_('This account is not authorized for posting.'))
            if not rec._bypass() and rec.doctype_id not in self.env.user.accounting_auth_group_id.doctype_ids:
                raise AccessError(_('This document type is not authorized.'))
            if rec.opening_run_id:
                run = rec.opening_run_id
                run.check_access('read')
                if run.company_id != rec.company_id or run.branch_id != rec.branch_id or run.accounting_date != rec.accounting_date or run.state != 'open' or rec.source_model:
                    raise ValidationError(_('Opening journals must match an open run branch and date and have no business source.'))
            rec.line_ids._validate_dimensions(posting=False)

    def _validate_posting(self):
        self = self.with_context(active_test=False)
        self._validate_scope()
        # Lock configuration read by financial validation against concurrent edits.
        for records, table in [(self.line_ids.account_id, 'ab_accounting_account_guide'), (self.doctype_id, 'ab_accounting_doctype'), (self.line_ids.costcenter_id, 'ab_costcenter')]:
            if records:
                records.flush_recordset()
                # Table names are fixed internal constants, never caller input.
                self.env.cr.execute('SELECT id FROM ' + table + ' WHERE id IN %s ORDER BY id FOR SHARE', [tuple(records.ids)])
                records.invalidate_recordset()
        for rec in self:
            if not rec.active:
                raise ValidationError(_('An archived journal cannot be posted.'))
            periods = self.env['ab_accounting_period'].search(fields.Domain('company_id', '=', rec.company_id.id) & fields.Domain('branch_id', '=', rec.branch_id.id) & fields.Domain('date_from', '<=', rec.accounting_date) & fields.Domain('date_to', '>=', rec.accounting_date))
            if len(periods) != 1 or periods.state != 'open':
                raise ValidationError(_('Posting requires exactly one open accounting period.'))
            rec.line_ids._validate_dimensions(posting=True)
            if len(rec.line_ids) < 2 or any(not (l.debit_val or l.credit_val) for l in rec.line_ids):
                raise ValidationError(_('A journal requires at least two nonzero lines.'))
            if float_compare(math.fsum(rec.line_ids.mapped('debit_val')), math.fsum(rec.line_ids.mapped('credit_val')), precision_digits=2):
                raise ValidationError(_('Debit and credit totals must balance to two decimal places.'))

    def _payload(self):
        self.ensure_one()
        payload = {k: self[k] or False for k in ['origin_database', 'operation_identity', 'source_model', 'source_res_id', 'source_reference', 'event_type', 'original_event_reference', 'reference', 'reversal_reason']}
        payload.update(company_id=self.company_id.id, branch_id=self.branch_id.id, doctype_id=self.doctype_id.id, accounting_date=str(self.accounting_date), opening_run_id=self.opening_run_id.id, account_id=self.account_id.id, reversal_of_id=self.reversal_of_id.id)
        payload['lines'] = []
        for line in self.line_ids:
            row = {k: line[k].id if line._fields[k].type == 'many2one' else line[k] or False for k in LINE_INPUT}
            row['due_date'] = str(line.due_date) if line.due_date else False
            for k in ['debit_val', 'credit_val']:
                row[k] = format(round(line[k], 2) or 0, '.2f')
            payload['lines'].append(row)
        payload['lines'].sort(key=lambda row: json.dumps(row, sort_keys=True))
        return payload

    def _fingerprint(self):
        return hashlib.sha256(json.dumps(self._payload(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def action_post(self):
        self._require_poster()
        with self.env.cr.savepoint():
            self._serialize_stores(self.branch_id)
            self._lock()
            drafts = self.filtered(lambda rec: rec.state != 'posted')
            drafts._check_edit()
            drafts._validate_posting()
            for rec in drafts:
                number = self.env['ir.sequence'].next_by_code('ab_accounting.posting')
                if not number:
                    raise UserError(_('The accounting posting sequence is missing.'))
                super(Header, rec).write({'state': 'posted', 'posting_number': number, 'posted_by': self.env.uid, 'posted_at': fields.Datetime.now(), 'posted_date': fields.Date.today(), 'request_fingerprint': rec._fingerprint()})
        return True

    def btn_post_je(self):
        return self.action_post()

    def btn_confirm_all_je(self):
        return self.action_confirm()

    def btn_freeze(self):
        return self.action_freeze()

    def btn_unfreeze(self):
        return self.action_unfreeze()

    @api.model
    def post_journal(self, request):
        """Atomic generated-entry contract; see POSTING_CONTRACT.md. No commit."""
        self._require_poster()
        allowed = {'origin_database', 'operation_identity', 'company_id', 'branch_id', 'doctype_id', 'accounting_date', 'source_model', 'source_res_id', 'source_reference', 'event_type', 'original_event_reference', 'reference', 'opening_run_id', 'lines'}
        required = {'origin_database', 'operation_identity', 'company_id', 'branch_id', 'doctype_id', 'accounting_date', 'source_reference', 'event_type', 'lines'}
        if not isinstance(request, dict) or set(request) - allowed or required - set(request):
            raise ValidationError(_('The posting request contains missing or unsupported fields.'))
        if not all(request[k] for k in required):
            raise ValidationError(_('Required posting request values cannot be empty.'))
        if any(not isinstance(request[k], str) or not request[k].strip() for k in ['origin_database', 'operation_identity', 'source_reference', 'event_type']):
            raise ValidationError(_('Operation identity, origin, source reference and event type must be nonempty text.'))
        if any(isinstance(request[k], bool) or not isinstance(request[k], int) or request[k] <= 0 for k in ['company_id', 'branch_id', 'doctype_id']):
            raise ValidationError(_('Posting scope identifiers must be positive integers.'))
        if bool(request.get('source_model')) != bool(request.get('source_res_id')):
            raise ValidationError(_('A local source link requires both a model and a record identifier.'))
        if not isinstance(request['lines'], list) or any(not isinstance(l, dict) or set(l) - LINE_INPUT for l in request['lines']):
            raise ValidationError(_('Journal lines contain unsupported fields.'))
        for line in request['lines']:
            amount(line.get('debit_val', 0))
            amount(line.get('credit_val', 0))
        # The service contract is explicit; native action default_* context must not
        # silently become part of a generated journal or change retry semantics.
        vals = {key: request.get(key, False) for key in allowed - {'lines'}}
        vals.update(account_id=False, reversal_reason=False, active=True)
        vals['line_ids'] = [fields.Command.create(dict({
            key: line.get(key, 0 if key in {'debit_val', 'credit_val'} else False)
            for key in LINE_INPUT
        }, active=True)) for line in request['lines']]
        branch = self.env['ab_store'].browse(request['branch_id']).exists()
        company = self.env['res.company'].browse(request['company_id']).exists()
        if not branch or not company:
            raise ValidationError(_('The posting scope does not exist.'))
        self._check_scope(company, branch)
        with self.env.cr.savepoint():
            self._serialize_stores(branch)
            # Bounded identity lookup only. Validate ordinary access before reading content.
            existing = self.sudo().with_context(active_test=False).search(fields.Domain('origin_database', '=', request['origin_database']) & fields.Domain('operation_identity', '=', request['operation_identity']), limit=1).with_env(self.env)
            if existing:
                existing.check_access('read')
                existing._check_scope(existing.company_id, existing.branch_id)
                if not self._bypass() and existing.create_uid != self.env.user:
                    raise AccessError(_('Only the creator can retry this operation.'))
                # Use an in-memory record to normalize the request without a second persisted journal.
                candidate = self.new(dict(vals, reversal_of_id=False))
                if existing.state != 'posted' or candidate._fingerprint() != existing.request_fingerprint:
                    raise ValidationError(_('The operation identity was reused with different content.'))
                return existing
            try:
                with self.env.cr.savepoint():
                    journal = self.create(vals)
                    journal.action_post()
                    return journal
            except IntegrityError as exc:
                if 'identity_unique' not in (exc.diag.constraint_name or ''):
                    raise
                # PostgreSQL REPEATABLE READ cannot see a concurrent winner in this snapshot.
                # Retry the entire business transaction, never commit/retry only accounting.
                raise ConcurrencyError('Concurrent accounting operation; retry the complete transaction.') from exc

    def _check_reviewer(self):
        self.check_access('write')
        if not (self._manager() or self.env.user.has_group('ab_accounting.group_ab_accounting_reviewer')):
            raise AccessError(_('Reviewer access is required.'))
        for rec in self:
            rec._check_scope(rec.company_id, rec.branch_id)
            if not self._manager() and (rec.create_uid == self.env.user or rec.create_uid not in self.env.user.responsible_for_ids):
                raise AccessError(_('This journal is outside your reviewer responsibilities.'))

    def action_confirm(self):
        self._lock()
        self._check_reviewer()
        if any(r.state != 'posted' for r in self):
            raise UserError(_('Only posted journals can be confirmed.'))
        return super().write({'reviewed_by': self.env.uid, 'reviewed_at': fields.Datetime.now(), 'is_frozen': True})

    def action_freeze(self):
        self._lock()
        self._check_reviewer()
        return super().write({'is_frozen': True})

    def action_unfreeze(self):
        self._lock()
        self._check_reviewer()
        return super().write({'is_frozen': False})

    def action_reverse(self, date=None, reason=None):
        self.ensure_one()
        if self.source_model or self.source_res_id or self.event_type not in {"manual", "opening"}:
            raise UserError(_('Reverse this business operation through its source workflow.'))
        return self._reverse(date, reason)

    def _reverse_from_source(self, source, date, reason):
        self.ensure_one()
        source.ensure_one()
        source.check_access('write')
        if not self.env.user.has_group('ab_accounting.group_ab_accounting_auto_je') or self.origin_database != self.env.cr.dbname or self.source_model != source._name or self.source_res_id != source.id:
            raise AccessError(_('Only the authorized source adapter can reverse this journal.'))
        return self._reverse(date, reason, source=source)

    def _reverse(self, date=None, reason=None, source=None):
        self.ensure_one()
        self._require_poster()
        self.check_access('read')
        reason = reason or self.reversal_reason
        if not (reason or '').strip():
            raise ValidationError(_('A reversal reason is required.'))
        with self.env.cr.savepoint():
            self._serialize_stores(self.branch_id)
            self._lock()
            if self.state != 'posted' or self.reversal_ids or self.reversal_of_id:
                raise UserError(_('Only an unreversed original posted journal can be reversed.'))
            if not self._bypass() and self.create_uid != self.env.user:
                raise AccessError(_('Only the creator can reverse this journal.'))
            vals = {'company_id': self.company_id.id, 'branch_id': self.branch_id.id, 'doctype_id': self.doctype_id.id, 'accounting_date': date or fields.Date.context_today(self), 'event_type': 'reversal', 'original_event_reference': self.operation_identity, 'reference': reason, 'reversal_reason': reason, 'line_ids': []}
            for line in self.line_ids:
                row = {k: line[k].id if line._fields[k].type == 'many2one' else line[k] for k in LINE_INPUT}
                row.update(debit_val=line.credit_val, credit_val=line.debit_val)
                vals['line_ids'].append(fields.Command.create(row))
            if source is not None:
                vals.update(source_model=source._name, source_res_id=source.id, source_reference=self.source_reference)
            reversal = self.create(vals)
            super(Header, reversal).write({'reversal_of_id': self.id})
            reversal.action_post()
            return reversal

    def action_reverse_wizard(self):
        self.ensure_one()
        self.check_access('read')
        self._check_scope(self.company_id, self.branch_id)
        return {'type': 'ir.actions.act_window', 'res_model': 'ab_accounting_reversal', 'view_mode': 'form', 'target': 'new', 'context': {'default_header_id': self.id}}

    def action_source(self):
        self.ensure_one()
        self.check_access('read')
        self._check_scope(self.company_id, self.branch_id)
        if self.origin_database != self.env.cr.dbname or not self.source_model or self.source_model not in self.env or not self.source_res_id:
            raise UserError(_('No accessible local source document is available.'))
        source = self.env[self.source_model].browse(self.source_res_id).exists()
        if not source:
            raise UserError(_('No accessible local source document is available.'))
        source.check_access('read')
        if 'company_id' in source._fields and source.company_id and source.company_id != self.company_id:
            raise AccessError(_('The source document belongs to a different company.'))
        for field in ['branch_id', 'store_id']:
            if field in source._fields and source._fields[field].type == 'many2one':
                target = source[field]
                expected = self.branch_id if target._name == 'ab_store' else None
                if expected is not None and target != expected:
                    raise AccessError(_('The source document belongs to a different branch.'))
        return {'type': 'ir.actions.act_window', 'res_model': self.source_model, 'res_id': source.id, 'view_mode': 'form'}


class Line(models.Model):
    _name = 'ab_accounting_je_line'
    _inherit = 'ab_accounting_scope'
    _description = 'Journal Item'
    _rec_name = 'explain'
    _order = 'accounting_date, posting_number, id'
    header_id = fields.Many2one('ab_accounting_je_header', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='header_id.company_id', store=True, index=True)
    branch_id = fields.Many2one(related='header_id.branch_id', store=True, index=True)
    store_id = fields.Many2one(related='header_id.store_id', store=True)
    accounting_date = fields.Date(related='header_id.accounting_date', store=True, index=True)
    posting_number = fields.Char(related='header_id.posting_number', store=True)
    state = fields.Selection(related='header_id.state', store=True, index=True)
    is_posted = fields.Boolean(related='header_id.is_posted')
    doctype_id = fields.Many2one(related='header_id.doctype_id', store=True)
    opening_run_id = fields.Many2one(related='header_id.opening_run_id', store=True)
    account_id = fields.Many2one('ab_accounting_account_guide', required=True, ondelete='restrict', index=True)
    partner_id = fields.Many2one('res.partner', ondelete='restrict', index=True)
    costcenter_id = fields.Many2one('ab_costcenter', ondelete='restrict', index=True)
    explain = fields.Char(string='Description', required=True)
    doc_no = fields.Char(string='Document Reference')
    due_date = fields.Date()
    debit_val = fields.Float(string='Debit', digits=(16, 2))
    credit_val = fields.Float(string='Credit', digits=(16, 2))
    net_val = fields.Float(string='Balance', compute='_compute_net', store=True, digits=(16, 2))
    active = fields.Boolean(default=True)

    @api.depends('debit_val', 'credit_val')
    def _compute_net(self):
        for rec in self:
            rec.net_val = rec.debit_val - rec.credit_val

    def _validate_dimensions(self, posting=False):
        allowed = None if self._bypass() else set(self.env.user._accounting_accounts('post'))
        for rec in self:
            rec._check_scope(rec.company_id, rec.branch_id)
            account = rec.account_id
            account.check_access('read')
            if account.company_id != rec.company_id:
                raise ValidationError(_('The account must belong to the journal company.'))
            if allowed is not None and account.id not in allowed:
                raise AccessError(_('This account is not authorized for posting.'))
            if rec.partner_id:
                rec.partner_id.check_access('read')
                if rec.partner_id.company_id and rec.partner_id.company_id != rec.company_id:
                    raise ValidationError(_('The partner must belong to the journal company.'))
            if rec.costcenter_id:
                rec.costcenter_id.check_access('read')
            if rec.debit_val < 0 or rec.credit_val < 0 or (rec.debit_val and rec.credit_val):
                raise ValidationError(_('Use a nonnegative debit or credit, never both on one line.'))
            if posting:
                if not account.active or not account.is_final or account.child_ids or not rec.active:
                    raise ValidationError(_('Posting requires active lines and active posting accounts.'))
                if (account.has_costcenter and not rec.costcenter_id) or (account.has_partner and not rec.partner_id) or (account.has_due_date and not rec.due_date):
                    raise ValidationError(_('Required account dimensions are missing.'))
                if rec.costcenter_id and (not rec.costcenter_id.active or (account.costcenter_ids and rec.costcenter_id not in account.costcenter_ids)):
                    raise ValidationError(_('The cost center is inactive or not allowed on this account.'))
                if not (rec.explain or '').strip():
                    raise ValidationError(_('A journal item description is required.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._require_poster()
        clean = []
        for original in vals_list:
            if set(original) - (LINE_INPUT | {'header_id', 'active'}):
                raise UserError(_('Journal item scope and audit fields are controlled by the header.'))
            vals = dict(original)
            vals.setdefault('header_id', self.env.context.get('default_header_id'))
            for field in ['debit_val', 'credit_val']:
                vals[field] = amount(vals.get(field, self.env.context.get("default_" + field, 0)))
            clean.append(vals)
        headers = self.env['ab_accounting_je_header'].browse(sorted({v['header_id'] for v in clean if v.get('header_id')}))
        self._serialize_stores(headers.branch_id)
        headers._lock()
        headers._check_edit()
        with self.env.cr.savepoint():
            records = super().create(clean)
            records._validate_dimensions()
            return records

    def write(self, vals):
        if set(vals) - (LINE_INPUT | {'active'}):
            raise UserError(_('Journal items cannot be reparented or have their scope overwritten.'))
        self._serialize_stores(self.header_id.branch_id)
        self.header_id._lock()
        self.header_id._check_edit()
        for field in ['debit_val', 'credit_val']:
            if field in vals:
                amount(vals[field])
        with self.env.cr.savepoint():
            result = super().write(vals)
            self._validate_dimensions()
            return result

    def unlink(self):
        self._serialize_stores(self.header_id.branch_id)
        self.header_id._lock()
        self.header_id._check_edit()
        return super().unlink()


class Reversal(models.TransientModel):
    _name = 'ab_accounting_reversal'
    _description = 'Reverse Journal'
    header_id = fields.Many2one('ab_accounting_je_header', required=True)
    accounting_date = fields.Date(required=True, default=fields.Date.context_today)
    reason = fields.Char(required=True)

    def action_reverse(self):
        self.ensure_one()
        rec = self.header_id.action_reverse(self.accounting_date, self.reason)
        return {'type': 'ir.actions.act_window', 'res_model': rec._name, 'res_id': rec.id, 'view_mode': 'form'}
