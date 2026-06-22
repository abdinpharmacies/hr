# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class ManpowerHourNeed(models.Model):
    _name = 'ab_hr_manpower_hour_need'
    _description = 'Manpower Need Per Hour'
    _rec_name = 'workplace'

    workplace = fields.Many2one('ab_hr_department', required=True, index=True, string='Branch')
    workplace_region = fields.Many2one(related='workplace.workplace_region', store=True)
    job_title = fields.Many2one('ab_hr_job', index=True, string='Job Title')

    required_operating_hours = fields.Float(string='Required Hours')
    default_actual_daily_hours = fields.Float(string='Fallback Actual Daily Hours', default=8.0)
    actual_employee_ids = fields.Many2many(
        comodel_name='ab_hr_employee',
        string='Employees',
    )
    employee_line_ids = fields.One2many(
        comodel_name='ab_hr_manpower_hour_need_line',
        inverse_name='manpower_hour_need_id',
        string='Employees',
    )
    actual_available_hours = fields.Float(
        string='Actual Hours',
    )
    shortage_hours = fields.Float(
        string='Shortage Hours',
        compute='_compute_shortage_hours',
        compute_sudo=True,
        store=True,
    )
    required_hours_label = fields.Char(
        string='Required Hours Label',
        compute='_compute_kanban_labels',
    )
    actual_hours_label = fields.Char(
        string='Actual Hours Label',
        compute='_compute_kanban_labels',
    )
    shortage_hours_label = fields.Char(
        string='Shortage Hours Label',
        compute='_compute_kanban_labels',
    )

    _unique_workplace_job_title = models.Constraint(
        'UNIQUE(workplace, job_title)',
        'Only one manpower per-hour plan is allowed for the same branch and job title.',
    )

    @api.depends('required_operating_hours', 'actual_available_hours')
    def _compute_shortage_hours(self):
        for rec in self:
            rec.shortage_hours = max(rec.required_operating_hours - rec.actual_available_hours, 0.0)

    def _compute_kanban_labels(self):
        for rec in self:
            rec.required_hours_label = _('Required Hours')
            rec.actual_hours_label = _('Actual Hours')
            rec.shortage_hours_label = _('Shortage Hours')

    @api.onchange('workplace', 'job_title', 'required_operating_hours', 'default_actual_daily_hours')
    def _onchange_capacity_inputs(self):
        for rec in self:
            employees = rec._get_actual_employees()
            actual_hours = sum(rec._get_employee_actual_hours(employee) for employee in employees)
            rec.actual_employee_ids = [(6, 0, employees.ids)]
            rec.actual_available_hours = actual_hours
            rec.shortage_hours = max(rec.required_operating_hours - actual_hours, 0.0)

    @api.onchange('required_operating_hours', 'actual_available_hours')
    def _onchange_hours(self):
        for rec in self:
            rec.shortage_hours = max(rec.required_operating_hours - rec.actual_available_hours, 0.0)

    @api.depends('workplace.name', 'job_title.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s / %s' % (
                rec.workplace.name or '',
                rec.job_title.name or '',
            )

    def _get_actual_workforce_domain(self):
        self.ensure_one()
        if not self.workplace:
            return [('id', '=', 0)]
        domain = [
            ('workplace', '=', self.workplace.id),
            ('termination_date', '=', False),
            ('issue_date', '=', False),
        ]
        if self.job_title:
            domain.append(('job_id', '=', self.job_title.id))
        return domain

    def _get_actual_employees(self):
        self.ensure_one()
        employees = self.env['ab_hr_job_occupied'].sudo().search(
            self._get_actual_workforce_domain()
        ).mapped('employee_id')
        if not self.workplace:
            return employees

        if self.workplace.user_id:
            employees |= self.workplace.user_id.ab_employee_ids.sudo()

        employee_domain = [
            ('department_id', '=', self.workplace.id),
            ('termination_date', '=', False),
            ('issue_date', '=', False),
        ]
        if self.job_title:
            employee_domain.append(('job_id', '=', self.job_title.id))
        return employees | self.env['ab_hr_employee'].sudo().search(employee_domain)

    def action_fetch_employees(self):
        self.ensure_one()
        employees = self._get_actual_employees()
        line_commands = [(5, 0, 0)]
        actual_hours = 0.0
        for employee in employees:
            employee_hours = self._get_employee_actual_hours(employee)
            actual_hours += employee_hours
            line_commands.append((0, 0, {
                'employee_id': employee.id,
                'actual_hours': employee_hours,
            }))
        self.write({
            'actual_employee_ids': [(6, 0, employees.ids)],
            'employee_line_ids': line_commands,
            'actual_available_hours': actual_hours,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Manpower Need Per Hour',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def _refresh_actual_hours_for_employees(self, employees):
        if not employees:
            return
        plans = self.sudo().search([
            '|',
            ('employee_line_ids.employee_id', 'in', employees.ids),
            ('actual_employee_ids', 'in', employees.ids),
        ])
        for plan in plans:
            if plan.employee_line_ids:
                for line in plan.employee_line_ids:
                    line.actual_hours = plan._get_employee_actual_hours(line.employee_id)
                line_employees = plan.employee_line_ids.mapped('employee_id')
                plan.write({
                    'actual_employee_ids': [(6, 0, line_employees.ids)],
                    'actual_available_hours': sum(plan.employee_line_ids.mapped('actual_hours')),
                })
                continue

            plan.write({
                'actual_available_hours': sum(
                    plan._get_employee_actual_hours(employee)
                    for employee in plan.actual_employee_ids
                ),
            })

    def _get_employee_actual_hours(self, employee):
        self.ensure_one()
        basic_effect = self._get_employee_basic_working_hour_effect(employee)
        if basic_effect:
            return basic_effect.basic_working_hour_value
        return self._get_employee_daily_hours(employee)

    def _get_employee_basic_working_hour_effect(self, employee):
        self.ensure_one()
        if 'ab_hr_basic_effect' not in self.env.registry.models:
            return self.env['ab_hr_employee']
        return self.env['ab_hr_basic_effect'].sudo().search([
            ('employee_id', '=', employee.id),
            ('effect_type_id.basic_working_hour_number', '=', True),
            ('active', '=', True),
        ], order='id desc', limit=1)

    def _get_employee_daily_hours(self, employee):
        self.ensure_one()
        if 'daily_working_hours' in employee._fields and employee.daily_working_hours:
            return employee.daily_working_hours
        if 'resource_calendar_id' in employee._fields and employee.resource_calendar_id:
            calendar = employee.resource_calendar_id
            if 'hours_per_day' in calendar._fields and calendar.hours_per_day:
                return calendar.hours_per_day
        return self.default_actual_daily_hours or 0.0


class ManpowerHourNeedLine(models.Model):
    _name = 'ab_hr_manpower_hour_need_line'
    _description = 'Manpower Need Per Hour Employee'
    _rec_name = 'employee_id'

    manpower_hour_need_id = fields.Many2one(
        'ab_hr_manpower_hour_need',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one('ab_hr_employee', required=True, string='Employee')
    user_id = fields.Many2one(related='employee_id.user_id', string='User')
    job_title = fields.Many2one(related='employee_id.job_id', string='Job Title')
    department_id = fields.Many2one(related='employee_id.department_id', string='Department')
    actual_hours = fields.Float(string='Actual Hours')
