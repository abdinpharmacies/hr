import math
from copy import deepcopy
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.ab_crm_core.models.core import _INTERNAL


class Request(models.Model):
    _name = 'ab_oms_request'
    _inherit = 'ab_crm_scoped'
    _description = 'OMS Request'
    _order = 'id desc'

    name = fields.Char(default=lambda self: str(uuid4()), required=True, readonly=True, copy=False)
    active = fields.Boolean(default=True)
    customer_id = fields.Many2one('ab_crm_customer', ondelete='restrict', check_company=True)
    conversation_id = fields.Many2one('ab_crm_conversation', ondelete='restrict', check_company=True)
    assigned_id = fields.Many2one('res.users', string='Assigned Staff', readonly=True, copy=False)
    customer_name = fields.Char(required=True)
    customer_phone = fields.Char(required=True)
    customer_address = fields.Text()
    customer_reference = fields.Integer(string='Branch Customer Reference')
    employee_reference = fields.Integer(string='Branch Employee Reference')
    is_delivery = fields.Boolean(default=True)
    delivery_instructions = fields.Text()
    line_ids = fields.One2many('ab_oms_line', 'request_id', copy=True)
    attempt_ids = fields.One2many('ab_oms_attempt', 'request_id', copy=False)
    note_ids = fields.One2many('ab_oms_note', 'request_id', copy=False)
    state = fields.Selection([('draft', 'Draft'), ('approved', 'Customer Approved'), ('submitted', 'Submitted'), ('followup', 'Follow-up')], default='draft', required=True, readonly=True)
    approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    approval_note = fields.Text(string='Customer Approval Evidence')
    promotion_reference = fields.Integer(string='Branch Promotion Reference')
    source_db_serial = fields.Integer(string='Source Database Serial')
    replacement_of = fields.Many2one('ab_oms_request', readonly=True, ondelete='restrict', copy=False)
    source_reference = fields.Char(readonly=True, copy=False, index=True)
    source_revision = fields.Integer(readonly=True, copy=False)
    source_snapshot = fields.Json(readonly=True, copy=False)
    paid_amount = fields.Monetary(readonly=True, copy=False)
    payment_references = fields.Json(readonly=True, copy=False)
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id)
    cancellation_requested = fields.Boolean(readonly=True, copy=False)
    followup_reason = fields.Selection([('lost', 'Lost Sale'), ('special', 'Special Request'), ('shortage', 'Stock Shortage'), ('other', 'Other')])
    _source_unique = models.Constraint('UNIQUE(source_reference)', 'This website request was already imported.')
    _name_unique = models.Constraint('UNIQUE(name)', 'Request reference must be unique.')

    def _protected_fields(self):
        return {'state', 'name', 'assigned_id', 'approved_by', 'approved_at', 'replacement_of', 'source_reference', 'source_revision', 'source_snapshot', 'paid_amount', 'payment_references', 'cancellation_requested'}

    @api.model_create_multi
    def create(self, values_list):
        if not _INTERNAL.get():
            for values in values_list:
                if self._protected_fields() & values.keys():
                    raise AccessError(_('Use the supported OMS workflow.'))
                values.update(state='draft', name=str(uuid4()), assigned_id=False, approved_by=False, approved_at=False,
                              replacement_of=False, source_reference=False, source_revision=0, source_snapshot=False,
                              paid_amount=0, payment_references=False, cancellation_requested=False)
        return super().create(values_list)

    def write(self, values):
        self._authorize()
        self.lock_for_update()
        if not _INTERNAL.get():
            if self._protected_fields() & values.keys():
                raise AccessError(_('Use the supported OMS workflow.'))
            if set(values) - {'active'} and any(r.state != 'draft' for r in self):
                raise UserError(_('Submitted and approved requests are frozen.'))
        return super().write(values)

    @api.constrains('customer_id', 'conversation_id', 'branch_id', 'replacement_of')
    def _check_scope(self):
        for record in self:
            for target in (record.customer_id, record.conversation_id, record.replacement_of):
                if target:
                    target.check_access('read')
                    if target.company_id != record.company_id or (target != record.replacement_of and target.branch_id != record.branch_id):
                        raise ValidationError(_('Related records must belong to the same branch.'))

    def action_claim(self):
        self._staff_action()
        self._authorize()
        self.lock_for_update()
        if any(r.assigned_id and r.assigned_id != self.env.user and not self._manager() for r in self):
            raise UserError(_('This request is already assigned.'))
        return self._internal_write({'assigned_id': self.env.uid})

    def action_approve(self):
        self._staff_action()
        self._authorize()
        self.lock_for_update()
        for record in self:
            if record.state != 'draft' or not record.approval_note or not record.assigned_id:
                raise UserError(_('Claim the draft and record customer approval first.'))
            record._validate_ready()
        return self._internal_write({'state': 'approved', 'approved_by': self.env.uid, 'approved_at': fields.Datetime.now()})

    def action_reopen(self):
        self._staff_action()
        self._authorize()
        if any(r.state != 'approved' or r.attempt_ids for r in self):
            raise UserError(_('Only an unsubmitted approval can be reopened.'))
        return self._internal_write({'state': 'draft', 'approved_by': False, 'approved_at': False})

    def _validate_ready(self):
        self.ensure_one()
        if not self.line_ids or self.customer_reference <= 0 or self.employee_reference <= 0:
            raise UserError(_('Add lines and verified branch customer and employee references.'))
        if self.currency_id != self.company_id.currency_id:
            raise UserError(_('Requests in another currency require manual review.'))
        if self.paid_amount or self.payment_references:
            raise UserError(_('Prepaid requests require manual payment reconciliation before branch submission.'))
        if self.cancellation_requested:
            raise UserError(_('Resolve the cancellation request before submission.'))
        for line in self.line_ids:
            line._check_values()
            if line.branch_product_reference <= 0 or line.unit_factor <= 0:
                raise UserError(_('Map every product and unit before submission.'))
        if self.promotion_reference and self.source_db_serial <= 0:
            raise UserError(_('A source database serial is required for promotions.'))

    def _payload(self):
        self.ensure_one()
        self._validate_ready()
        payload = {'header': {'customer_id': {'eplus_serial': self.customer_reference},
                             'employee_id': {'id': self.employee_reference},
                             'bill_customer_name': self.customer_name, 'bill_customer_phone': self.customer_phone,
                             'bill_customer_address': self.customer_address or '', 'is_delivery': self.is_delivery,
                             'delivery_instructions': self.delivery_instructions or ''},
                   'lines': [{'product_id': {'id': line.branch_product_reference}, 'qty_str': str(line.quantity),
                              'sell_price': line.price_unit, 'uom_factor': line.unit_factor,
                              'unavailable_reason': line.shortage_reason or False,
                              'unavailable_reason_other': line.shortage_detail or ''} for line in self.line_ids]}
        if self.promotion_reference:
            payload.update(promotion={'id': self.promotion_reference}, source_db_serial=self.source_db_serial)
        return payload

    def _destination(self):
        raise UserError(_('Install and configure the branch adapter before submitting.'))

    def action_submit(self):
        self._staff_action()
        self.ensure_one()
        self._authorize()
        self.lock_for_update()
        if self.attempt_ids:
            return True
        if self.state != 'approved':
            raise UserError(_('Customer approval is required before submission.'))
        values = {'request_id': self.id, 'branch_id': self.branch_id.id, 'company_id': self.company_id.id,
                  'payload': self._payload(), 'destination': self._destination(), 'revision': 1}
        token = _INTERNAL.set(True)
        try:
            self.env['ab_oms_attempt'].create(values)
            self.write({'state': 'submitted'})
        finally:
            _INTERNAL.reset(token)
        return True

    def action_followup(self):
        self._staff_action()
        self._authorize()
        if any(r.attempt_ids or not r.followup_reason for r in self):
            raise UserError(_('Choose a follow-up reason on an unsubmitted request.'))
        return self._internal_write({'state': 'followup'})

    def action_choose_replacement(self):
        self._staff_action()
        self.ensure_one()
        self._authorize()
        return {'type': 'ir.actions.act_window', 'res_model': 'ab_oms_replacement', 'view_mode': 'form',
                'target': 'new', 'context': {'default_request_id': self.id, 'default_branch_id': self.branch_id.id}}

    def action_replacement(self, branch_id=None):
        self._staff_action()
        self.ensure_one()
        self._authorize()
        self.lock_for_update()
        if not self.attempt_ids or any(a.state != 'rejected' or not a.can_edit for a in self.attempt_ids):
            raise UserError(_('Resolve the original attempt with the branch before replacing it.'))
        if self.env[self._name].search_count(fields.Domain('replacement_of', '=', self.id)):
            raise UserError(_('A replacement request already exists.'))
        branch = self.env['ab_crm_branch'].browse(branch_id) if branch_id else self.branch_id
        branch.ensure_one()
        branch.check_access('read')
        if branch.company_id != self.company_id:
            raise AccessError(_('The selected company or branch is not allowed.'))
        token = _INTERNAL.set(True)
        try:
            replacement = self.copy({'name': str(uuid4()), 'state': 'draft', 'replacement_of': self.id,
                                     'approved_by': False, 'approved_at': False, 'approval_note': False,
                                     'branch_id': branch.id, 'customer_id': False, 'conversation_id': False,
                                     'customer_reference': 0, 'employee_reference': 0, 'promotion_reference': 0,
                                     'paid_amount': self.paid_amount, 'payment_references': self.payment_references,
                                     'source_snapshot': self.source_snapshot, 'cancellation_requested': self.cancellation_requested})
            replacement.line_ids.write({'branch_product_reference': 0, 'unit_factor': 0})
            self.attempt_ids.write({'retired': True, 'queued': False})
        finally:
            _INTERNAL.reset(token)
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': replacement.id, 'view_mode': 'form'}


class Line(models.Model):
    _name = 'ab_oms_line'
    _inherit = 'ab_crm_scoped'
    _description = 'OMS Request Line'
    _rec_name = 'name'

    request_id = fields.Many2one('ab_oms_request', required=True, ondelete='restrict', check_company=True)
    name = fields.Char(required=True)
    source_product_reference = fields.Char(readonly=True)
    source_unit_reference = fields.Char(readonly=True)
    branch_product_reference = fields.Integer(string='Branch Product Reference')
    unit_factor = fields.Float(string='Branch Unit Factor', default=0)
    quantity = fields.Float(default=1, required=True)
    price_unit = fields.Float(string='Unit Price', required=True)
    shortage_reason = fields.Selection([('not_transferred', 'Not Transferred'), ('wrong_price', 'Wrong Price'), ('stocktaking_error', 'Stocktaking Error'), ('not_entered', 'Not Entered'), ('promised_customer', 'Promised to Customer'), ('other', 'Other')])
    shortage_detail = fields.Char()
    shortage_authorization = fields.Char(string='Branch Shortage Authorization')

    @api.constrains('quantity', 'price_unit', 'unit_factor', 'shortage_reason', 'shortage_authorization')
    def _check_values(self):
        for record in self:
            if any(not math.isfinite(x) for x in (record.quantity, record.price_unit, record.unit_factor)) or record.quantity <= 0 or record.price_unit < 0 or record.unit_factor < 0:
                raise ValidationError(_('Quantities and unit factors must be positive; prices cannot be negative.'))
            if record.shortage_reason and not record.shortage_authorization:
                raise ValidationError(_('Record branch authorization for stock shortages.'))

    @api.constrains('request_id', 'branch_id', 'company_id')
    def _check_scope(self):
        for record in self:
            record.request_id.check_access('read')
            if record.branch_id != record.request_id.branch_id or record.company_id != record.request_id.company_id:
                raise ValidationError(_('Related records must belong to the same branch.'))

    def _editable(self, requests):
        requests._authorize()
        requests.lock_for_update()
        if not _INTERNAL.get() and any(r.state != 'draft' for r in requests):
            raise UserError(_('Submitted and approved requests are frozen.'))
        requests._internal_write({'write_date': fields.Datetime.now()})

    @api.model_create_multi
    def create(self, values_list):
        requests = self.env['ab_oms_request'].browse([v.get('request_id') or self.env.context.get('default_request_id') for v in values_list])
        self._editable(requests)
        for values in values_list:
            request = self.env['ab_oms_request'].browse(values.get('request_id') or self.env.context.get('default_request_id'))
            values.update(branch_id=request.branch_id.id, company_id=request.company_id.id)
        return super().create(values_list)

    def write(self, values):
        self._editable(self.request_id)
        if {'request_id', 'branch_id', 'company_id'} & values.keys():
            raise AccessError(_('Request lines cannot be moved between requests.'))
        if not _INTERNAL.get() and {'source_product_reference', 'source_unit_reference'} & values.keys():
            raise AccessError(_('Website references are immutable.'))
        if 'price_unit' in values:
            for line in self:
                if line.price_unit != values['price_unit']:
                    token = _INTERNAL.set(True)
                    try:
                        self.env['ab_oms_price_history'].create({'line_id': line.id, 'branch_id': line.branch_id.id,
                            'company_id': line.company_id.id, 'old_price': line.price_unit, 'new_price': values['price_unit'],
                            'changed_by': self.env.uid, 'change_date': fields.Datetime.now()})
                    finally:
                        _INTERNAL.reset(token)
        return super().write(values)


class Attempt(models.Model):
    _name = 'ab_oms_attempt'
    _inherit = 'ab_crm_scoped'
    _description = 'OMS Submission'
    _rec_name = 'token'
    _order = 'id desc'

    request_id = fields.Many2one('ab_oms_request', required=True, ondelete='restrict', check_company=True)
    token = fields.Char(default=lambda self: str(uuid4()), required=True, readonly=True, copy=False)
    revision = fields.Integer(default=1, readonly=True, required=True)
    payload = fields.Json(required=True, readonly=True)
    destination = fields.Json(required=True, readonly=True)
    state = fields.Selection([('prepending', 'Prepending'), ('unknown', 'Unknown'), ('rejected', 'Rejected'), ('pending', 'Pending'), ('saved', 'Saved')], default='prepending', required=True, readonly=True)
    queued = fields.Boolean(default=True, readonly=True)
    retired = fields.Boolean(readonly=True)
    can_edit = fields.Boolean(readonly=True)
    branch_header_id = fields.Integer(readonly=True)
    invoice_reference = fields.Integer(readonly=True)
    result = fields.Json(readonly=True)
    history = fields.Json(readonly=True)
    last_error = fields.Text(readonly=True)
    last_success = fields.Datetime(readonly=True)
    _token_unique = models.Constraint('UNIQUE(token)', 'Submission token must be unique.')
    _request_unique = models.Constraint('UNIQUE(request_id)', 'Only one operation is allowed per request.')

    @api.model_create_multi
    def create(self, values_list):
        if not _INTERNAL.get():
            raise AccessError(_('Use Submit to create a frozen submission.'))
        return super().create(values_list)

    def write(self, values):
        if not _INTERNAL.get():
            raise AccessError(_('Submission evidence is managed by the adapter.'))
        return super().write(values)

    def action_retry(self):
        self._staff_action()
        self._authorize()
        self.lock_for_update()
        if any(r.retired or r.state not in ('unknown', 'rejected') for r in self):
            raise UserError(_('Only unresolved or rejected original submissions can be retried.'))
        return self._internal_write({'queued': True})

    def action_correct(self):
        self._staff_action()
        self.ensure_one()
        self._authorize()
        if self.state != 'rejected' or not self.can_edit or self.retired or self.queued:
            raise UserError(_('A confirmed editable rejection is required.'))
        wizard = self.env['ab_oms_correction'].create({'attempt_id': self.id,
            'promotion_reference': (self.payload.get('promotion') or {}).get('id', 0),
            'approval_note': False,
            'line_ids': [fields.Command.create({'sequence': i, 'name': str(line['product_id']['id']),
                'quantity': float(line['qty_str'])}) for i, line in enumerate(self.payload['lines'])]})
        return {'type': 'ir.actions.act_window', 'res_model': 'ab_oms_correction', 'res_id': wizard.id,
                'view_mode': 'form', 'target': 'new'}

    def correct_rejection(self, quantities, promotion_reference=False, approval_note=False):
        self._staff_action()
        self.ensure_one()
        self._authorize()
        self.lock_for_update()
        if self.state != 'rejected' or not self.can_edit or self.retired or self.queued or not isinstance(approval_note, str) or not approval_note.strip():
            raise UserError(_('A confirmed editable rejection and renewed customer approval are required.'))
        if not isinstance(quantities, list) or len(quantities) != len(self.payload['lines']):
            raise ValidationError(_('Provide one quantity for every original line.'))
        payload = deepcopy(self.payload)
        for line, quantity in zip(payload['lines'], quantities):
            if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or not math.isfinite(quantity) or quantity <= 0:
                raise ValidationError(_('Quantities must be finite positive numbers.'))
            line['qty_str'] = str(quantity)
        if promotion_reference:
            if type(promotion_reference) is not int or promotion_reference <= 0 or not self.request_id.source_db_serial:
                raise ValidationError(_('A valid promotion and source database reference are required.'))
            payload['promotion'] = {'id': promotion_reference}
            payload['source_db_serial'] = self.request_id.source_db_serial
        else:
            payload.pop('promotion', None)
        if payload == self.payload:
            raise UserError(_('The corrected revision must change quantities or promotion.'))
        history = list(self.history or []) + [{'revision': self.revision, 'payload': self.payload, 'result': self.result,
                                             'actor': self.env.uid, 'at': str(fields.Datetime.now()), 'approval': approval_note}]
        return self._internal_write({'payload': payload, 'revision': self.revision + 1, 'state': 'prepending',
                                     'history': history, 'queued': True, 'can_edit': False})


class Note(models.Model):
    _name = 'ab_oms_note'
    _inherit = 'ab_crm_scoped'
    _description = 'OMS Follow-up Note'
    _rec_name = 'body'

    request_id = fields.Many2one('ab_oms_request', required=True, ondelete='restrict', check_company=True)
    body = fields.Text(required=True)

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            request = self.env['ab_oms_request'].browse(values.get('request_id') or self.env.context.get('default_request_id'))
            request._authorize('read')
            values.update(branch_id=request.branch_id.id, company_id=request.company_id.id)
        return super().create(values_list)

    def write(self, values):
        raise UserError(_('Append a new note instead of changing history.'))


class PriceHistory(models.Model):
    _name = 'ab_oms_price_history'
    _inherit = 'ab_crm_scoped'
    _description = 'OMS Price History'

    line_id = fields.Many2one('ab_oms_line', required=True, ondelete='restrict', check_company=True)
    old_price = fields.Float(required=True)
    new_price = fields.Float(required=True)
    changed_by = fields.Many2one('res.users', required=True, readonly=True)
    change_date = fields.Datetime(required=True, readonly=True)

    @api.model_create_multi
    def create(self, values_list):
        if not _INTERNAL.get():
            raise AccessError(_('Price history is recorded automatically.'))
        return super().create(values_list)

    def write(self, values):
        raise AccessError(_('Price history is immutable.'))


class Correction(models.TransientModel):
    _name = 'ab_oms_correction'
    _description = 'OMS Rejected Submission Correction'

    attempt_id = fields.Many2one('ab_oms_attempt', required=True, readonly=True)
    line_ids = fields.One2many('ab_oms_correction_line', 'wizard_id')
    promotion_reference = fields.Integer(string='Branch Promotion Reference')
    approval_note = fields.Text(string='Renewed Customer Approval')

    def action_apply(self):
        self.ensure_one()
        self.attempt_id._authorize()
        self.attempt_id.correct_rejection(self.line_ids.sorted('sequence').mapped('quantity'), self.promotion_reference, self.approval_note)
        return {'type': 'ir.actions.act_window_close'}


class CorrectionLine(models.TransientModel):
    _name = 'ab_oms_correction_line'
    _description = 'OMS Correction Quantity'

    wizard_id = fields.Many2one('ab_oms_correction', required=True, ondelete='cascade')
    sequence = fields.Integer(required=True, readonly=True)
    name = fields.Char(readonly=True)
    quantity = fields.Float(required=True)


class Replacement(models.TransientModel):
    _name = 'ab_oms_replacement'
    _description = 'OMS Replacement Branch'

    request_id = fields.Many2one('ab_oms_request', required=True)
    branch_id = fields.Many2one('ab_crm_branch', required=True)

    def action_create(self):
        self.ensure_one()
        return self.request_id.action_replacement(self.branch_id.id)
