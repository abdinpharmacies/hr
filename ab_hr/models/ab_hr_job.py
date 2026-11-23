from odoo import api, fields, models

from .extra_functions import with_normalized_name


class Job(models.Model):
    _name = 'ab_hr_job'
    _description = 'Job'

    name = fields.Char(required=True)
    internal_job = fields.Boolean(default=True, index=True)
    active = fields.Boolean(default=True)

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        return with_normalized_name(domain, operator, value)
