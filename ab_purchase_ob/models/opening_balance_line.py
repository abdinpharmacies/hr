import math

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Opening_Balance_Details(models.Model):
    _name = 'ab_purchase_ob_line'
    _description = 'opening_balance_details'
    _rec_name = 'product_id'
    _inherits = {'ab_product_source': 'source_id'}

    source_id = fields.Many2one(
        'ab_product_source', required=True, delegate=True, ondelete='cascade')
    header_id = fields.Many2one(
        'ab_purchase_ob_header', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='header_id.company_id', store=True, index=True)
    correction_qty = fields.Float(string='Correction Quantity')
    receipt_qty = fields.Float(compute='_compute_receipt_qty')

    @api.depends('qty', 'correction_qty', 'header_id.correction_of_id')
    def _compute_receipt_qty(self):
        for line in self:
            line.receipt_qty = line.correction_qty if line.header_id.correction_of_id else line.qty

    header_status = fields.Selection(related='header_id.status')

    @api.onchange('no_expiry')
    def _onchange_no_expiry(self):
        if self.no_expiry:
            self.exp_date = False

    @api.onchange('product_id')
    def _onchange_product(self):
        self.uom_id = self.product_id.unit_l_id.id

    @api.onchange('product_id')
    def _on_change_product_id(self):
        for line in self:
            domain = [('product_id', '=', line.product_id.id)]
            product_params = self.search(
                domain, order='create_date desc', limit=1)
            if not product_params:
                domain = [('product_id', '=', line.product_id.id)]
                product_params = self.search(
                    domain, order='create_date desc', limit=1)
            line.price = product_params.price
            line.purchase_price = product_params.purchase_price
            line.taxes_ids = product_params.taxes_ids or self.env['ab_taxes'].search([
                ('name', '=', 'Exempt')])

    @api.constrains('qty')
    def _check_qty(self):
        for line in self:
            if line.qty < 0:
                raise ValidationError(_("Receipt quantities cannot be negative."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            header = self.env['ab_purchase_ob_header'].browse(vals.get('header_id'))
            if header.exists() and header.status == 'saved':
                raise ValidationError(_("Saved receipt lines cannot be changed."))
        records = super().create(vals_list)
        for line in records:
            if not line.header_id.correction_of_id:
                line.source_id._bind_origin(line.header_id.store_id, line.header_id._name, line.header_id.id, 'opening' if line.header_id.purpose == 'opening' else 'other')
        records._check_correction_sources()
        return records

    def write(self, vals):
        if any(line.header_id.status == 'saved' for line in self):
            raise ValidationError(_("Saved receipt lines cannot be changed."))
        if 'header_id' in vals and self.env['ab_purchase_ob_header'].browse(vals['header_id']).status == 'saved':
            raise ValidationError(_('Saved receipt lines cannot be changed.'))
        with self.env.cr.savepoint():
            expiry_values = {key: vals[key] for key in ('exp_date', 'no_expiry') if key in vals}
            if expiry_values:
                self.check_access('write')
                sources = (self.env['ab_product_source'].browse(vals['source_id'])
                           if 'source_id' in vals else self.mapped('source_id'))
                sources.write(expiry_values)
                vals = {key: value for key, value in vals.items() if key not in expiry_values}
            result = super().write(vals)
            if {'header_id', 'source_id'} & vals.keys():
                for line in self.filtered(lambda item: not item.header_id.correction_of_id):
                    line.source_id._bind_origin(line.header_id.store_id, line.header_id._name, line.header_id.id, 'opening' if line.header_id.purpose == 'opening' else 'other')
            self._check_correction_sources()
            return result

    def unlink(self):
        if any(line.header_id.status == 'saved' for line in self):
            raise ValidationError(_("Saved receipt lines cannot be changed."))
        return super().unlink()

    @api.constrains('source_id', 'header_id', 'correction_qty')
    def _check_correction_sources(self):
        for line in self:
            if not math.isfinite(line.correction_qty) or line.correction_qty < 0:
                raise ValidationError(_('Correction quantities must be finite and non-negative.'))
            if line.header_id.correction_of_id and line.source_id not in line.header_id.correction_of_id.line_ids.source_id:
                raise ValidationError(_('Correction sources must belong to the original receipt.'))

    def _check_correction_limits(self):
        for source in self.source_id:
            requested = self.filtered(lambda line: line.source_id == source)
            original = requested[0].header_id.correction_of_id
            previous = self.search([('source_id', '=', source.id), ('header_id.correction_of_id', '=', original.id), ('header_id.status', '=', 'saved')])
            received = sum(original.line_ids.filtered(lambda line: line.source_id == source).mapped('qty'))
            if sum(requested.mapped('correction_qty')) + sum(previous.mapped('correction_qty')) > received + 1e-9:
                raise ValidationError(_('Corrections cannot exceed the original received quantity.'))

    @api.constrains('bonus')
    def _check_receipt_bonus(self):
        if any(line.bonus for line in self):
            raise ValidationError(_('Opening and other receipts use a single quantity without purchase bonuses.'))
