from odoo import api, fields, models
from odoo.tools.translate import _



class AbAbdinTable(models.Model):
    _name = 'ab_abdin_table'
    _description = 'ab_abdin_table'

    name = fields.Char()
    address = fields.Text()
    value = fields.Float()
    myint = fields.Integer()









