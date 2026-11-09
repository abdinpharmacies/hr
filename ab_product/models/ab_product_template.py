from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AbdinProductTemplate(models.AbstractModel):
    _name = 'ab_product_template'
    _description = 'Abdin Product Template'

    product_id = fields.Many2one('ab_product', required=True, index=True)
    qty = fields.Float(required=True, string='Quantity', default=1)
    uom_id = fields.Many2one('ab_uom', required=True, index=True)
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

    def write(self, vals):
        res = super().write(vals)
        product_uom_ids = [self.product_id.unit_l_id.id,
                           self.product_id.unit_m_id.id, self.product_id.unit_s_id.id]
        if 'uom_id' in vals and vals['uom_id'] not in product_uom_ids:
            raise ValidationError(
                _("The unit of measure must be one of the product's units of measure."))
        return res
