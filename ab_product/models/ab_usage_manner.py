from odoo import api, fields, models


class AbdinUsageManner(models.Model):
    _name = 'ab_usage_manner'
    _description = 'Abdin Usage Manner'

    name = fields.Char(required=True)
    code = fields.Char()
    active = fields.Boolean(default=True)

