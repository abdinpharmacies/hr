# -*- coding: utf-8 -*-

from odoo import fields, models


class CustomerContractsTotalInvoiceDiscount(models.Model):
    _inherit = "ab_contract"

    allow_total_invoice_discount = fields.Boolean(string="Allow Total Invoice Discount")
