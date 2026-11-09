from odoo import api, fields, models, _


class ResUsers(models.Model):
    _name = 'res.users'
    _inherit = 'res.users'

    ab_employee_ids = fields.One2many('ab_hr_employee',
                                      'user_id',
                                      string='Employees')

    ab_department_ids = fields.One2many('ab_hr_department',
                                        'user_id',
                                        string='Department')

    count_linked = fields.Integer(compute='_compute_count_linked')

    def _compute_count_linked(self):
        for rec in self:
            rec.count_linked = len(rec.ab_employee_ids) + len(rec.ab_department_ids)

    def btn_link_employee(self):
        return {
            'name': 'Link Employee(s)',
            'type': 'ir.actions.act_window',
            'res_model': 'ab_hr_employee',
            'view_mode': 'kanban,form,list,pivot',

        }

    def btn_link_department(self):
        return {
            'name': 'Link Department(s)',
            'type': 'ir.actions.act_window',
            'res_model': 'ab_hr_department',
            'view_mode': 'list,form',

        }

    def btn_show_linked(self):
        self.ensure_one()
        if len(self.ab_department_ids) > 0:
            return {
                'name': 'Related Department(s)',
                'type': 'ir.actions.act_window',
                'res_model': 'ab_hr_department',
                'view_mode': 'list,form',
                'domain': [('user_id', '=', self.id)],

            }

        if len(self.ab_employee_ids) > 0:
            return {
                'name': 'Related Employee(s)',
                'type': 'ir.actions.act_window',
                'res_model': 'ab_hr_employee',
                'view_mode': 'kanban,form,list,pivot',
                'domain': [('user_id', '=', self.id)],

            }

    def btn_show_employee(self):
        pass
