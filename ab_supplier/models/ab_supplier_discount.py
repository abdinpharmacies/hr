from odoo import api, fields, models, _


class AbSupplierDiscount(models.Model):
    _name = 'ab_supplier_discount'
    _description = 'ab_supplier_discount'

    supplier_id = fields.Many2one('ab_costcenter')
    start_day = fields.Integer(default=0, required=True)
    discount = fields.Float(default=0, required=True, digits=(5, 2))
    withdrawal_bracket = fields.Float(default=0, required=True, digits=(16, 2))
