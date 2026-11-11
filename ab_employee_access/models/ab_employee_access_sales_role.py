from odoo import fields, models


class AbSalesHrRole(models.Model):
    _name = "ab_employee_access_sales_role"
    _description = "Sales HR POS Role"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    allow_pos_screen = fields.Boolean(default=True)
    allow_cashier_screen = fields.Boolean(default=False)
    allow_return_screen = fields.Boolean(default=False)
    idle_lock_seconds = fields.Integer(default=600)
    pin_rotation_days = fields.Integer(default=90)

    profile_ids = fields.One2many("ab_employee_access", "pos_role_id")
