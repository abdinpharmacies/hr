from odoo import api, fields, models


class AbdinProductGroup(models.Model):
    _name = 'ab_product_group'
    _description = 'Abdin Product Group'

    name = fields.Char(required=True)
    code = fields.Char()
    parent_id = fields.Many2one('ab_product_group')
    child_ids = fields.One2many(comodel_name='ab_product_group', inverse_name='parent_id')
    last_update_date = fields.Datetime()
    active = fields.Boolean(default=True)
