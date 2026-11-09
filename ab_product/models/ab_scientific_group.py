from odoo import api, fields, models


class AbdinScientificGroup(models.Model):
    _name = 'ab_scientific_group'
    _description = 'Abdin scientific group'

    name = fields.Char(required=True)
    code = fields.Char()
    last_update_date = fields.Datetime()
    active = fields.Boolean(default=True)





