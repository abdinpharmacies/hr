from odoo import api, fields, models, _


class ProductInherit(models.Model):
    _name = 'ab_costcenter'
    _inherit = 'ab_costcenter'

    eplus_serial = fields.Integer(index=True, readonly=True)

    last_update_date = fields.Datetime(index=True, readonly=True)

    _ab_costcenter_eplus_serial_unique = models.Constraint('unique(eplus_serial)', 'ePlus Serial CAN NOT BE DUPLICATED!')

    def write(self, values):
        res = super().write(values)
        if 'eplus_serial' in values and not values.get('eplus_serial'):
            values.update({'eplus_serial': None})
        return res
