from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class AbdinProductTemplate(models.AbstractModel):
    _name = 'ab_product_template'
    _description = 'Abdin Product Template'

    product_id = fields.Many2one('ab_product', required=False, index=True)
    qty = fields.Float(required=False, string='Quantity', default=1)
    uom_id = fields.Many2one('ab_product_uom', required=False, index=True)
    qty_large = fields.Float(compute='_compute_qty_large')
    product_uom_ids = fields.Many2many(related='product_id.uom_ids')

    @api.depends('qty', 'uom_id.factor', 'product_id.uom_id.factor')
    def _compute_qty_large(self):
        for rec in self:
            rec.qty_large = (rec.uom_id.convert_qty(rec.qty, rec.product_id.uom_id)
                             if rec.uom_id and rec.product_id.uom_id else 0.0)
