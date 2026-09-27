from odoo import models, _
from odoo.exceptions import ValidationError


class AbProduct(models.Model):
    _inherit = 'ab_product'

    def write(self, vals):
        if {'unit_s_id', 'unit_m_id', 'unit_l_id'} & vals.keys():
            has_saved = self.env['ab_inventory'].sudo().search_count([
                ('product_id', 'in', self.ids), ('status', '=', 'saved'),
            ])
            if has_saved:
                raise ValidationError(_(
                    "Item unit definitions cannot change after stock movements are saved."
                ))
        return super().write(vals)
