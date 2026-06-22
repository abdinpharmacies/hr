from odoo import api, fields, models, _


class Supplier(models.Model):
    _name = 'ab_supplier'
    _inherit = 'ab_supplier'
    """Add eplus_serial to keep data clean when removing this module in the future"""

    eplus_serial = fields.Integer(index=True)
    last_update_date = fields.Datetime(index=True)

    _sql_constraints = [
        ('ab_supplier_eplus_serial_unique', 'unique(eplus_serial)', 'ePlus Serial CAN NOT BE DUPLICATED!')]
