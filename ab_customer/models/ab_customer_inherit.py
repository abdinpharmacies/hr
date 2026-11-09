from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class ProductInherit(models.Model):
    _name = 'ab_customer'
    _inherit = 'ab_customer'

    eplus_serial = fields.Integer(index=True, readonly=True)

    last_update_date = fields.Datetime(index=True, readonly=True)

    eplus_create_date = fields.Datetime()

    _ab_product_eplus_serial_unique = models.Constraint('unique(eplus_serial)', 'ePlus Serial CAN NOT BE DUPLICATED!')

    user_code = fields.Char(store=False, readonly=False)
    password = fields.Char(store=False, readonly=False)

    def write(self, values):
        CC = self.env['ab_costcenter'].sudo()
        res = super().write(values)
        for rec in self:
            cc_user = CC.search([('code', '=', rec.user_code)], limit=1)
            rec = rec.sudo()
            if self.env.context.get('eplus_replication'):
                continue
            if not (rec.user_code and cc_user.password == rec.password):
                raise AccessError(_("Wrong Password"))
            else:
                msg = _("Edited by %s") % cc_user.name
                rec.message_post(body=msg)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for values in vals_list:
            records |= self._create_one_ab_customer_productinherit(values)
        return records

    def _create_one_ab_customer_productinherit(self, values):
        res = super().create(values)

        return res
