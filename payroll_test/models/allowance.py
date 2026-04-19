from odoo import models, fields, api

class AllowanceType(models.Model):
    _name = 'daily.hours.allowance.type'
    _description = 'Allowance Type'

    name = fields.Char(string='اسم البدلية', required=True)
    calculation_type = fields.Selection([
        ('prorated', 'تناسبي (حسب الحضور)'),
        ('fixed', 'ثابت (غير متأثر بالحضور)'),
        ('custom', 'مخصص (جماجم/بنزين)')
    ], string='نوع الحساب', required=True, default='prorated')
    default_amount = fields.Float(string='القيمة الافتراضية')

class EmployeeAllowance(models.Model):
    _name = 'daily.hours.extra.allowance'
    _description = 'Employee Allowance'

    ab_employee_id = fields.Many2one('ab_hr_employee', string='Employee', required=True, ondelete='cascade')
    allowance_type_id = fields.Many2one('daily.hours.allowance.type', string='Allowance Type', required=True)
    amount = fields.Float(string='Amount', required=True)
    calculation_type = fields.Selection([
        ('prorated', 'Prorated (by Attendance)'),
        ('fixed', 'Fixed (not affected)'),
        ('custom', 'Custom')
    ], string='Calculation Type', required=True)

    @api.onchange('allowance_type_id')
    def _onchange_allowance_type_id(self):
        if self.allowance_type_id:
            self.amount = self.allowance_type_id.default_amount
            self.calculation_type = self.allowance_type_id.calculation_type
