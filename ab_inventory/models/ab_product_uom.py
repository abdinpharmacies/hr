from odoo import fields, models, _
from odoo.exceptions import ValidationError


class AbProductUom(models.Model):
    _inherit = 'ab_product_uom'

    def write(self, vals):
        if {'factor', 'category_id', 'uom_type', 'active'} & vals.keys():
            self.sorted('id').lock_for_update(allow_referencing=True)
            sources = self.env['ab_product_source'].sudo().search(
                fields.Domain('uom_id', 'in', self.ids),
            )
            categories = self.mapped('category_id')
            products = self.env['ab_product'].sudo().search(
                fields.Domain('uom_category_id', 'in', categories.ids),
            )
            if products or sources:
                domain = (fields.Domain('status', 'in', ['pending', 'saved'])
                          & (fields.Domain('product_id', 'in', products.ids)
                             | fields.Domain('source_id', 'in', sources.ids)))
                if self.env['ab_inventory'].sudo().search(domain, limit=1):
                    raise ValidationError(_(
                        "Unit values cannot change while inventory movements are pending or saved."
                    ))
        return super().write(vals)
