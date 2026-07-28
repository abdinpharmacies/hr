from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class AbProductUomCategory(models.Model):
    _name = 'ab_product_uom_category'
    _description = 'Product UoM Category'

    name = fields.Char(required=False)
    active = fields.Boolean(default=False)
    uom_ids = fields.One2many('ab_product_uom', 'category_id')


class AbProductUom(models.Model):
    _name = 'ab_product_uom'
    _description = 'Product UoM'
    _order = 'name'

    name = fields.Char(required=False)
    category_id = fields.Many2one('ab_product_uom_category', required=False)
    uom_type = fields.Selection(
        selection=[('reference', 'Reference'), ('bigger', 'Bigger'), ('smaller', 'Smaller')],
        default='reference',
        required=False,
    )
    factor = fields.Float(default=1.0, digits=(16, 6))
    rounding = fields.Float(default=0.01, digits=(16, 6))
    active = fields.Boolean(default=True)

    def convert_qty(self, qty, to_uom):
        self.ensure_one()
        if not qty or not to_uom or self.category_id != to_uom.category_id:
            return 0.0
        return (qty * self.factor) / (to_uom.factor or 1.0)
