from odoo import models, fields, api
from datetime import datetime

class DailyHoursAttendance(models.Model):
    _name = 'daily.hours.attendance'
    _description = 'Attendance'
    _order = 'date desc, check_in_time desc'
    
    employee_id = fields.Many2one('ab_hr_employee', string='Employee', required=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    day_name = fields.Char(string='اليوم', compute='_compute_day_name', store=True)
    payslip_id = fields.Many2one('daily.hours.payslip', string='إيصال الراتب המربوط', ondelete='set null')
    
    check_in_time = fields.Datetime(string='وقت الحضور')
    check_out_time = fields.Datetime(string='وقت الانصراف')
    
    branch_code = fields.Char(string='كود الفرع')
    branch_name = fields.Char(string='اسم الفرع')
    
    # Authorizations and Overrides
    authorized_shift_change = fields.Boolean(string='تغيير وردية بإذن', default=False)
    manual_shift_start = fields.Float(string='موعد الحضور الجديد (بإذن)', help='يجب أن يكون الفرق ساعة أو أكثر عن الموعد الأساسي')
    authorized_two_hour_permission = fields.Boolean(string='إذن ساعتين', default=False)
    authorized_overtime = fields.Boolean(string='احتساب إضافي بإذن', default=False)
    
    is_unauthorized_shift = fields.Boolean(string='تغيير وردية بدون إذن (مخالفة)', compute='_compute_shift_penalties', store=True)
    is_late_arrival = fields.Boolean(string='تأخير (أكثر من 30 دقيقة)', compute='_compute_shift_penalties', store=True)
    
    shortage_minutes = fields.Float(string='دقائق النقص', compute='_compute_hours', store=True)
    extra_minutes = fields.Float(string='دقائق إضافية', compute='_compute_hours', store=True)
    
    attendance_status = fields.Selection([
        ('normal', 'طبيعي'),
        ('forget_checkout', 'نسيان بصمة انصراف'),
    ], string='حالة البصمة', default='normal', required=True)
    
    working_hours = fields.Float(string='ساعات العمل', compute='_compute_hours', store=True)
    extra_hours = fields.Float(string='ساعات إضافية', compute='_compute_hours', store=True)
    delay_hours = fields.Float(string='ساعات تأخير', compute='_compute_hours', store=True)
    absence_days = fields.Float(string='أيام الغياب', compute='_compute_absence', store=True)

    @api.depends('check_in_time', 'check_out_time', 'employee_id.working_hours_per_day', 'attendance_status')
    def _compute_hours(self):
        for record in self:
            required_hours = record.employee_id.working_hours_per_day or 8.0
            
            if record.check_in_time:
                if record.attendance_status == 'forget_checkout':
                    # Assume full working day if forgot checkout
                    record.working_hours = required_hours
                    record.extra_hours = 0.0
                    record.delay_hours = 0.0
                elif record.check_out_time:
                    delta = record.check_out_time - record.check_in_time
                    hours = delta.total_seconds() / 3600.0
                    record.working_hours = hours
                    
                    if hours > required_hours:
                        record.extra_hours = hours - required_hours
                        record.extra_minutes = record.extra_hours * 60.0
                        record.delay_hours = 0.0
                        record.shortage_minutes = 0.0
                    else:
                        record.extra_hours = 0.0
                        record.extra_minutes = 0.0
                        delay = required_hours - hours
                        record.delay_hours = delay if delay > 0 else 0.0
                        record.shortage_minutes = (delay * 60.0) if delay > 0 else 0.0
                else:
                    record.working_hours = 0.0
                    record.extra_hours = 0.0
                    record.extra_minutes = 0.0
                    record.delay_hours = 0.0
                    record.shortage_minutes = 0.0
            else:
                record.working_hours = 0.0
                record.extra_hours = 0.0
                record.extra_minutes = 0.0
                record.delay_hours = 0.0
                record.shortage_minutes = 0.0

    @api.depends('check_in_time', 'employee_id.shift_scheduled_start', 'authorized_shift_change', 'manual_shift_start')
    def _compute_shift_penalties(self):
        for record in self:
            record.is_unauthorized_shift = False
            record.is_late_arrival = False
            
            if not record.check_in_time:
                continue
                
            # Convert check_in time to float hours directly (simplification, assuming check in is in employee timezone)
            check_in_hour = record.check_in_time.hour + record.check_in_time.minute / 60.0
            scheduled_start = record.employee_id.shift_scheduled_start or 8.0
            
            active_start = scheduled_start
            
            if record.authorized_shift_change:
                # Must be 1 hour or more difference
                if record.manual_shift_start and abs(record.manual_shift_start - scheduled_start) >= 1.0:
                    active_start = record.manual_shift_start
                else:
                    # Invalid manual shift -> falls back to unauthorized shift/late
                    record.is_unauthorized_shift = True
                    
            diff = check_in_hour - active_start
            
            if diff > 0.5: # More than 30 mins late
                record.is_late_arrival = True
            elif abs(diff) > 0.5 and not record.authorized_shift_change: 
                # Arrived > 30 mins DIFFERENT from schedule (early or extremely late logic)
                # Text: حضر مبكرا باكثر من نصف ساعه = تغيير ورديه بدون اذن
                record.is_unauthorized_shift = True
            
            # Text: اذا حضر في غير موعده (بدون اذن) واكمل ساعاته = تغيير ورديه. اذا لم يكمل = تاخير.
            if record.is_unauthorized_shift and record.shortage_minutes > 0:
                record.is_late_arrival = True 
                # Will trigger both, or just shortage+late.

    @api.depends('date')
    def _compute_day_name(self):
        days_ar = {
            0: 'الاثنين (Monday)',
            1: 'الثلاثاء (Tuesday)',
            2: 'الأربعاء (Wednesday)',
            3: 'الخميس (Thursday)',
            4: 'الجمعة (Friday)',
            5: 'السبت (Saturday)',
            6: 'الأحد (Sunday)'
        }
        for record in self:
            if record.date:
                record.day_name = days_ar.get(record.date.weekday(), '')
            else:
                record.day_name = ''
    def _compute_absence(self):
        for record in self:
            if not record.check_in_time:
                record.absence_days = 1.0
            else:
                record.absence_days = 0.0
