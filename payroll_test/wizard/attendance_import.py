from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import io
try:
    import openpyxl
except ImportError:
    openpyxl = None
from datetime import datetime

class DailyHoursAttendanceImport(models.TransientModel):
    _name = 'daily.hours.attendance.import'
    _description = 'Import Attendance from Excel'

    file = fields.Binary(string='ملف الإكسل (.xlsx)', required=True)
    file_name = fields.Char(string='اسم الملف')

    def action_import(self):
        if not openpyxl:
            raise UserError(_("Please install 'openpyxl' library to import Excel files."))
        
        try:
            file_data = base64.b64decode(self.file)
            workbook = openpyxl.load_workbook(io.BytesIO(file_data), data_only=True)
            sheet = workbook.active
            
            # Format: [Code, Name, Job, Branch Code, Branch Name, Check-in, Check-out]
            # Columns (0-indexed): 0: Registration Number, 3: Branch Code, 4: Branch Name, 5: Check-in, 6: Check-out
            
            attendance_obj = self.env['daily.hours.attendance']
            employee_obj = self.env['hr.employee']
            
            records_created = 0
            for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True)):
                if not row or not row[0]: # Skip empty rows
                    continue
                
                reg_num = str(row[0])
                branch_code = str(row[3]) if row[3] else False
                branch_name = str(row[4]) if row[4] else False
                check_in_str = row[5]
                check_out_str = row[6]
                
                employee = employee_obj.search([('registration_number', '=', reg_num)], limit=1)
                if not employee:
                    continue # Or raise warning
                
                # Parse Dates: Expecting "24/01/2026 10:04:32 AM"
                check_in = self._parse_datetime(check_in_str)
                check_out = self._parse_datetime(check_out_str)
                
                status = 'normal'
                if check_in and not check_out:
                    status = 'forget_checkout'
                
                if check_in:
                    attendance_obj.create({
                        'employee_id': employee.id,
                        'date': check_in.date(),
                        'check_in_time': check_in,
                        'check_out_time': check_out,
                        'branch_code': branch_code,
                        'branch_name': branch_name,
                        'attendance_status': status,
                    })
                    records_created += 1
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('نجاح'),
                    'message': _('تم رفع %s سجل بصمة بنجاح.') % records_created,
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(_("Error processing file: %s") % str(e))

    def _parse_datetime(self, value):
        if not value:
            return False
        if isinstance(value, datetime):
            return value
        
        # Formats to try
        formats = [
            '%d/%m/%Y %I:%M:%S %p', # 24/01/2026 10:04:32 AM
            '%Y-%m-%d %H:%M:%S',
            '%d/%m/%Y %H:%M:%S',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(str(value), fmt)
            except ValueError:
                continue
        return False
