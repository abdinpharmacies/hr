# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrEmployeeBase(models.AbstractModel):
    _inherit = "ab_hr_employee"

    child_ids = fields.One2many('ab_hr_employee', 'parent_id', string='Direct subordinates',
                                domain=[('is_working', '=', True)])

    child_all_count = fields.Integer(
        'Indirect Subordinates Count',
        compute='_compute_subordinates', recursive=True, store=False,
        compute_sudo=True)

    @api.depends('is_working', 'child_ids', 'child_ids.is_working', 'child_ids.parent_path')
    def _compute_subordinates(self):
        for employee in self:
            subs = self.env[self._name].search([
                ('id', 'child_of', employee.id),
                ('id', '!=', employee.id),  # exclude self
                ('is_working', '=', True),
            ])

            employee.subordinate_ids = subs
            employee.child_all_count = len(subs)
