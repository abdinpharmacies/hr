from odoo import fields, models


class Store(models.Model):
    _inherit = 'ab_store'

    asset_department_ids = fields.One2many(
        'ab_hr_department', 'store_id', string='Asset Departments',
        groups='base.group_system',
    )
