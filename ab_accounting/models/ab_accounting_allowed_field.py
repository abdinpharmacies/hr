from odoo import api, fields, models


class AllowedJEFields(models.Model):
    _name = 'ab_accounting_allowed_field'
    _description = 'ab_accounting_allowed_field'

    name = fields.Char(required=True)
