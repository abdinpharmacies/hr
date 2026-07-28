from odoo import api, fields, models
from odoo.tools.translate import _


class AbStore(models.Model):
    _name = 'ab_store'
    _inherit = 'ab_store'

    """Inherit ab_store to add eplus_serial and keep data structure clean when removing this module in the future"""

    eplus_serial = fields.Integer(index=True)
    last_update_date = fields.Datetime(index=True)
