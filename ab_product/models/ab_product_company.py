from odoo import api, fields, models


class AbdinProductCompany(models.Model):
    _name = 'ab_product_company'
    _description = 'Abdin Product Company'

    name = fields.Char(required=True)
    code = fields.Char()
    telephone = fields.Char()
    address = fields.Char()
    active = fields.Boolean(default=True)
    last_update_date = fields.Datetime()





