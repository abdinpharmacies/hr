from odoo import api, fields, models
from .extra_functions import get_modified_name


class Job(models.Model):
    _name = 'ab_hr_job'
    _description = 'ab_hr_job'

    name = fields.Char()
    access_history_user_ids = fields.Many2many('ab_users')
    internal_job = fields.Boolean(default=True, index=True)
    active = fields.Boolean(default=True)

    @api.model
    def _search_display_name(self, operator, value):
        mod_name = get_modified_name(value)
        return ['|', ('name', operator, value), ('name', operator, mod_name)]
