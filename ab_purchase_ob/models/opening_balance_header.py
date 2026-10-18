import uuid

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class OpeningBalanceHeader(models.Model):
    _name = 'ab_purchase_ob_header'
    _description = 'opening_balance_header'
    _rec_name = 'doc_code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _document_unique = models.Constraint('UNIQUE(store_id, purpose, doc_code)', 'Receipt document numbers must be unique per store and purpose.')

    company_id = fields.Many2one(related='store_id.company_id', store=True, index=True)
    opening_run_id = fields.Many2one('ab_purchase_ob_run', string='Opening Run', ondelete='restrict')
    correction_of_id = fields.Many2one('ab_purchase_ob_header', string='Corrected Receipt', ondelete='restrict')
    receipt_reason = fields.Char(string='Receipt Reason')
    tax_snapshot = fields.Json(readonly=True, copy=False)

    store_id = fields.Many2one(
        'ab_store', domain=[('allow_purchase', '=', True)], required=True, tracking=True)
    purpose = fields.Selection(
        [
            ('opening', 'Opening Inventory'),
            ('non_purchase_receipt', 'Non-purchase Receipt'),
        ],
        default='opening',
        required=True,
        tracking=True,
    )
    receipt_type_id = fields.Many2one(
        'ab_purchase_ob_receipt_type',
        string='Receipt Type',
        ondelete='restrict',
        tracking=True,
    )
    doc_code = fields.Char(default='0000000000', required=True, tracking=True)
    doc_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    lines_count = fields.Integer(compute='compute_totals')
    total_price = fields.Float(compute='compute_totals', digits=(12, 3))
    total_cost = fields.Float(compute='compute_totals', digits=(12, 3))
    total_tax = fields.Float(compute='compute_totals', digits=(12, 3))
    active = fields.Boolean(default=True)
    description = fields.Text()
    status = fields.Selection(
        selection=[('pending', 'Pending'), ('saved', 'Saved')],
        default='pending')
    line_ids = fields.One2many(
        comodel_name='ab_purchase_ob_line', inverse_name='header_id', required=True)

    @api.constrains('purpose', 'receipt_type_id')
    def _check_receipt_type(self):
        for rec in self:
            if rec.purpose == 'non_purchase_receipt' and not rec.receipt_type_id:
                raise ValidationError(_("Select a receipt type for non-purchase receipts."))
            if rec.purpose == 'opening' and rec.receipt_type_id:
                raise ValidationError(_("Opening inventory documents cannot use non-purchase receipt types."))

    def btn_submit_inventory(self):
        self.ensure_one()
        self.check_access('write')
        self.lock_for_update()
        self.invalidate_recordset()
        if not (
            self.env.user.has_group('base.group_system')
            or self.env.user.has_group('ab_inventory.group_inventory_manager')
        ):
            raise AccessError(_("Only inventory or purchase managers can save receipt documents into stock."))
        if self.status == 'saved':
            return True
        self._check_receipt_type()
        if not (self.receipt_reason or '').strip():
            raise ValidationError(_('Provide a receipt reason before posting stock.'))
        if self.purpose == 'opening' and not self.correction_of_id:
            run = self.opening_run_id
            if not run or run.store_id != self.store_id:
                raise ValidationError(_('Select an opening run belonging to this store.'))
            run.lock_for_update()
            run.invalidate_recordset()
            if run.state != 'open' or self.doc_date > run.cutoff_date:
                raise ValidationError(_('Opening stock must be posted within an open run and its cutoff date.'))
        if self.correction_of_id:
            if 'ab_purchase_accounting_config' in self.env.registry and self.env['ab_purchase_accounting_config'].sudo().search_count([('active', '=', True), ('company_id', '=', self.company_id.id), ('branch_id', '=', self.store_id.id), ('activation_date', '<=', self.doc_date)]):
                raise ValidationError(_('Receipt corrections with active accounting require the accounting integration phase.'))
            self.correction_of_id.lock_for_update()
            original = self.correction_of_id
            if original.status != 'saved' or original.correction_of_id or original.store_id != self.store_id or original.purpose != self.purpose:
                raise ValidationError(_('Corrections must reference a saved original receipt in the same store and purpose.'))
            self.line_ids._check_correction_limits()
        lines = self.line_ids.filtered(lambda line: line.receipt_qty > 0)
        if not lines:
            raise ValidationError(_("Add a receipt line with a positive quantity."))
        if any(line.receipt_qty < 0 for line in self.line_ids):
            raise ValidationError(_("Receipt quantities cannot be negative."))
        with self.env.cr.savepoint():
            for line in lines:
                self.env['ab_inventory_process'].inventory_write(
                    line, line.receipt_qty, self.store_id.id, sign=-1 if self.correction_of_id else 1, status='saved',
                )
            snapshot = {key: self[key] for key in ('total_price', 'total_cost', 'total_tax')}
            super(OpeningBalanceHeader, self).write({'status': 'saved', 'tax_snapshot': snapshot})
        return True

    @api.depends('line_ids', 'line_ids.receipt_qty', 'line_ids.price', 'line_ids.taxes_ids', 'line_ids.unit_cost', 'tax_snapshot')
    def compute_totals(self):
        for line in self:
            line.total_price = sum(rec.price * rec.receipt_qty for rec in line.line_ids)
            line.total_cost = sum(rec.source_id._get_purchase_tax_values(qty=rec.receipt_qty, bonus=0)['total'] for rec in line.line_ids)
            line.total_tax = sum(rec.source_id._get_purchase_tax_values(qty=rec.receipt_qty, bonus=0)['total_tax'] for rec in line.line_ids)
            if line.tax_snapshot:
                for key in ('total_price', 'total_cost', 'total_tax'):
                    line[key] = line.tax_snapshot[key]
            line.lines_count = len(line.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('tax_snapshot') for vals in vals_list):
            raise ValidationError(_('Receipt totals can only be frozen by approval.'))
        if any(vals.get('status', 'pending') != 'pending' for vals in vals_list):
            raise ValidationError(_("Create receipt documents as pending."))
        return super().create(vals_list)

    def write(self, vals):
        if 'tax_snapshot' in vals:
            raise ValidationError(_('Receipt totals can only be frozen by approval.'))
        if {'store_id', 'correction_of_id', 'purpose'} & vals.keys() and any(rec.line_ids for rec in self):
            raise ValidationError(_('Remove draft lines before changing receipt scope or purpose.'))
        if 'status' in vals:
            raise ValidationError(_("Use the Submit action to save receipt documents."))
        protected = {'store_id', 'purpose', 'receipt_type_id', 'doc_code', 'doc_date', 'line_ids', 'receipt_reason', 'opening_run_id', 'correction_of_id'}
        if protected.intersection(vals) and any(rec.status == 'saved' for rec in self):
            raise ValidationError(_("Saved receipt documents cannot be changed."))
        return super().write(vals)

    def unlink(self):
        raise ValidationError(_('Archive receipt documents instead of deleting them.'))

    def action_create_correction(self):
        self.ensure_one()
        self.check_access('read')
        if self.status != 'saved' or self.correction_of_id:
            raise ValidationError(_('Select a saved original receipt to create a correction.'))
        correction = self.create({
            'store_id': self.store_id.id, 'purpose': self.purpose,
            'correction_of_id': self.id, 'receipt_type_id': self.receipt_type_id.id,
            'opening_run_id': self.opening_run_id.id,
            'doc_code': self.doc_code + '-COR-' + uuid.uuid4().hex[:8],
            'line_ids': [fields.Command.create({'source_id': line.source_id.id, 'correction_qty': 0}) for line in self.line_ids],
        })
        return {'type': 'ir.actions.act_window', 'name': _('Correct Receipt'),
                'res_model': self._name, 'res_id': correction.id, 'views': [(False, 'form')]}
