from odoo import api, fields, models


class AbdinProductOrigin(models.Model):
    _name = 'ab_product_origin'
    _description = 'Abdin Product Origin'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

