from odoo import api, fields, models
from odoo.tools.translate import _


class ProductInherit(models.Model):
    _name = 'ab_costcenter'
    _inherit = 'ab_costcenter'

    eplus_serial = fields.Integer(index=True, readonly=True)

    last_update_date = fields.Datetime(index=True, readonly=True)
