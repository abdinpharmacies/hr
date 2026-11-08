from odoo import api, fields, models
from odoo.tools.translate import _


class ProductInherit(models.Model):
    _name = 'ab_product'
    _inherit = 'ab_product'

    eplus_serial = fields.Integer(index=True)

    last_update_date = fields.Datetime(index=True)

    eplus_create_date = fields.Datetime(index=True)



class ProductCardInherit(models.Model):
    _name = 'ab_product_card'
    _inherit = 'ab_product_card'

    eplus_serial = fields.Integer(index=True)
    last_update_date = fields.Datetime(index=True)
