from odoo import api, fields, models, _


class AbPurchaseJeData(models.AbstractModel):
    _name = 'ab_purchase_je_line_data'
    _description = 'ab_purchase_je_line_data'

    # je_taxes_value = fields.Float(compute='_compute_je_line_data')
    # je_inventory_value = fields.Float(compute='_compute_je_line_data')
    # je_received_discount_value = fields.Float(compute='_compute_je_line_data')
    # je_supplier_value = fields.Float(compute='_compute_je_line_data')
    # je_taxes_account_id = fields.Many2one('ab_accounting_account_guide', compute='_compute_je_line_data')
    # je_taxes_debit_value = fields.Float(compute='_compute_je_line_data')
    # je_taxes_credit_value = fields.Float(compute='_compute_je_line_data')
    # je_inventory_account_id = fields.Many2one('ab_accounting_account_guide', compute='_compute_je_line_data')
    # je_inventory_debit_value = fields.Float(compute='_compute_je_line_data')
    # je_inventory_credit_value = fields.Float(compute='_compute_je_line_data')
    # je_disc_received_account_id = fields.Many2one('ab_accounting_account_guide', compute='_compute_je_line_data')
    # je_disc_received_debit_value = fields.Float(compute='_compute_je_line_data')
    # je_disc_received_credit_value = fields.Float(compute='_compute_je_line_data')
    # je_supplier_account_id = fields.Many2one('ab_accounting_account_guide', compute='_compute_je_line_data')
    # je_supplier_debit_value = fields.Float(compute='_compute_je_line_data')
    # je_supplier_credit_value = fields.Float(compute='_compute_je_line_data')
