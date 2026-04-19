from odoo import models, fields, api

class DailyHoursDeduction(models.Model):
    _name = 'daily.hours.deduction'
    _description = 'Payroll Deductions'

    name = fields.Char(string='Name', compute='_compute_name')
    employee_id = fields.Many2one('ab_hr_employee', string='Employee', required=True)
    period_id = fields.Many2one('daily.hours.payroll.period', string='Payroll Period', required=True)

    absence_deduction_basic = fields.Float(string='Absence Deduction (Basic)', compute='_compute_deductions', store=True)
    absence_deduction_allowances = fields.Float(string='Absence Deduction (Allowances)', compute='_compute_deductions', store=True)
    delay_deduction = fields.Float(string='Delay Deduction', compute='_compute_deductions', store=True)
    total_deductions = fields.Float(string='Total Deductions', compute='_compute_total', store=True)

    @api.depends('employee_id', 'period_id')
    def _compute_name(self):
        for record in self:
            if record.employee_id and record.period_id:
                record.name = f"Deductions for {record.employee_id.name} - {record.period_id.name}"
            else:
                record.name = 'خصم جديد' if record.env.lang == 'ar_001' else 'New Deduction'

    @api.depends('employee_id', 'period_id')
    def _compute_deductions(self):
        for record in self:
            if not record.employee_id or not record.period_id:
                record.absence_deduction_basic = 0.0
                record.absence_deduction_allowances = 0.0
                record.delay_deduction = 0.0
                continue
                
            attendances = self.env['daily.hours.attendance'].search([
                ('employee_id', '=', record.employee_id.id),
                ('date', '>=', record.period_id.start_date),
                ('date', '<=', record.period_id.end_date)
            ])
            
            structure = self.env['daily.hours.salary.structure'].search([
                ('employee_id', '=', record.employee_id.id),
                ('period_id', '=', record.period_id.id)
            ], limit=1)
            
            if not structure:
                record.absence_deduction_basic = 0.0
                record.absence_deduction_allowances = 0.0
                record.delay_deduction = 0.0
                continue

            total_absence = sum(attendances.mapped('absence_days'))
            
            record.absence_deduction_basic = total_absence * structure.day_basic
            record.absence_deduction_allowances = total_absence * structure.day_allowances
            
            delay_days_count = len(attendances.filtered(lambda a: a.delay_hours > 0.5))
            if delay_days_count > 5:
                delay_days_count = 5
            
            record.delay_deduction = delay_days_count * (0.25 * structure.day_basic)

    @api.depends('absence_deduction_basic', 'absence_deduction_allowances', 'delay_deduction')
    def _compute_total(self):
        for record in self:
            # Note: absence_deduction_basic is handled separately in the payslip net salary calculation
            # as part of 'actual_basic_salary'. So we only sum Other deductions here.
            record.total_deductions = record.delay_deduction
