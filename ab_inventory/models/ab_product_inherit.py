from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class AbProduct(models.Model):
    _name = 'ab_product'
    _inherit = 'ab_product'

    def write(self, vals):
        for rec in self:
            old_unit_s_id_unit_no = rec.unit_s_id.unit_no
            res = super().write(vals)
            if self.env.context.get('eplus_replication'):
                return res
            if (rec.unit_s_id.unit_no != old_unit_s_id_unit_no
                    and self.env['ab_inventory'].sudo().search_count([('product_id', '=', rec.id)])):
                raise ValidationError(_("Can not change small unit because sub product appears in inventory,"
                                        " please create another sub product."))
            return res
