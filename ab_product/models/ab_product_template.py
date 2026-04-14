from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class AbdinProductTemplate(models.AbstractModel):
    _name = 'ab_product_template'
    _description = 'Abdin Product Template'

    product_id = fields.Many2one('ab_product', required=False, index=True)
    qty = fields.Float(required=False, string='Quantity', default=1)
    uom_id = fields.Many2one('ab_uom', required=False, index=True)
    qty_large = fields.Float(compute='_compute_qty_large')
    product_uom_ids = fields.Many2many(related='product_id.uom_ids')

    @api.depends('qty', 'uom_id', 'product_id')
    def _compute_qty_large(self):
        for rec in self:
            if rec.uom_id.unit_size == 'large':
                rec.qty_large = rec.qty
            elif rec.uom_id.unit_size == 'medium':
                rec.qty_large = rec.qty / rec.product_id.unit_m_id.unit_no
            elif rec.uom_id.unit_size == 'small':
                rec.qty_large = rec.qty / rec.product_id.unit_s_id.unit_no
            else:
                rec.qty_large = 0
