# -*- coding: utf-8 -*-

from odoo import fields, models


class AbSalesPosReplicationTurn(models.Model):
    _name = "ab_sales_pos_replication_turn"
    _description = "Sales POS Replication Manual Turn"
    _rec_name = "user_id"
    _order = "write_date desc"

    user_id = fields.Many2one(
        "res.users",
        required=True,
        index=True,
        ondelete="cascade",
        default=lambda self: self.env.user,
    )
    cron_id = fields.Many2one(
        "ir.cron",
        required=True,
        index=True,
        ondelete="cascade",
    )
    last_manual_run_at = fields.Datetime(required=True, default=fields.Datetime.now)

    _uniq_user_cron = models.Constraint(
        "UNIQUE(user_id, cron_id)",
        "Manual replication turn already exists for this user and cron.",
    )
