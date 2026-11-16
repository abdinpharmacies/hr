import base64
import binascii
import math
from decimal import Decimal, ROUND_HALF_UP

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


CLAIM_STATES = [
    ('draft', 'Draft'), ('in_progress', 'In Progress'),
    ('returned', 'Returned'), ('closed', 'Closed'),
]
PAYMENT_NATURE = [
    ('cash', 'Cash'), ('check', 'Check'), ('bank_transfer', 'Bank Transfer'),
]
TAX_CLASSIFICATION = [
    ('through_supplier', 'Advance Payments'), ('tax_payment', 'Tax Payment'),
    ('non_tax_payment', 'Non-tax Payment'),
]
SUPPLIER_SECTION = [('medical', 'Medicine'), ('cosmo', 'Cosmetics'), ('other', 'Other')]
PASSIVE_DECISIONS = [
    ('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'),
    ('deferred', 'Deferred'), ('cancelled', 'Cancelled'),
    ('not_required', 'Not Required'),
]
CLAIM_DEFAULT_FIELDS = ('type_of_invoice', 'payment_nature', 'tax_classification', 'section', 'area')
GROUP_PREFIX = 'ab_supplier_claim_cycle.supplier_claim_group_'


class SupplierClaimCycle(models.Model):
    _name = 'ab_supplier_claim_cycle'
    _description = 'Supplier Claim'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'supplier_id'
    _rec_names_search = ['claim_reference', 'supplier_id']
    _order = 'id desc'

    claim_reference = fields.Char(string='Claim ID', copy=False, tracking=True)
    _claim_reference_unique = models.Constraint(
        'UNIQUE(claim_reference)', 'Claim ID must be unique.')
    supplier_id = fields.Many2one(
        'ab_costcenter', required=True, ondelete='restrict', tracking=True,
        domain=fields.Domain('code', '=like', '1-%'))
    num_of_invoice = fields.Integer(required=True, tracking=True)
    state = fields.Selection(
        CLAIM_STATES, default='draft', required=True, readonly=True, copy=False, index=True)
    user_id = fields.Many2one(
        'res.users', default=lambda self: self.env.user, readonly=True, ondelete='set null')
    area = fields.Selection([('south', 'South'), ('north', 'North')], required=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
        readonly=True, index=True)
    claim_amount = fields.Float(required=True, digits=(16, 2), tracking=True)
    type_of_invoice = fields.Selection([
        ('original', 'Original'), ('copy', 'Copy'), ('bank_statement', 'Bank Statement'),
    ], required=True, tracking=True)
    payment_nature = fields.Selection(PAYMENT_NATURE, copy=False, tracking=True)
    tax_classification = fields.Selection(
        TAX_CLASSIFICATION, string='Tax Type', copy=False, tracking=True,
        help='Defaults from the latest claim for this cost center.')
    section = fields.Selection(
        SUPPLIER_SECTION, copy=False, tracking=True,
        help='Defaults from the latest claim for this cost center.')
    active = fields.Boolean(default=True)
    review_round = fields.Integer(default=0, readonly=True, copy=False)

    delivery_representative_name = fields.Char(string='Company Representative Name', copy=False)
    delivery_representative_phone = fields.Char(string='Company Representative Phone', copy=False)
    secretarial_notes = fields.Text()
    attachment = fields.Binary(string='Attachment', attachment=False, copy=False)
    attachment_filename = fields.Char(copy=False)
    supplier_cheque_attachment = fields.Binary(attachment=False, copy=False)
    supplier_cheque_filename = fields.Char(copy=False)
    tax_review_attachment = fields.Binary(attachment=False, copy=False)
    tax_review_filename = fields.Char(copy=False)
    payment_request_attachment = fields.Binary(attachment=False, copy=False)
    payment_request_filename = fields.Char(copy=False)
    bank_cheque_attachment = fields.Binary(string='Cheque Attachment', attachment=False, copy=False)
    bank_cheque_filename = fields.Char(copy=False)

    tax_discount_decision = fields.Selection([
        ('apply', 'Apply'), ('do_not_apply', 'Do Not Apply'),
    ], copy=False)
    tax_discount_rate = fields.Float(compute='_compute_amounts', digits=(16, 2), store=True)
    tax_discount_amount = fields.Float(compute='_compute_amounts', digits=(16, 2), store=True)
    net_claim_amount = fields.Float(compute='_compute_amounts', digits=(16, 2), store=True)

    document_revision = fields.Integer(default=1, readonly=True, copy=False)
    document_ids = fields.One2many(
        'ab_supplier_claim_document', 'claim_id', readonly=True, copy=False)
    history_ids = fields.One2many(
        'ab_supplier_claim_cycle.history', 'claim_id', readonly=True, copy=False)

    # Passive schema retained because installed workflows can still reference these
    # technical names. None of these fields drives workflow state or permissions.
    secretarial_preparation_status = fields.Selection([
        ('not_required', 'Not Required'), ('waiting', 'Waiting'), ('pending', 'Pending'),
        ('prepared', 'Prepared'), ('returned', 'Returned'), ('suspended', 'Suspended'),
    ], default='not_required', readonly=True, copy=False)
    preparation_started_at = fields.Datetime(readonly=True, copy=False)
    preparation_due_date = fields.Datetime(readonly=True, copy=False)
    payment_request_revision = fields.Integer(readonly=True, copy=False)
    bank_approval_revision = fields.Integer(readonly=True, copy=False)
    invalidated_payment_request_digest = fields.Char(readonly=True, copy=False)
    migration_gate_exception = fields.Boolean(readonly=True, copy=False)
    return_destination = fields.Selection([
        ('secretarial', 'Secretarial'), ('supplier_accounts', 'Supplier Accounts'),
    ], readonly=True, copy=False)
    resume_stage = fields.Char(readonly=True, copy=False)
    rejection_department = fields.Char(readonly=True, copy=False)
    rejection_reason = fields.Text(readonly=True, copy=False)
    tax_decision = fields.Selection(PASSIVE_DECISIONS, default='not_required', copy=False)
    tax_notes = fields.Text(copy=False)
    tax_followup_date = fields.Date(copy=False)
    inventory_decision = fields.Selection(PASSIVE_DECISIONS, default='not_required', copy=False)
    purchasing_decision = fields.Selection(PASSIVE_DECISIONS, default='not_required', copy=False)
    supplier_accounts_decision = fields.Selection(PASSIVE_DECISIONS, default='not_required', copy=False)
    bank_accounts_decision = fields.Selection(PASSIVE_DECISIONS, default='not_required', copy=False)
    inventory_notes = fields.Text(copy=False)
    purchasing_notes = fields.Text(copy=False)
    supplier_accounts_notes = fields.Text(copy=False)
    bank_accounts_notes = fields.Text(copy=False)
    inventory_followup_date = fields.Date(copy=False)
    purchasing_followup_date = fields.Date(copy=False)
    supplier_accounts_followup_date = fields.Date(copy=False)
    bank_accounts_followup_date = fields.Date(copy=False)

    @api.depends('claim_amount', 'tax_discount_decision')
    def _compute_amounts(self):
        for claim in self:
            amount = Decimal(str(claim.claim_amount)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)
            discount = Decimal('0')
            if claim.tax_discount_decision == 'apply':
                discount = (amount * Decimal('0.01')).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
            claim.tax_discount_rate = 1.0
            claim.tax_discount_amount = float(discount)
            claim.net_claim_amount = float(amount - discount)

    @api.constrains('claim_amount')
    def _check_amount(self):
        for claim in self:
            claim._validate_amount_value({'claim_amount': claim.claim_amount})

    @api.depends('claim_reference', 'supplier_id.display_name')
    def _compute_display_name(self):
        super()._compute_display_name()
        for claim in self:
            if claim.claim_reference:
                claim.display_name = f'[{claim.claim_reference}] {claim.display_name}'

    def _is_admin(self):
        return (self.env.su or self.env.user.has_group(GROUP_PREFIX + 'admin')
                or self.env.user.has_group('base.group_system'))

    def _require_role(self, role):
        allowed = self._is_admin()
        if role == 'user':
            allowed = allowed or self.env.user.has_group(GROUP_PREFIX + 'user')
        elif role != 'admin':
            raise AccessError(_('Unknown supplier claim role.'))
        if not allowed:
            raise AccessError(_('You are not authorized for this workflow action.'))

    def _prepare_action(self):
        self.check_access('write')
        self.lock_for_update()
        self.invalidate_recordset()
        self.check_access('write')
        if any(not claim.active or claim.state == 'closed' for claim in self):
            raise UserError(_('Closed or archived claims cannot be changed.'))

    @api.model
    def _entry_fields(self):
        return {
            'supplier_id', 'num_of_invoice', 'area', 'claim_amount', 'type_of_invoice',
            'secretarial_notes', 'attachment', 'attachment_filename',
            'delivery_representative_name', 'delivery_representative_phone',
            'claim_reference', 'tax_classification', 'section', 'payment_nature',
        }

    @api.model
    def _validate_amount_value(self, vals):
        if 'claim_amount' not in vals:
            return
        value = vals['claim_amount']
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0):
            raise ValidationError(_('The claim amount must be a positive finite number.'))

    @api.model
    def _normalize_claim_reference(self, value):
        return (value or '').strip().upper() or False

    def _last_claim_values_by_supplier(self, supplier_ids, exclude_ids=None):
        supplier_ids = {supplier_id for supplier_id in supplier_ids if supplier_id}
        result = {supplier_id: {name: False for name in CLAIM_DEFAULT_FIELDS}
                  for supplier_id in supplier_ids}
        if not supplier_ids:
            return result
        domain = fields.Domain('supplier_id', 'in', supplier_ids)
        excluded = [record_id for record_id in (exclude_ids or []) if isinstance(record_id, int)]
        if excluded:
            domain &= fields.Domain('id', 'not in', excluded)
        found = set()
        for claim in self.with_context(active_test=False).search(
                domain, order='supplier_id, id desc'):
            supplier_id = claim.supplier_id.id
            if supplier_id not in found:
                result[supplier_id] = {name: claim[name] for name in CLAIM_DEFAULT_FIELDS}
                found.add(supplier_id)
        return result

    @api.onchange('supplier_id')
    def _onchange_supplier_terms(self):
        drafts = self.filtered(lambda claim: claim.state == 'draft')
        defaults = self._last_claim_values_by_supplier(
            drafts.mapped('supplier_id').ids, exclude_ids=drafts._origin.ids)
        empty = {name: False for name in CLAIM_DEFAULT_FIELDS}
        for claim in drafts:
            claim.update(defaults.get(claim.supplier_id.id, empty))

    @api.model_create_multi
    def create(self, vals_list):
        self._require_role('user')
        clean_vals_list = []
        for vals in vals_list:
            self._validate_amount_value(vals)
            unexpected = set(vals) - self._entry_fields() - {'active'}
            if unexpected:
                raise AccessError(_('Create a draft claim without workflow values.'))
            values = {
                **self._last_claim_values_by_supplier([vals.get('supplier_id')]).get(
                    vals.get('supplier_id'), {}),
                **vals,
                'state': 'draft', 'user_id': self.env.uid,
                'company_id': self.env.company.id, 'review_round': 0,
                'document_revision': 1, 'active': True,
            }
            values['claim_reference'] = self._normalize_claim_reference(
                values.get('claim_reference'))
            clean_vals_list.append(values)
        safe_context = {key: value for key, value in self.env.context.items()
                        if not key.startswith('default_')}
        claims = super(SupplierClaimCycle, self.with_context(safe_context)).create(
            clean_vals_list)
        claims._append_current_documents(clean_vals_list)
        for claim in claims.filtered(lambda record: bool((record.secretarial_notes or '').strip())):
            claim._log_generic('secretarial_note', reason=claim.secretarial_notes.strip())
        return claims

    def write(self, vals):
        self._require_role('user')
        self._validate_amount_value(vals)
        if set(vals) == {'active'}:
            self._require_role('admin')
        elif set(vals) - self._entry_fields():
            raise AccessError(_('Only draft claim fields can be edited directly.'))
        if any(claim.state != 'draft' for claim in self):
            raise AccessError(_('Submitted claims are changed only by dynamic workflow actions.'))
        self.check_access('write')
        self.lock_for_update()
        values = dict(vals)
        if 'claim_reference' in values:
            values['claim_reference'] = self._normalize_claim_reference(values['claim_reference'])
        result = super().write(values)
        self._append_current_documents([values] * len(self))
        for claim in self:
            claim._log_generic('claim_updated', reason=_('Draft claim fields were updated.'))
        return result

    def _append_current_documents(self, values_list):
        payloads = []
        for claim, values in zip(self, values_list):
            for kind in ('attachment', 'supplier_cheque', 'tax_review',
                         'payment_request', 'bank_cheque'):
                content_field = 'attachment' if kind == 'attachment' else kind + '_attachment'
                filename_field = 'attachment_filename' if kind == 'attachment' else kind + '_filename'
                if content_field in values and claim[content_field]:
                    payloads.append({
                        'claim_id': claim.id, 'kind': kind, 'content': claim[content_field],
                        'filename': claim[filename_field], 'revision': claim.document_revision,
                        'reason': 'Document uploaded', 'user_id': self.env.uid,
                        'occurred_at': fields.Datetime.now(),
                    })
        if payloads:
            self.env['ab_supplier_claim_document']._append(payloads)

    def action_upload_documents(self, field_name, files):
        self.ensure_one()
        self._prepare_action()
        kinds = {
            'attachment': 'attachment',
            'supplier_cheque_attachment': 'supplier_cheque',
            'tax_review_attachment': 'tax_review',
            'payment_request_attachment': 'payment_request',
            'bank_cheque_attachment': 'bank_cheque',
        }
        if field_name not in kinds or not isinstance(files, list) or not files:
            raise ValidationError(_('Select at least one valid file to upload.'))
        for file in files:
            if (not isinstance(file, dict) or not isinstance(file.get('name'), str)
                    or not file['name'].strip() or not isinstance(file.get('data'), str)):
                raise ValidationError(_('Each attachment requires a filename and valid file content.'))
            try:
                content = base64.b64decode(file['data'], validate=True)
            except (ValueError, binascii.Error):
                raise ValidationError(
                    _('Each attachment requires a filename and valid file content.')) from None
            if not content:
                raise ValidationError(_('Empty attachments cannot be uploaded.'))
        kind = kinds[field_name]
        filename_field = 'attachment_filename' if kind == 'attachment' else kind + '_filename'
        with self.env.cr.savepoint():
            self.write({field_name: files[-1]['data'], filename_field: files[-1]['name']})
            if len(files) > 1:
                self.env['ab_supplier_claim_document']._append([{
                    'claim_id': self.id, 'kind': kind, 'content': file['data'],
                    'filename': file['name'], 'revision': self.document_revision,
                    'reason': 'Document uploaded', 'user_id': self.env.uid,
                    'occurred_at': fields.Datetime.now(),
                } for file in files[:-1]])
        return True

    def _workflow_write(self, vals):
        self._validate_amount_value(vals)
        return super(SupplierClaimCycle, self.sudo()).write(vals)

    @api.ondelete(at_uninstall=True)
    def _prevent_claim_deletion(self):
        raise UserError(_('Archive claims instead of deleting them.'))
