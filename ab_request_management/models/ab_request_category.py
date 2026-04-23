from odoo import api, fields, models


class AbRequestCategory(models.Model):
    _name = 'ab_request_category'
    _description = 'ab_request_category'

    name = fields.Char()
