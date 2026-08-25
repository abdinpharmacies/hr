# -*- coding: utf-8 -*-


from odoo import models, fields, api


class CustomerContracts(models.Model):
    _name = 'ab_contract'
    _inherit = 'ab_contract'

    allow_total_invoice_discount = fields.Boolean(default=False)
    total_invoice_discount_source = fields.Selection(
        [
            ("our_company", "Our Company"),
            ("contract_company", "Contract Company"),
        ],
        default="our_company",
        required=False,
    )
