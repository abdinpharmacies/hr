from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class Opening_Balance_Details(models.Model):
    _name = 'ab_purchase_ob_line'
    _description = 'opening_balance_details'
    _rec_name = 'product_id'

    source_id = fields.Many2one(
        'ab_product_source', required=True, delegate=True, ondelete='cascade')
    header_id = fields.Many2one(
        'ab_purchase_ob_header', required=True, ondelete='cascade')
    header_status = fields.Selection(related='header_id.status')

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
