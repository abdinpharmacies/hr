# models/ab_product_balance_wizard.py
from odoo import models, fields, api


class AbProductBalanceWizard(models.TransientModel):
    _name = 'ab_product_balance_wizard'
    _description = 'Product Balance Wizard'

    product_id = fields.Many2one('ab_product')
    balance_html = fields.Html(string="Store Balances", compute='_compute_balance_html')

    @api.depends('product_id')
    def _compute_balance_html(self):
        for wiz in self:
            if wiz.product_id:
                wiz.balance_html = wiz.product_id._get_all_stores_balance_html(
                    [wiz.product_id.eplus_serial]
                )
            else:
                wiz.balance_html = ""
