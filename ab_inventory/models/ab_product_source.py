from odoo import fields, models, _
from odoo.exceptions import ValidationError


class AbProductSource(models.Model):
    _inherit = 'ab_product_source'

    def write(self, vals):
        if {'product_id', 'uom_id'} & vals.keys():
            extra_products = [vals['product_id']] if vals.get('product_id') else []
            self.env['ab_inventory_process']._lock_unit_definitions(
                self.ids, product_ids=extra_products,
            )
            domain = (fields.Domain('source_id', 'in', self.ids)
                      & fields.Domain('status', 'in', ['pending', 'saved']))
            if self.env['ab_inventory'].sudo().search(domain, limit=1):
                raise ValidationError(_(
                    "The item and unit cannot change while inventory movements are pending or saved."
                ))
        return super().write(vals)
