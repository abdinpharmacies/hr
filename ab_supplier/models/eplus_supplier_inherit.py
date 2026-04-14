from odoo import api, fields, models
from odoo.tools.translate import _


class Supplier(models.Model):
    _name = 'ab_supplier'
    _inherit = 'ab_supplier'
    """Add eplus_serial to keep data clean when removing this module in the future"""

    eplus_serial = fields.Integer(index=True)
    last_update_date = fields.Datetime(index=True)
