from odoo import api, fields, models
from .extra_functions import get_modified_name


class Job(models.Model):
    _name = 'ab_hr_job'
    _description = 'ab_hr_job'

    name = fields.Char(required=True)
    access_history_user_ids = fields.Many2many('res.users', domain=[('share', '=', False)])
    internal_job = fields.Boolean(default=True, index=True)
    active = fields.Boolean(default=True)

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        mod_name = get_modified_name(name)
        args += ['|',
                 ('name', operator, name),
                 ('name', operator, mod_name),
                 ]

        ids = (self.with_user(name_get_uid) if name_get_uid else self).search(args, limit=limit).ids
        return ids

    _ab_hr_job_unique = models.Constraint('unique(name)', 'JOB CAN NOT BE DUPLICATED!')

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        ids = self._name_search(name, args=domain, operator=operator, limit=limit)
        return [(record.id, record.display_name) for record in self.browse(ids)]

    @api.model
    def _search_display_name(self, operator, value):
        """Keep code/barcode/name matching in relational search domains too."""
        if operator in ('in', 'not in') and isinstance(value, (list, tuple)):
            domain = fields.Domain.OR(self._search_display_name('=', item) for item in value)
            return list(~domain if operator == 'not in' else domain)
        ids = self._name_search(value or '', operator=operator, limit=None)
        return [('id', 'in', ids)]
