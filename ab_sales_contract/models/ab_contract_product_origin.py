from odoo import fields, models


class ContractProductOrigin(models.Model):
    _name = 'ab_contract_product_origin'
    _description = 'ab_contract_product_origin'

    contract_id = fields.Many2one('ab_contract')
    product_card_id = fields.Many2one('ab_product_card')
    discount = fields.Float(string='Discount %')
