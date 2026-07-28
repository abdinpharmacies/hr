from odoo import fields, models


class ContractProductOrigin(models.Model):
    _name = 'ab_contract_product_origin'
    _description = 'ab_contract_product_origin'

    contract_id = fields.Many2one('ab_contract')
    product_card_id = fields.Many2one('ab_product_card')
    discount = fields.Float(string='Discount %')

    _sql_constraints = [
        (
            'ab_contract_product_origin_contract_card_uniq',
            'unique(contract_id, product_card_id)',
            'This product card already has a rule for this contract.',
        )
    ]


