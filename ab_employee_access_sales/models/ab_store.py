from odoo import fields, models


class AbStore(models.Model):
    _inherit = "ab_store"

    pos_service_user_id = fields.Many2one(
        "res.users",
        string="POS Service User",
        domain=[("share", "=", False)],
        help="Shared Odoo user used by this branch/device instead of creating an Odoo account per employee.",
    )
    pos_shift_ids = fields.One2many("ab_employee_access_sales_shift", "store_id")
    pos_session_ids = fields.One2many("ab_employee_access_sales_pos_session", "store_id")
