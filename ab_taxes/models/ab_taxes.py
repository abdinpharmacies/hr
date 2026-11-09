from odoo import api, fields, models


class Taxes(models.Model):
    _name = 'ab_taxes'
    _description = 'ab_taxes'
    name = fields.Char()
    percentage = fields.Float()
    status = fields.Selection(selection=[('purchase', 'Purchase'), ('sales', 'Sales'), ('all', 'All')],
                              default='purchase')
    active = fields.Boolean(default=True)
    apply_on_total = fields.Boolean()
