# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.tools.translate import _


class Employee(models.Model):
    _inherit = ["ab_hr_employee"]

    subordinate_ids = fields.One2many('ab_hr_employee', string='Subordinates', compute='_compute_subordinates',
                                      help="Direct and indirect subordinates",
                                      compute_sudo=True)

    def btn_show_org_chart(self):
        self.ensure_one()
        return {
            'name': _('Org Chart'),
            'type': 'ir.actions.act_window',
            'res_model': 'ab_hr_employee',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('ab_hr_org_chart.hr_employee_view_org_chart_form').id, 'form')],
            'target': 'new',
            'context': dict(self.env.context, org_chart_only=True),
        }
