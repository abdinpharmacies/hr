from odoo import api, fields, models


class Customer(models.Model):
    _name = 'ab_customer'
    _inherit = 'ab_customer'

    customer_type = fields.Selection([
        ('person', 'Person'),
        ('insurance', 'Insurance'),
    ], required=False, default='person')
    parent_id = fields.Many2one('ab_customer')
    max_credit = fields.Float()
    branch_id = fields.Many2one('ab_store')
    default_branch_id = fields.Many2one('ab_store')
    current_points = fields.Float(compute='compute_loyalty_points')
    description = fields.Text()

    def compute_loyalty_points(self):
        for rec in self:
            rec.current_points = 0
