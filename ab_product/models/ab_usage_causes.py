from odoo import api, fields, models


class AbdinUsageCauses(models.Model):
    _name = 'ab_usage_causes'
    _description = 'Abdin Usage Causes'

    name = fields.Char(required=True)
    code = fields.Char()
    active = fields.Boolean(default=True)

