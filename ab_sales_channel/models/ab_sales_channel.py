from odoo import fields, models, _
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
from odoo.exceptions import UserError


class AbSalesChannel(models.Model):
    _name = "ab_sales_channel"
    _description = "Sales Channel"
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(index=True, copy=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _uniq_code = models.Constraint(
        "UNIQUE(code)",
        "Sales channel code must be unique.",
    )

    def unlink(self):
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(_("Archive sales channels instead of deleting them."))
