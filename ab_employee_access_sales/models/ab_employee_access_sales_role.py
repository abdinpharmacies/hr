from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AbSalesHrRole(models.Model):
    _name = "ab_employee_access_sales_role"
    _inherit = 'ab_employee_access_sales_role'
    _order = "sequence, name, id"

    @api.constrains(
        "pin_rotation_days",
    )
    def _check_limits(self):
        for rec in self:
            if rec.pin_rotation_days < 1:
                raise ValidationError("PIN rotation days must be at least 1.")

    def permission_payload(self):
        self.ensure_one()
        return {
            "allow_pos_screen": bool(self.allow_pos_screen),
            "allow_cashier_screen": bool(self.allow_cashier_screen),
            "allow_return_screen": bool(self.allow_return_screen),
            "pin_rotation_days": int(self.pin_rotation_days or 90),
        }
