from odoo import models, fields, api
from .engines import get_engine

class DailyHoursPayslip(models.Model):
    _name = 'daily.hours.payslip'
    _description = 'Payslip'

    name = fields.Char(string='Name', compute='_compute_name')
    employee_id = fields.Many2one('ab_hr_employee', string='Employee', required=True)
    period_id = fields.Many2one('daily.hours.payroll.period', string='Payroll Period', required=True)
    
    salary_basic = fields.Float(string='الراتب الأساسي', readonly=True)
    allowances_basic_four = fields.Float(string='البدلات الأساسية', readonly=True)
    attendance_percentage = fields.Float(string='نسبة الحضور (%)', readonly=True)
    agreement_salary = fields.Float(string='راتب الاتفاق', readonly=True)
    
    extra_allowances = fields.Float(string='إجمالي البدلات الإضافية', readonly=True)
    extra_allowances_fixed = fields.Float(string='بدلات إضافية ثابتة', readonly=True)
    extra_allowances_prorated = fields.Float(string='بدلات إضافية تناسبية', readonly=True)
    extra_allowances_custom = fields.Float(string='بدلات إضافية مخصصة', readonly=True)
    
    penalty_late_arrival = fields.Float(string='جزاء تأخير', readonly=True)
    penalty_unauthorized_shift = fields.Float(string='جزاء تغيير وردية', readonly=True)
    penalty_shortage_hours = fields.Float(string='خصم نقص الساعات', readonly=True)
    penalty_forget_fingerprint = fields.Float(string='جزاء نسيان البصمة', readonly=True)
    
    earning_grace_period_overtime = fields.Float(string='إضافي فترة سماح', readonly=True)
    earning_authorized_overtime = fields.Float(string='إضافي بإذن', readonly=True)
    earning_two_hour_permission = fields.Float(string='تعويض إذن ساعتين', readonly=True)
    earning_manual_bonus = fields.Float(string='مكافآت (يدوي)')
    
    attendance_ids = fields.One2many('daily.hours.attendance', 'payslip_id', string='سجل الحضور اليومي')
    
    total_earnings = fields.Float(string='إجمالي الاستحقاقات', readonly=True)
    total_deductions = fields.Float(string='إجمالي الخصومات', readonly=True)
    net_salary = fields.Float(string='الصافي للتسديد', readonly=True)

    def _get_engine(self):
        self.ensure_one()
        return get_engine(self)

    @api.depends('employee_id', 'period_id')
    def _compute_name(self):
        for record in self:
            if record.employee_id and record.period_id:
                record.name = f"قسيمة راتب {record.employee_id.name} - {record.period_id.name}"
            else:
                record.name = "قسيمة جديدة"

    def action_prepare_attendances(self):
        from datetime import timedelta
        for record in self:
            if not record.employee_id or not record.period_id:
                continue
            
            start_date = record.period_id.start_date
            end_date = record.period_id.end_date
            
            # Link existing
            existing_attendances = self.env['daily.hours.attendance'].search([
                ('employee_id', '=', record.employee_id.id),
                ('date', '>=', start_date),
                ('date', '<=', end_date)
            ])
            existing_attendances.write({'payslip_id': record.id})
            
            existing_dates = set(existing_attendances.mapped('date'))
            delta = end_date - start_date
            
            missing_dates = []
            for i in range(delta.days + 1):
                day = start_date + timedelta(days=i)
                if day not in existing_dates:
                    missing_dates.append({
                        'employee_id': record.employee_id.id,
                        'date': day,
                        'payslip_id': record.id,
                        'attendance_status': 'normal'
                    })
            if missing_dates:
                self.env['daily.hours.attendance'].create(missing_dates)

    def generate_payslip(self):
        for record in self:
            record.action_prepare_attendances()
            
            engine = record._get_engine()
            if not engine:
                # If no engine is found for the payroll system, reset values
                record.salary_basic = 0.0
                record.allowances_basic_four = 0.0
                record.extra_allowances = 0.0
                record.extra_allowances_prorated = 0.0
                record.extra_allowances_custom = 0.0
                
                record.penalty_late_arrival = 0.0
                record.penalty_unauthorized_shift = 0.0
                record.penalty_shortage_hours = 0.0
                record.penalty_forget_fingerprint = 0.0
                
                record.earning_grace_period_overtime = 0.0
                record.earning_authorized_overtime = 0.0
                record.earning_two_hour_permission = 0.0
                record.earning_manual_bonus = 0.0
                
                record.total_earnings = 0.0
                record.total_deductions = 0.0
                record.net_salary = 0.0
                continue

            structure = self.env['daily.hours.salary.structure'].search([
                ('employee_id', '=', record.employee_id.id),
                ('period_id', '=', record.period_id.id)
            ], limit=1)
            
            if not structure:
                structure = self.env['daily.hours.salary.structure'].create({
                    'employee_id': record.employee_id.id,
                    'period_id': record.period_id.id,
                })
                
            attendances = record.attendance_ids
            
            # Delegate to Engine
            vals = engine.calculate_payslip(structure, attendances)
            record.update(vals)
            
            # 4. Deductions
            deduction = self.env['daily.hours.deduction'].search([
                ('employee_id', '=', record.employee_id.id),
                ('period_id', '=', record.period_id.id)
            ], limit=1)
            
            if not deduction:
                deduction = self.env['daily.hours.deduction'].create({
                    'employee_id': record.employee_id.id,
                    'period_id': record.period_id.id,
                })
            
            # Note: absence_deduction_basic is already handled in engine.calculate_payslip -> record.salary_basic
            # We only add other deductions (delay, forget fingerprint, other)
            record.penalty_forget_fingerprint = structure.forget_fingerprint_penalty
            record.total_deductions = deduction.total_deductions + record.penalty_forget_fingerprint + record.penalty_late_arrival + record.penalty_unauthorized_shift + record.penalty_shortage_hours
            
            # 5. Final Calculations
            earnings_components = [
                record.salary_basic, 
                record.allowances_basic_four, 
                record.extra_allowances,
                record.earning_grace_period_overtime,
                record.earning_authorized_overtime,
                record.earning_two_hour_permission,
                record.earning_manual_bonus
            ]
            record.total_earnings = sum(earnings_components)
            record.net_salary = record.total_earnings - record.total_deductions
