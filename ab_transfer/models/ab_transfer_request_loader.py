# -*- coding: utf-8 -*-

from odoo import fields, models


class AbTransferHeader(models.Model):
    _inherit = "ab_transfer_header"

    transfer_request_id = fields.Many2one(
        "ab_transfer_request",
        string="Transfer Request",
        copy=False,
    )


class AbTransferLine(models.Model):
    _inherit = "ab_transfer_line"

    requested_qty = fields.Float(
        string="Requested Quantity",
        digits=(16, 3),
        default=0.0,
        copy=False,
    )
