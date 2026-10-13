from odoo import api, fields, models


class ContractProductOrigin(models.Model):
    _name = 'ab_contract_product_origin'
    _description = 'ab_contract_product_origin'

    contract_id = fields.Many2one('ab_contract')
    product_card_id = fields.Many2one('ab_product_card')
    discount = fields.Float(string='Discount %')

    @api.constrains('contract_id', 'discount', 'product_card_id')
    def _check_contract_promotions(self):
        self.mapped('contract_id')._check_allow_promotions()

    def write(self, vals):
        previous_contracts = self.mapped('contract_id')
        result = super().write(vals)
        if {'contract_id', 'discount', 'product_card_id'} & vals.keys():
            (previous_contracts | self.mapped('contract_id'))._check_allow_promotions()
        return result

    _sql_constraints = [
        (
            'ab_contract_product_origin_contract_card_uniq',
            'unique(contract_id, product_card_id)',
            'This product card already has a rule for this contract.',
        )
    ]


