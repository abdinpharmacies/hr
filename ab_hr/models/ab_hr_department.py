from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .extra_functions import with_normalized_name


class Department(models.Model):
    _name = 'ab_hr_department'
    _description = 'Department'
    _parent_store = True

    name = fields.Char(required=True)
    parent_id = fields.Many2one('ab_hr_department', string='Superior Department', index=True, ondelete='restrict')
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('ab_hr_department', 'parent_id', string='Child Departments')
    manager_id = fields.Many2one('ab_hr_employee', string='Department Manager')
    store_id = fields.Many2one('ab_store', index=True)
    active = fields.Boolean(default=True)

    @api.constrains('parent_id')
    def _check_department_hierarchy(self):
        if self._has_cycle():
            raise ValidationError(_('A department cannot be its own direct or indirect parent.'))

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        return with_normalized_name(domain, operator, value)
