# -*- coding: utf-8 -*-

from odoo import fields, models, _


class AbSalesCallcenterRpcLog(models.Model):
    _name = "ab_sales_callcenter_rpc_log"
    _description = "Sales Call-Center RPC Log"
    _order = "submitted_at desc, id desc"

    name = fields.Char(
        required=True,
        default=lambda self: _("Call-Center Branch Submit"),
    )
    active = fields.Boolean(default=True)
    rpc_config_id = fields.Many2one(
        "ab_sales_branch_rpc_config",
        string="Branch RPC Configuration",
        readonly=True,
        ondelete="set null",
        index=True,
    )
    store_id = fields.Many2one(
        "ab_store",
        string="Target Store",
        readonly=True,
        ondelete="set null",
        index=True,
    )
    payload_token = fields.Char(string="POS Client Token", readonly=True, index=True)
    state = fields.Selection(
        selection=[
            ("started", "Started"),
            ("success", "Success"),
            ("error", "Error"),
        ],
        default="started",
        readonly=True,
        index=True,
    )
    submitted_by_id = fields.Many2one(
        "res.users",
        string="Submitted By",
        readonly=True,
        ondelete="set null",
        index=True,
    )
    submitted_at = fields.Datetime(string="Submitted At", readonly=True, index=True)
    remote_header_id = fields.Integer(string="Remote Header ID", readonly=True)
    remote_status = fields.Char(string="Remote Status", readonly=True)
    remote_eplus_serial = fields.Integer(string="Remote E-Plus Serial", readonly=True)
    response_message = fields.Text(string="Response Message", readonly=True)
    error_message = fields.Text(string="Error Message", readonly=True)
