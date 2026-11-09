from odoo import api, fields, models, _


class AbStore(models.Model):
    _name = 'ab_store'
    _inherit = 'ab_store'

    """Inherit ab_store to add eplus_serial and keep data structure clean when removing this module in the future"""

    eplus_serial = fields.Integer(index=True)
    last_update_date = fields.Datetime(index=True)

    _ab_store_eplus_serial_unique = models.Constraint('unique(eplus_serial)', 'ePlus Serial CAN NOT BE DUPLICATED!')
