from odoo import api, fields, models, _


class AbdinEplusSupplier(models.Model):
    _name = 'abdin_eplus_ab_supplier'
    _description = 'abdin_eplus_ab_supplier'

    name = fields.Char()
