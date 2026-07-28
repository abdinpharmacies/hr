# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AbSalesPosDraftCache(models.Model):
    _name = "ab_sales_pos_draft_cache"
    _description = "Sales POS Draft Cache"
    _rec_name = "user_id"
    _order = "write_date desc, id desc"

    user_id = fields.Many2one(
        "res.users",
        required=True,
        index=True,
        ondelete="cascade",
        default=lambda self: self.env.user,
    )
    employee_id = fields.Many2one(
        "ab_hr_employee",
        index=True,
        ondelete="cascade",
        help="Employee logged into the POS with PIN. Empty means the draft cache is scoped only by Odoo user.",
    )
    employee_scope_key = fields.Integer(default=0, required=True, index=True)
    cache_key = fields.Char(required=True, index=True)
    selected_id = fields.Char()
    last_synced_at = fields.Datetime()
    bills_json = fields.Json(default=list)

    _uniq_user_cache_key = models.Constraint(
        "UNIQUE(user_id, employee_scope_key, cache_key)",
        "POS draft cache already exists for this user and employee.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            values = dict(vals or {})
            values["employee_scope_key"] = int(
                values.get("employee_id") or values.get("employee_scope_key") or 0
            )
            prepared.append(values)
        return super().create(prepared)

    def write(self, vals):
        values = dict(vals or {})
        if "employee_id" in values:
            values["employee_scope_key"] = int(values.get("employee_id") or 0)
        return super().write(values)
