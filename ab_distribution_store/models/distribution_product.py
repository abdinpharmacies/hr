from odoo import fields, models


class DistributionStoreProduct(models.Model):
    _name = 'ab_distribution_store_product'
    _description = 'Distribution Store Product'

    code = fields.Char(required=True)
    name = fields.Char(required=True)
    default_price = fields.Float(digits=(10, 2))
    active = fields.Boolean(default=True)
