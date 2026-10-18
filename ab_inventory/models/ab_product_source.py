from odoo import models, _
from odoo.exceptions import ValidationError


class AbProductSource(models.Model):
    _inherit = 'ab_product_source'

    def write(self, vals):
        if {'product_id', 'uom_id'} & vals.keys():
            has_saved = self.env['ab_inventory'].sudo().search_count([
                ('source_id', 'in', self.ids), ('status', '=', 'saved'),
            ])
            if has_saved:
                raise ValidationError(_(
                    "The item and unit cannot change after stock movements are saved."
                ))
        return super().write(vals)
