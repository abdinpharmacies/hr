from odoo import fields, models


class AbSalesHeader(models.Model):
    _inherit = "ab_sales_header"

    pos_hr_employee_id = fields.Many2one("ab_hr_employee", copy=False, index=True, readonly=True)
    pos_hr_profile_id = fields.Many2one("ab_employee_access", copy=False, index=True, readonly=True)
    pos_hr_role_id = fields.Many2one("ab_employee_access_sales_role", copy=False, index=True, readonly=True)
    pos_hr_shift_id = fields.Many2one("ab_employee_access_sales_shift", copy=False, index=True, readonly=True)
    pos_hr_session_id = fields.Many2one("ab_employee_access_sales_pos_session", copy=False, index=True, readonly=True)
    pos_hr_service_user_id = fields.Many2one("ab_users", copy=False, index=True, readonly=True)
    pos_hr_device_uid = fields.Char(copy=False, index=True, readonly=True)
    pos_hr_device_name = fields.Char(copy=False, readonly=True)
    pos_hr_device_ip = fields.Char(copy=False, index=True, readonly=True)
