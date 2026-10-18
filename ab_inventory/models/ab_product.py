from odoo import fields, models, _
from odoo.exceptions import ValidationError


class AbProduct(models.Model):
    _inherit = 'ab_product'

    def write(self, vals):
        if {'unit_s_id', 'unit_m_id', 'unit_l_id'} & vals.keys():
            for product_id in sorted(self.ids):
                self.env.cr.execute(
                    'SELECT id FROM ab_product WHERE id = %s FOR UPDATE',
                    (product_id,),
                )
            domain = (fields.Domain('product_id', 'in', self.ids)
                      & fields.Domain('status', 'in', ['pending', 'saved']))
            if self.env['ab_inventory'].sudo().search(domain, limit=1):
                raise ValidationError(_(
                    "Item unit definitions cannot change while inventory movements are pending or saved."
                ))
        return super().write(vals)
