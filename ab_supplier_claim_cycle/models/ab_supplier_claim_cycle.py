import base64
import hashlib
import math
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

PAYMENT_NATURE = [
    ('cash', 'Cash'),
    ('check', 'Check'),
    ('bank_transfer', 'Bank Transfer'),
]
TAX_CLASSIFICATION = [
    ('through_supplier', 'Advance Payments'),
    ('tax_payment', 'Tax Payment'),
    ('withholding_tax', 'Withholding Tax'),
    ('non_tax_payment', 'Non-tax Payment'),
]

SUPPLIER_SECTION = [('medical', 'Medicine'), ('cosmo', 'Cosmetics'), ('other', 'Other')]
CLAIM_DEFAULT_FIELDS = ('type_of_invoice', 'payment_nature', 'tax_classification', 'section', 'area')

STATES = [(value, label) for value, label in (
    ('draft', 'Draft'), ('operational_review', 'Operational Review'),
    ('financial_review', 'Financial Review'), ('secretarial_preparation', 'Secretarial Preparation'),
    ('bank_accounts', 'Bank Accounts'), ('returned_secretarial', 'Returned to Secretarial'),
    ('ready_to_close', 'Ready to Close'), ('closed', 'Closed'))]
DECISIONS = [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'),
             ('deferred', 'Deferred'), ('cancelled', 'Cancelled'), ('not_required', 'Not Required')]
DEPARTMENTS = ('inventory', 'purchasing', 'tax', 'supplier_accounts', 'bank_accounts')
STAGES = dict(inventory='operational_review', purchasing='operational_review',
              tax='financial_review', supplier_accounts='financial_review', bank_accounts='bank_accounts')
GROUP_PREFIX = 'ab_supplier_claim_cycle.supplier_claim_group_'


class SupplierClaimCycle(models.Model):
    _name = 'ab_supplier_claim_cycle'
    _description = 'Supplier Claim'
    _inherit = ['mail.thread']
    _rec_name = 'supplier_id'
    _rec_names_search = ['claim_reference', 'supplier_id']
    _order = 'id desc'

    claim_reference = fields.Char(string='Claim ID', copy=False, tracking=True)
    _claim_reference_unique = models.Constraint(
        'UNIQUE(claim_reference)',
        'Claim ID must be unique.',
    )

    supplier_id = fields.Many2one(
        'ab_costcenter', required=True, ondelete='restrict', tracking=True,
        domain=fields.Domain('code', '=like', '1-%'),
    )
    num_of_invoice = fields.Integer(required=True, tracking=True)
    state = fields.Selection(STATES, default='draft', required=True, readonly=True, copy=False, index=True)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True, ondelete='set null')
    area = fields.Selection([('south', 'South'), ('north', 'North')], required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company,
                                 readonly=True, index=True)
    claim_amount = fields.Float(required=True, digits=(16, 2), tracking=True)
    amount_of_check = fields.Char(compute='_compute_legacy_amount')
    tax_discount_decision = fields.Selection([('apply', 'Apply'), ('do_not_apply', 'Do Not Apply')], copy=False)
    tax_discount_rate = fields.Float(compute='_compute_amounts', digits=(16, 2), store=True)
    tax_discount_amount = fields.Float(compute='_compute_amounts', digits=(16, 2), store=True)
    net_claim_amount = fields.Float(compute='_compute_amounts', digits=(16, 2), store=True)
    secretarial_preparation_status = fields.Selection([
        ('not_required', 'Not Required'), ('waiting', 'Waiting'), ('pending', 'Pending'),
        ('prepared', 'Prepared'), ('returned', 'Returned'), ('suspended', 'Suspended')],
        default='not_required', readonly=True, copy=False)
    preparation_started_at = fields.Datetime(readonly=True, copy=False)
    preparation_due_date = fields.Datetime(readonly=True, copy=False)
    preparation_overdue = fields.Boolean(compute='_compute_preparation_overdue')
    document_revision = fields.Integer(default=1, readonly=True, copy=False)
    payment_request_revision = fields.Integer(readonly=True, copy=False)
    bank_approval_revision = fields.Integer(readonly=True, copy=False)
    invalidated_payment_request_digest = fields.Char(readonly=True, copy=False)
    migration_gate_exception = fields.Boolean(readonly=True, copy=False)
    return_destination = fields.Selection([('secretarial', 'Secretarial'),
                                           ('supplier_accounts', 'Supplier Accounts')], readonly=True, copy=False)
    document_ids = fields.One2many('ab_supplier_claim_document', 'claim_id', readonly=True, copy=False)
    supplier_cheque_attachment = fields.Binary(attachment=False, copy=False)
    supplier_cheque_filename = fields.Char(copy=False)
    tax_review_attachment = fields.Binary(attachment=False, copy=False)
    tax_review_filename = fields.Char(copy=False)
    payment_request_attachment = fields.Binary(attachment=False, copy=False)
    payment_request_filename = fields.Char(copy=False)
    tax_decision = fields.Selection(DECISIONS, default='not_required', readonly=True, copy=False)
    tax_notes = fields.Text(copy=False)
    tax_followup_date = fields.Date(copy=False)
    can_edit_tax = fields.Boolean(compute='_compute_permissions')
    can_edit_supplier_accounts = fields.Boolean(compute='_compute_permissions')
    can_edit_bank_accounts = fields.Boolean(compute='_compute_permissions')
    can_edit_inventory = fields.Boolean(compute='_compute_permissions')
    can_edit_purchasing = fields.Boolean(compute='_compute_permissions')
    can_prepare_payment = fields.Boolean(compute='_compute_permissions')
    can_close_claim = fields.Boolean(compute='_compute_permissions')

    @api.depends('claim_amount')
    def _compute_legacy_amount(self):
        for claim in self:
            claim.amount_of_check = f'{claim.claim_amount:.2f}'

    @api.depends('claim_amount', 'tax_discount_decision')
    def _compute_amounts(self):
        for claim in self:
            amount = Decimal(str(claim.claim_amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            discount = (amount * Decimal('0.01')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if claim.tax_discount_decision == 'apply' else Decimal('0')
            claim.tax_discount_rate = 1.0
            claim.tax_discount_amount = float(discount)
            claim.net_claim_amount = float(amount - discount)

    @api.constrains('claim_amount')
    def _check_amount(self):
        for claim in self:
            if not math.isfinite(claim.claim_amount) or claim.claim_amount <= 0:
                raise ValidationError(_('The claim amount must be a positive finite number.'))

    @api.depends('preparation_due_date', 'secretarial_preparation_status', 'active')
    def _compute_preparation_overdue(self):
        for claim in self:
            claim.preparation_overdue = bool(claim.active and claim.preparation_due_date
                and claim.secretarial_preparation_status in ('pending', 'returned')
                and claim.preparation_due_date < fields.Datetime.now())

    def _role_allowed(self, role):
        if self._is_admin():
            return True
        return (not self.env.user.has_group(GROUP_PREFIX + 'reviewer')
                and self.env.user.has_group(GROUP_PREFIX + role))

    def _department_actionable(self, department):
        self.ensure_one()
        return bool(self.active and self.state == STAGES[department]
            and self[f'{department}_decision'] in ('pending', 'deferred')
            and (department != 'bank_accounts' or self.secretarial_preparation_status == 'prepared'))

    @api.depends('state', 'active', 'secretarial_preparation_status',
                 *(f'{d}_decision' for d in DEPARTMENTS))
    @api.depends_context('uid')
    def _compute_permissions(self):
        for claim in self:
            for department in DEPARTMENTS:
                claim[f'can_edit_{department}'] = self._role_allowed(department) and claim._department_actionable(department)
            claim.can_close_claim = bool(self._role_allowed('user') and claim.active and claim.state == 'ready_to_close')
            claim.can_prepare_payment = bool(self._role_allowed('user') and claim.active
                and claim.state == 'secretarial_preparation'
                and claim.secretarial_preparation_status in ('pending', 'returned'))

    type_of_invoice = fields.Selection([('original', 'Original'), ('copy', 'Copy'),
                                        ('bank_statement', 'Bank Statement')], required=True, tracking=True)
    active = fields.Boolean(default=True)
    payment_nature = fields.Selection(PAYMENT_NATURE, copy=False, tracking=True)
    tax_classification = fields.Selection(
        TAX_CLASSIFICATION, string='Tax Type', copy=False, tracking=True,
        help='Defaults from the latest claim for this cost center and remains editable in Draft.')
    section = fields.Selection(
        SUPPLIER_SECTION, copy=False, tracking=True,
        help='Defaults from the latest claim for this cost center and remains editable in Draft.')
    review_round = fields.Integer(default=0, readonly=True, copy=False)
    resume_stage = fields.Selection(STATES, readonly=True, copy=False)
    rejection_department = fields.Selection([(d, d.replace('_', ' ').title()) for d in DEPARTMENTS], readonly=True,
                                            copy=False)
    rejection_reason = fields.Text(readonly=True, copy=False)
    delivery_representative_name = fields.Char(string='Company Representative Name', copy=False)
    delivery_representative_phone = fields.Char(string='Company Representative Phone', copy=False)
    secretarial_notes = fields.Text()
    # Inline binary storage protects evidence from direct ir.attachment mutations.
    attachment = fields.Binary(string='Attachment', attachment=False, copy=False)
    cheque_attachment = fields.Binary(related='supplier_cheque_attachment', readonly=True)
    cheque_filename = fields.Char(related='supplier_cheque_filename', readonly=True)
    bank_cheque_attachment = fields.Binary(string='Cheque Attachment', attachment=False, copy=False)
    bank_cheque_filename = fields.Char(copy=False)
    history_ids = fields.One2many(
        'ab_supplier_claim_cycle.history', 'claim_id', readonly=True, copy=False)
    inventory_decision = fields.Selection(DECISIONS, default='not_required', readonly=True, copy=False)
    purchasing_decision = fields.Selection(DECISIONS, default='not_required', readonly=True, copy=False)
    supplier_accounts_decision = fields.Selection(DECISIONS, default='not_required', readonly=True, copy=False)
    bank_accounts_decision = fields.Selection(DECISIONS, default='not_required', readonly=True, copy=False)
    inventory_notes = fields.Text(copy=False)
    purchasing_notes = fields.Text(copy=False)
    supplier_accounts_notes = fields.Text(copy=False)
    bank_accounts_notes = fields.Text(copy=False)
    inventory_followup_date = fields.Date(copy=False)
    purchasing_followup_date = fields.Date(copy=False)
    supplier_accounts_followup_date = fields.Date(copy=False)
    bank_accounts_followup_date = fields.Date(copy=False)

    can_edit_supplier_section = fields.Boolean(compute='_compute_can_edit_claim_inputs')
    can_edit_correction_fields = fields.Boolean(compute='_compute_can_edit_claim_inputs')
    can_edit_payment_nature = fields.Boolean(compute='_compute_can_edit_claim_inputs')
    can_edit_open_claim_fields = fields.Boolean(compute='_compute_can_edit_claim_inputs')
    can_upload_secretarial_cheque = fields.Boolean(compute='_compute_can_upload_secretarial_cheque')

    @api.depends('state', 'active')
    def _compute_can_upload_secretarial_cheque(self):
        for claim in self:
            claim.can_upload_secretarial_cheque = False

    @api.depends('claim_reference', 'supplier_id.display_name')
    def _compute_display_name(self):
        super()._compute_display_name()
        for claim in self:
            if claim.claim_reference:
                claim.display_name = f'[{claim.claim_reference}] {claim.display_name}'

    @api.model
    def _normalize_claim_reference(self, value):
        return (value or '').strip().upper() or False

    @api.depends('state', 'active', 'resume_stage')
    @api.depends_context('uid')
    def _compute_can_edit_claim_inputs(self):
        for claim in self:
            open_permitted = bool(self._role_allowed('user') and claim.active and claim.state != 'closed')
            permitted = open_permitted and claim.state in ('draft', 'returned_secretarial')
            claim.can_edit_supplier_section = permitted and claim.state == 'draft'
            claim.can_edit_correction_fields = permitted
            claim.can_edit_payment_nature = open_permitted
            claim.can_edit_open_claim_fields = open_permitted

    can_edit_current_review = fields.Boolean(compute='_compute_can_edit_current_review')

    @api.depends('state', 'active', *(f'{d}_decision' for d in DEPARTMENTS))
    @api.depends_context('uid')
    def _compute_can_edit_current_review(self):
        for claim in self:
            claim.can_edit_current_review = any(self._role_allowed(d) and claim._department_actionable(d)
                                                for d in DEPARTMENTS)

    note_history_ids = fields.One2many(
        'ab_supplier_claim_cycle.history', compute='_compute_note_history', readonly=True)

    exception_history_ids = fields.One2many(
        'ab_supplier_claim_cycle.history', compute='_compute_note_history', readonly=True)

    @api.depends('history_ids', 'history_ids.display_note', 'history_ids.event', 'history_ids.decision')
    def _compute_note_history(self):
        for claim in self:
            claim.note_history_ids = claim.history_ids.filtered(
                lambda entry: bool(entry.display_note))
            claim.exception_history_ids = claim.history_ids.filtered(
                lambda entry: entry.event == 'decision' and entry.decision in ('rejected', 'deferred'))

    timeline_tax_exception_ids = fields.One2many('ab_supplier_claim_cycle.history', compute='_compute_timeline_exceptions')
    timeline_tax = fields.Text(compute='_compute_timeline_details')
    timeline_tax_date = fields.Datetime(compute='_compute_timeline_details')

    timeline_inventory_exception_ids = fields.One2many(
        'ab_supplier_claim_cycle.history', compute='_compute_timeline_exceptions')
    timeline_purchasing_exception_ids = fields.One2many(
        'ab_supplier_claim_cycle.history', compute='_compute_timeline_exceptions')
    timeline_supplier_accounts_exception_ids = fields.One2many(
        'ab_supplier_claim_cycle.history', compute='_compute_timeline_exceptions')
    timeline_bank_accounts_exception_ids = fields.One2many(
        'ab_supplier_claim_cycle.history', compute='_compute_timeline_exceptions')

    @api.depends('history_ids.event', 'history_ids.department', 'history_ids.decision')
    def _compute_timeline_exceptions(self):
        for claim in self:
            exceptions = claim.history_ids.filtered(
                lambda entry: entry.event == 'decision' and entry.decision in ('deferred', 'rejected'))
            for department in DEPARTMENTS:
                claim[f'timeline_{department}_exception_ids'] = exceptions.filtered(
                    lambda entry: entry.department == department).sorted('id')

    timeline_draft = fields.Text(compute='_compute_timeline_details')
    timeline_draft_date = fields.Datetime(compute='_compute_timeline_details')
    timeline_inventory = fields.Text(compute='_compute_timeline_details')
    timeline_inventory_date = fields.Datetime(compute='_compute_timeline_details')
    timeline_purchasing = fields.Text(compute='_compute_timeline_details')
    timeline_purchasing_date = fields.Datetime(compute='_compute_timeline_details')
    timeline_supplier_accounts = fields.Text(compute='_compute_timeline_details')
    timeline_supplier_accounts_date = fields.Datetime(compute='_compute_timeline_details')
    timeline_bank_accounts = fields.Text(compute='_compute_timeline_details')
    timeline_bank_accounts_date = fields.Datetime(compute='_compute_timeline_details')
    timeline_closure = fields.Text(compute='_compute_timeline_details')
    timeline_closure_date = fields.Datetime(compute='_compute_timeline_details')

    @api.depends('history_ids', 'history_ids.user_id.name', 'history_ids.occurred_at',
                 'history_ids.event', 'history_ids.department', 'create_uid.name', 'create_date')
    @api.depends_context('lang', 'tz')
    def _compute_timeline_details(self):
        for claim in self:
            latest = {}
            for event in claim.history_ids.sorted('id', reverse=True):
                stage = False
                if event.event == 'decision' and event.department in DEPARTMENTS:
                    stage = event.department
                elif event.event == 'closed':
                    stage = 'closure'
                elif event.event in ('resubmitted', 'secretarial_note'):
                    stage = 'draft'
                if stage and stage not in latest:
                    latest[stage] = event
            for stage in ('draft', *DEPARTMENTS, 'closure'):
                event = latest.get(stage)
                lines = []
                date = False
                if event:
                    lines = [event.user_id.display_name]
                    date = event.occurred_at
                elif stage == 'draft' and claim.create_date:
                    lines = [claim.create_uid.display_name]
                    date = claim.create_date
                claim['timeline_' + stage + '_date'] = date
                claim['timeline_' + stage] = '\n'.join(lines) or False

    def _last_claim_values_by_supplier(self, supplier_ids, exclude_ids=None):
        supplier_ids = {supplier_id for supplier_id in supplier_ids if supplier_id}
        exclude_ids = [record_id for record_id in (exclude_ids or []) if isinstance(record_id, int)]
        empty_values = {name: False for name in CLAIM_DEFAULT_FIELDS}
        result = {supplier_id: dict(empty_values) for supplier_id in supplier_ids}
        if not supplier_ids:
            return result

        domain = fields.Domain('supplier_id', 'in', supplier_ids)
        if exclude_ids:
            domain &= fields.Domain('id', 'not in', exclude_ids)
        previous_claims = self.with_context(active_test=False).search(
            domain,
            order='supplier_id, id desc',
        )
        found = set()
        for previous_claim in previous_claims:
            supplier_id = previous_claim.supplier_id.id
            if supplier_id not in found:
                result[supplier_id] = {
                    name: previous_claim[name]
                    for name in CLAIM_DEFAULT_FIELDS
                }
                found.add(supplier_id)
        return result

    @api.onchange('supplier_id')
    def _onchange_supplier_terms(self):
        draft_claims = self.filtered(lambda claim: claim.state == 'draft')
        values_by_supplier = self._last_claim_values_by_supplier(
            draft_claims.mapped('supplier_id').ids,
            exclude_ids=draft_claims._origin.ids,
        )
        empty_values = {name: False for name in CLAIM_DEFAULT_FIELDS}
        for claim in draft_claims:
            claim.update(values_by_supplier.get(claim.supplier_id.id, empty_values))

    @api.constrains(*(f'{department}_{suffix}' for department in DEPARTMENTS
                      for suffix in ('decision', 'followup_date')))
    def _check_deferred_details(self):
        for claim in self:
            for department in DEPARTMENTS:
                if claim[f'{department}_decision'] == 'deferred':
                    if not claim[f'{department}_followup_date']:
                        raise ValidationError(_('A deferred review must retain its follow-up date.'))

    def _is_admin(self):
        return self.env.su or self.env.user.has_group(GROUP_PREFIX + 'admin') or self.env.user.has_group(
            'base.group_system')

    def _require_role(self, role):
        if not self._role_allowed(role):
            raise AccessError(_('You are not authorized for this workflow action.'))

    def _prepare_action(self):
        self.check_access('write')
        self.lock_for_update()
        self.invalidate_recordset()
        self.check_access('write')
        if any(not c.active or c.state == 'closed' for c in self):
            raise UserError(_('Closed or archived claims cannot be changed.'))

    @api.model
    def _protected_fields(self):
        return {'state', 'user_id', 'company_id', 'review_round', 'resume_stage', 'rejection_department',
                'rejection_reason', 'history_ids', 'document_ids', 'tax_discount_rate', 'tax_discount_amount',
                'net_claim_amount', 'secretarial_preparation_status', 'preparation_started_at',
                'preparation_due_date', 'document_revision', 'payment_request_revision',
                'bank_approval_revision', 'migration_gate_exception', 'return_destination',
                'amount_of_check', 'cheque_attachment', 'cheque_filename', 'invalidated_payment_request_digest'} | {f'{d}_decision' for d in DEPARTMENTS}

    @api.model
    def _entry_fields(self):
        return {'supplier_id', 'num_of_invoice', 'area', 'claim_amount', 'type_of_invoice',
                'secretarial_notes', 'attachment', 'delivery_representative_name',
                'delivery_representative_phone', 'claim_reference', 'tax_classification',
                'section', 'payment_nature'}

    @api.model_create_multi
    def create(self, vals_list):
        self._require_role('user')
        clean = []
        for vals in vals_list:
            self._validate_amount_value({'claim_amount': vals.get('claim_amount')})
            harmless = {'active': True, **{kind + '_filename': False for kind in ('supplier_cheque', 'tax_review', 'payment_request', 'bank_cheque')}}
            if any(name not in harmless or value != harmless[name]
                   for name, value in vals.items() if name not in self._entry_fields()):
                raise AccessError(_('Create a draft claim without workflow values.'))
            values = {**self._last_claim_values_by_supplier([vals.get('supplier_id')]).get(vals.get('supplier_id'), {}), **vals}
            values.update(state='draft', user_id=self.env.uid, company_id=self.env.company.id,
                          review_round=0, active=True, document_revision=1,
                          secretarial_preparation_status='not_required')
            values['claim_reference'] = self._normalize_claim_reference(values.get('claim_reference'))
            clean.append(values)
        safe_context = {key: value for key, value in self.env.context.items() if not key.startswith('default_')}
        claims = super(SupplierClaimCycle, self.with_context(safe_context)).create(clean)
        claims._record_secretarial_notes()
        return claims

    def write(self, vals):
        self._validate_amount_value(vals)
        if set(vals) & self._protected_fields():
            raise AccessError(_('Use the validated workflow actions to change decisions or stages.'))
        self.check_access('write')
        self.lock_for_update()
        self.invalidate_recordset()
        self.check_access('write')
        if set(vals) == {'active'}:
            self._require_role('admin')
            result = super().write(vals)
            self._log('archived' if not vals['active'] else 'restored')
            return result
        self._prepare_action()
        for claim in self:
            allowed = set()
            if claim.can_edit_correction_fields:
                allowed = self._entry_fields() - {'supplier_id', 'section', 'payment_nature'}
                if claim.state == 'draft':
                    allowed = self._entry_fields()
            if claim.can_edit_open_claim_fields:
                allowed |= {'supplier_id', 'payment_nature', 'type_of_invoice'}
            for department in DEPARTMENTS:
                if self._role_allowed(department) and claim._department_actionable(department):
                    allowed |= {f'{department}_notes', f'{department}_followup_date'}
                    if department == 'supplier_accounts':
                        allowed |= {'supplier_cheque_attachment', 'supplier_cheque_filename'}
                    elif department == 'tax':
                        allowed |= {'tax_review_attachment', 'tax_review_filename', 'tax_discount_decision'}
                    elif department == 'bank_accounts':
                        allowed |= {'bank_cheque_attachment', 'bank_cheque_filename'}
            if claim.can_prepare_payment:
                allowed |= {'payment_request_attachment', 'payment_request_filename', 'secretarial_notes'}
            if set(vals) - allowed:
                raise AccessError(_('You may only edit the fields assigned to your current stage.'))
        draft_supplier_changes = self.filtered(
            lambda claim: claim.state == 'draft' and 'supplier_id' in vals
            and claim.supplier_id.id != vals['supplier_id'])
        supplier_defaults = (self._last_claim_values_by_supplier([vals['supplier_id']], exclude_ids=self.ids)
                             if draft_supplier_changes else {})
        review_changes = {}
        for claim in self.filtered(lambda record: record.state != 'draft'):
            changes = []
            for name in ('supplier_id', 'payment_nature', 'type_of_invoice'):
                if name not in vals:
                    continue
                old_value = claim[name].id if name == 'supplier_id' else claim[name]
                if old_value != vals[name]:
                    if name == 'supplier_id':
                        supplier = self.env['ab_costcenter'].browse(vals[name]).exists()
                        if not supplier or not supplier.active:
                            raise ValidationError(_('Select an active supplier.'))
                        old_label, new_label = claim.supplier_id.display_name, supplier.display_name
                    else:
                        labels = dict(claim._fields[name]._description_selection(self.env))
                        old_label, new_label = labels.get(old_value, old_value), labels.get(vals[name], vals[name])
                    changes.append('%s: %s → %s' % (
                        claim._fields[name].get_description(self.env)['string'], old_label, new_label))
            if changes:
                if not vals.get('payment_nature', claim.payment_nature):
                    raise ValidationError(_('Select a payment nature before submitting the claim.'))
                reason = _('Claim details changed: %(changes)s. Previous approvals and payment documents require review.',
                           changes='; '.join(changes))
                digest = (hashlib.sha256(base64.b64decode(claim.payment_request_attachment)).hexdigest()
                          if claim.payment_request_attachment else claim.invalidated_payment_request_digest)
                review_changes[claim.id] = (claim.state, reason, digest)
                for kind in ('supplier_cheque', 'tax_review', 'payment_request', 'bank_cheque'):
                    if claim[kind + '_attachment']:
                        claim._snapshot_document(kind, reason)
        if 'claim_reference' in vals:
            vals = {**vals, 'claim_reference': self._normalize_claim_reference(vals['claim_reference'])}
        for claim in self:
            if vals.get('payment_request_attachment') and claim.invalidated_payment_request_digest:
                digest = hashlib.sha256(base64.b64decode(vals['payment_request_attachment'])).hexdigest()
                if digest == claim.invalidated_payment_request_digest:
                    raise ValidationError(_('Upload a corrected payment request; the invalidated document cannot be reused.'))
            if vals.get('supplier_cheque_attachment') and claim.supplier_cheque_attachment:
                claim._workflow_write({'document_revision': claim.document_revision + 1})
        result = super().write(vals)
        if draft_supplier_changes:
            defaults = {name: value for name, value in supplier_defaults.get(vals['supplier_id'], {}).items()
                        if name not in vals and value}
            if defaults:
                draft_supplier_changes._workflow_write(defaults)
        for claim in self:
            for kind in ('supplier_cheque', 'tax_review', 'payment_request', 'bank_cheque'):
                if (kind + '_attachment' in vals or kind + '_filename' in vals) and claim[kind + '_attachment']:
                    claim._snapshot_document(kind, 'Document uploaded')
            if 'payment_request_attachment' in vals:
                claim._workflow_write({'payment_request_revision': claim.document_revision if vals['payment_request_attachment'] else 0})
            if claim.state == 'returned_secretarial' and set(vals) & {'claim_amount', 'tax_classification'}:
                claim._workflow_write(claim._financial_reset_values())
            if claim.id in review_changes:
                old_state, reason, digest = review_changes[claim.id]
                claim._restart_changed_claim_reviews(old_state, reason, digest)
        if 'secretarial_notes' in vals:
            self._record_secretarial_notes()
        return result

    def _restart_changed_claim_reviews(self, old_state, reason, invalidated_digest):
        self.ensure_one()
        values = self._financial_reset_values()
        values.update(
            state='financial_review' if self.payment_nature == 'cash' else 'operational_review',
            review_round=self.review_round + 1, document_revision=self.document_revision + 1,
            resume_stage=False, rejection_department=False, rejection_reason=False, return_destination=False,
            secretarial_preparation_status='waiting', preparation_started_at=False, preparation_due_date=False,
            invalidated_payment_request_digest=invalidated_digest)
        for department in ('inventory', 'purchasing'):
            values[department + '_decision'] = 'not_required' if self.payment_nature == 'cash' else 'pending'
        for kind in ('supplier_cheque', 'tax_review', 'payment_request', 'bank_cheque'):
            values[kind + '_attachment'] = False
            values[kind + '_filename'] = False
        self._workflow_write(values)
        self._log('claim_updated', old_state, reason=reason)

    def _snapshot_document(self, kind, reason):
        self.ensure_one()
        self.env['ab_supplier_claim_document']._append({
            'claim_id': self.id, 'kind': kind, 'content': self[kind + '_attachment'],
            'filename': self[kind + '_filename'], 'revision': self.document_revision,
            'reason': reason, 'user_id': self.env.uid, 'occurred_at': fields.Datetime.now()})

    @api.ondelete(at_uninstall=True)
    def _prevent_claim_deletion(self):
        raise UserError(_('Archive claims instead of deleting them.'))

    @api.model
    def _validate_amount_value(self, vals):
        if 'claim_amount' in vals:
            value = vals['claim_amount']
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValidationError(_('The claim amount must be a positive finite number.'))

    def _workflow_write(self, vals):
        self._validate_amount_value(vals)
        # Private RPC-inaccessible bypass, never controlled by a context flag.
        return super(SupplierClaimCycle, self.sudo()).write(vals)

    def _history_values(self, event, from_state=None, department=False, decision=False, reason=False,
                        followup_date=False):
        self.ensure_one()
        return {
            'claim_id': self.id, 'event': event, 'from_state': from_state or self.state, 'to_state': self.state,
            'department': department, 'decision': decision, 'reason': reason, 'followup_date': followup_date,
            'review_round': self.review_round, 'user_id': self.env.uid, 'occurred_at': fields.Datetime.now(),
            **{f'{d}_decision': self[f'{d}_decision'] for d in DEPARTMENTS},
            'tax_classification': self.tax_classification, 'section': self.section,
            'document_revision': self.document_revision, 'return_destination': self.return_destination,
            'preparation_status': self.secretarial_preparation_status,
            'notes': ((self[f'{department}_notes'] or '').strip() or False)
            if event == 'decision' and department in DEPARTMENTS else False,
        }

    def _log(self, event, from_state=None, department=False, decision=False, reason=False, followup_date=False):
        self.env['ab_supplier_claim_cycle.history']._append([
            claim._history_values(event, from_state, department, decision, reason, followup_date) for claim in self])

    def _record_secretarial_notes(self):
        self.env['ab_supplier_claim_cycle.history']._append([
            claim._history_values('secretarial_note', department='secretarial', reason=claim.secretarial_notes.strip())
            for claim in self if (claim.secretarial_notes or '').strip()])

    def _financial_reset_values(self):
        self.ensure_one()
        return dict(tax_decision='pending' if self.tax_classification != 'non_tax_payment' else 'not_required',
                    supplier_accounts_decision='pending', tax_discount_decision=False,
                    bank_accounts_decision='not_required' if self.payment_nature == 'cash' else 'pending',
                    payment_request_attachment=False, payment_request_filename=False, payment_request_revision=0,
                    bank_approval_revision=0, migration_gate_exception=False)

    def action_submit(self):
        self._require_role('user')
        self._prepare_action()
        for claim in self:
            if claim.state not in ('draft', 'returned_secretarial'):
                raise UserError(_('Only draft or returned claims can be submitted.'))
            if not claim.payment_nature or not claim.tax_classification or not claim.supplier_id.active:
                raise ValidationError(_('Select an active supplier, payment nature and tax type.'))
            old_state = claim.state
            stage = ('financial_review' if claim.payment_nature == 'cash' else 'operational_review') if old_state == 'draft' else claim.resume_stage
            if stage not in ('operational_review', 'financial_review'):
                raise ValidationError(_('The claim has no valid review stage to resume.'))
            vals = dict(state=stage, review_round=claim.review_round + 1, resume_stage=False,
                        rejection_department=False, rejection_reason=False, secretarial_preparation_status='waiting')
            vals.update(claim._financial_reset_values())
            for department in ('inventory', 'purchasing'):
                vals[department + '_decision'] = ('not_required' if claim.payment_nature == 'cash' else
                    'approved' if claim[department + '_decision'] == 'approved' else 'pending')
            claim._workflow_write(vals)
            claim._log('submitted' if old_state == 'draft' else 'resubmitted', old_state)
        return True

    def _preparation_values(self):
        self.ensure_one()
        calendar = self.company_id.resource_calendar_id
        if not calendar:
            raise ValidationError(_('Configure the company working calendar.'))
        started = fields.Datetime.now()
        due = calendar.plan_days(self.company_id.supplier_claim_secretarial_sla_days,
                                 started + timedelta(days=1), compute_leaves=True)
        if not due:
            raise ValidationError(_('The working calendar has no preparation deadline.'))
        return dict(state='secretarial_preparation', secretarial_preparation_status='pending',
                    preparation_started_at=started, preparation_due_date=due,
                    payment_request_attachment=False, payment_request_filename=False,
                    payment_request_revision=0, bank_approval_revision=0)

    def _validate_preparation(self):
        self.ensure_one()
        if self.supplier_accounts_decision != 'approved' or self.tax_decision not in ('approved', 'not_required'):
            raise ValidationError(_('Financial approvals are required before payment preparation.'))
        if self.tax_decision == 'approved' and not self.tax_review_attachment:
            raise ValidationError(_('A tax review attachment is required.'))
        if self.payment_nature == 'check' and not self.supplier_cheque_attachment:
            raise ValidationError(_('A supplier cheque attachment is required.'))
        if not self.payment_request_attachment or self.payment_request_revision != self.document_revision:
            raise ValidationError(_('Upload a payment request for the current document revision.'))

    def action_prepare_payment(self):
        self._require_role('user')
        self._prepare_action()
        for claim in self:
            if not claim.can_prepare_payment:
                raise UserError(_('Payment preparation is not pending.'))
            claim._validate_preparation()
            claim._workflow_write(dict(secretarial_preparation_status='prepared',
                state='ready_to_close' if claim.payment_nature == 'cash' else 'bank_accounts',
                bank_accounts_decision='not_required' if claim.payment_nature == 'cash' else 'pending'))
            claim._log('prepared', 'secretarial_preparation')
        return True

    def action_decide(self, department, decision, reason=None, followup_date=None,
                      return_destination=None, affects_tax=False):
        if department not in DEPARTMENTS or decision not in ('approved', 'rejected', 'deferred'):
            raise ValidationError(_('Invalid department decision.'))
        self._require_role(department)
        self._prepare_action()
        for claim in self:
            if not claim._department_actionable(department):
                raise UserError(_('This department has no pending decision in the current stage.'))
            decision_reason = (reason or '').strip() if decision != 'approved' else False
            followup = (fields.Date.to_date(followup_date) if decision == 'deferred'
                        else claim[f'{department}_followup_date'])
            if decision in ('rejected', 'deferred') and not decision_reason:
                raise ValidationError(_('A reason is required for rejection or deferral.'))
            if decision == 'deferred' and (not followup or followup < fields.Date.context_today(claim)):
                raise ValidationError(_('Deferral requires a follow-up date today or later.'))
            old_state = claim.state
            vals = {f'{department}_decision': decision, f'{department}_followup_date': followup}
            if decision == 'approved':
                if department == 'tax' and (not claim.tax_discount_decision or not claim.tax_review_attachment):
                    raise ValidationError(_('Select the tax discount decision and upload the tax review attachment.'))
                if department == 'supplier_accounts':
                    if claim.tax_decision not in ('approved', 'not_required'):
                        raise ValidationError(_('Tax approval is required before Supplier Accounts approval.'))
                    if claim.payment_nature == 'check' and not claim.supplier_cheque_attachment:
                        raise ValidationError(_('A supplier cheque attachment is required.'))
                    vals.update(claim._preparation_values())
                elif department in ('inventory', 'purchasing'):
                    other = 'purchasing' if department == 'inventory' else 'inventory'
                    if claim[other + '_decision'] == 'approved':
                        vals['state'] = 'financial_review'
                elif department == 'bank_accounts':
                    if not claim.migration_gate_exception:
                        claim._validate_preparation()
                    vals.update(state='ready_to_close', bank_approval_revision=claim.document_revision)
            elif decision == 'rejected':
                vals.update(rejection_department=department, rejection_reason=decision_reason)
                if department == 'bank_accounts':
                    if return_destination not in ('secretarial', 'supplier_accounts'):
                        raise ValidationError(_('Choose a return destination.'))
                    vals.update(return_destination=return_destination, migration_gate_exception=False,
                        payment_request_attachment=False, payment_request_filename=False,
                        payment_request_revision=0, bank_approval_revision=0,
                        invalidated_payment_request_digest=hashlib.sha256(base64.b64decode(claim.payment_request_attachment)).hexdigest() if claim.payment_request_attachment else False)
                    if return_destination == 'secretarial':
                        vals.update(state='secretarial_preparation', secretarial_preparation_status='returned')
                    else:
                        vals.update(state='financial_review', supplier_accounts_decision='pending',
                                    secretarial_preparation_status='suspended')
                        if affects_tax:
                            vals.update(claim._financial_reset_values())
                else:
                    vals.update(state='returned_secretarial', resume_stage=old_state,
                                secretarial_preparation_status='suspended')
                    if department in ('inventory', 'purchasing'):
                        other = 'purchasing' if department == 'inventory' else 'inventory'
                        if claim[other + '_decision'] in ('pending', 'deferred'):
                            vals[other + '_decision'] = 'cancelled'
                    else:
                        other = 'supplier_accounts' if department == 'tax' else 'tax'
                        if claim[other + '_decision'] != 'not_required':
                            vals[other + '_decision'] = 'cancelled'
            claim._workflow_write(vals)
            claim._log('decision', old_state, department, decision, decision_reason, followup)
        return True

    def action_replace_supplier_document(self, content, filename, reason, claim_amount=None, tax_classification=None):
        self.ensure_one()
        self._require_role('admin')
        self._prepare_action()
        if not content or not filename or not (reason or '').strip():
            raise ValidationError(_('A replacement document, filename and reason are required.'))
        if self.state not in ('financial_review', 'secretarial_preparation', 'bank_accounts', 'ready_to_close'):
            raise UserError(_('Supplier document replacement requires financial review or payment preparation.'))
        old_state = self.state
        if self.supplier_cheque_attachment:
            self._snapshot_document('supplier_cheque', reason)
        invalidated_digest = hashlib.sha256(base64.b64decode(self.payment_request_attachment)).hexdigest() if self.payment_request_attachment else self.invalidated_payment_request_digest
        vals = dict(invalidated_payment_request_digest=invalidated_digest, supplier_cheque_attachment=content, supplier_cheque_filename=filename,
                    document_revision=self.document_revision + 1, migration_gate_exception=False,
                    payment_request_attachment=False, payment_request_filename=False,
                    payment_request_revision=0, bank_approval_revision=0,
                    bank_accounts_decision='not_required' if self.payment_nature == 'cash' else 'pending')
        if claim_amount is not None or tax_classification is not None:
            if claim_amount is not None:
                vals['claim_amount'] = claim_amount
            if tax_classification is not None:
                vals['tax_classification'] = tax_classification
            self._workflow_write(vals)
            vals = self._financial_reset_values()
            vals.update(state='financial_review', secretarial_preparation_status='suspended')
        elif self.state in ('secretarial_preparation', 'bank_accounts', 'ready_to_close'):
            vals.update(self._preparation_values())
        self._workflow_write(vals)
        self._snapshot_document('supplier_cheque', reason)
        self._log('document_replaced', old_state, reason=reason)
        return True

    def action_close(self):
        self._require_role('user')
        self._prepare_action()
        if any(c.state != 'ready_to_close' for c in self):
            raise UserError(_('Only claims ready to close can be closed.'))
        self._workflow_write({'state': 'closed'})
        self._log('closed', 'ready_to_close')
        return True

    def action_department_decision(self):
        department = self.env.context.get('claim_department')
        decision = self.env.context.get('claim_decision')
        if decision == 'approved':
            return self.action_decide(department, decision)
        self.ensure_one()
        if department not in DEPARTMENTS or decision not in ('rejected', 'deferred'):
            raise ValidationError(_('Invalid department decision.'))
        self._require_role(department)
        self._prepare_action()
        if self.state != STAGES[department] or self[f'{department}_decision'] not in ('pending', 'deferred'):
            raise UserError(_('This department has no pending decision in the current stage.'))
        wizard = self.env['ab_supplier_claim_cycle.decision.wizard'].create({
            'claim_id': self.id, 'department': department, 'decision': decision,
            'reason': False, 'review_round': self.review_round,
            'history_revision': max(self.history_ids.ids, default=0),
            'followup_date': (self[f'{department}_followup_date'] or fields.Date.context_today(self))
            if decision == 'deferred' else False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Claim') if decision == 'rejected' else _('Defer Claim'),
            'res_model': wizard._name, 'res_id': wizard.id,
            'view_mode': 'form', 'target': 'new',
        }

    def action_open_document_replacement(self):
        self.ensure_one()
        self._require_role('admin')
        self._prepare_action()
        return {'type': 'ir.actions.act_window', 'name': _('Replace Supplier Document'),
                'res_model': 'ab_supplier_claim_document_replacement', 'view_mode': 'form',
                'target': 'new', 'context': {'default_claim_id': self.id}}
