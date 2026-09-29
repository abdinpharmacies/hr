from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class OpeningBalanceHeader(models.Model):
    _name = 'ab_purchase_ob_header'
    _description = 'opening_balance_header'
    _inherit = ['mail.thread', 'mail.activity.mixin']

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
        if not (
            self.env.user.has_group('base.group_system')
            or self.env.user.has_group('ab_inventory.group_inventory_manager')
            or self.env.user.has_group('ab_purchase.group_ab_purchase_manager')
        ):
            raise AccessError(_("Only inventory or purchase managers can save receipt documents into stock."))
        if self.status == 'saved':
            return True
        self._check_receipt_type()
        lines = self.line_ids.filtered(lambda line: line.qty > 0)
        if not lines:
            raise ValidationError(_("Add a receipt line with a positive quantity."))
        if any(line.qty < 0 for line in self.line_ids):
            raise ValidationError(_("Receipt quantities cannot be negative."))
        with self.env.cr.savepoint():
            for line in lines:
                self.env['ab_inventory_process'].inventory_write(
                    line, line.qty, self.store_id.id, status='saved',
                )
            super(OpeningBalanceHeader, self).write({'status': 'saved'})
        return True

    @api.depends('line_ids', 'line_ids.qty', 'line_ids.price', 'line_ids.taxes_ids', 'line_ids.unit_cost')
    def compute_totals(self):
        for line in self:
            line.total_price = sum(rec.price * rec.qty for rec in line.line_ids)
            line.total_cost = sum(rec.unit_cost * rec.qty for rec in line.line_ids)
            line.total_tax = sum(rec.unit_taxes_value * rec.qty for rec in line.line_ids)
            line.lines_count = len(line.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('status', 'pending') != 'pending' for vals in vals_list):
            raise ValidationError(_("Create receipt documents as pending."))
        return super().create(vals_list)

    def write(self, vals):
        if 'status' in vals:
            raise ValidationError(_("Use the Submit action to save receipt documents."))
        protected = {'store_id', 'purpose', 'receipt_type_id', 'doc_code', 'doc_date', 'line_ids'}
        if protected.intersection(vals) and any(rec.status == 'saved' for rec in self):
            raise ValidationError(_("Saved receipt documents cannot be changed."))
        return super().write(vals)
