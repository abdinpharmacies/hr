from odoo import fields, models, _
from odoo.exceptions import ValidationError


class AbUom(models.Model):
    _inherit = 'ab_uom'

    def write(self, vals):
        if {'unit_no', 'unit_size', 'type_id'} & vals.keys():
            for uom_id in sorted(self.ids):
                self.env.cr.execute('SELECT id FROM ab_uom WHERE id = %s FOR UPDATE',
                                    (uom_id,))
            products = self.env['ab_product'].sudo().search(
                fields.Domain('unit_l_id', 'in', self.ids)
                | fields.Domain('unit_m_id', 'in', self.ids)
                | fields.Domain('unit_s_id', 'in', self.ids),
            )
            sources = self.env['ab_product_source'].sudo().search(
                fields.Domain('uom_id', 'in', self.ids),
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
