# -*- coding: utf-8 -*-

from odoo import fields, models


class AbSalesPosSettings(models.Model):
    _name = "ab_sales_pos_settings"
    _description = "Sales POS User Settings"
    _rec_name = "user_id"
    _order = "id desc"

    user_id = fields.Many2one(
        "res.users",
        required=True,
        index=True,
        ondelete="cascade",
        default=lambda self: self.env.user,
    )
    settings_version = fields.Integer(default=1)
    last_synced_at = fields.Datetime()
    settings_json = fields.Json(default=dict)

    _uniq_user_id = models.Constraint(
        "UNIQUE(user_id)",
        "POS settings already exist for this user.",
    )
