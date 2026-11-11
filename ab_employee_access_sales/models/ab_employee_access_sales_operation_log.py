from odoo import fields, models


class AbSalesHrOperationLog(models.Model):
    _name = "ab_employee_access_sales_operation_log"
    _description = "Sales HR POS Operation Log"
    _order = "operation_at desc, id desc"

    session_id = fields.Many2one("ab_employee_access_sales_pos_session", index=True, ondelete="set null")
    shift_id = fields.Many2one("ab_employee_access_sales_shift", index=True, ondelete="set null")
    store_id = fields.Many2one("ab_store", index=True, ondelete="set null")
    service_user_id = fields.Many2one("res.users", index=True, ondelete="set null")

    employee_id = fields.Many2one("ab_hr_employee", required=True, index=True, ondelete="restrict")
    profile_id = fields.Many2one("ab_employee_access", index=True, ondelete="set null")
    manager_employee_id = fields.Many2one("ab_hr_employee", index=True, ondelete="set null")
    role_id = fields.Many2one("ab_employee_access_sales_role", index=True, ondelete="set null")

    header_id = fields.Many2one("ab_sales_header", index=True, ondelete="set null")
    operation_type = fields.Selection(
        [
            ("login", "Login"),
            ("unlock", "Unlock"),
            ("lock", "Lock"),
            ("logout", "Logout"),
            ("change_store", "Change Store"),
            ("return_open", "Return Screen Open"),
            ("sale_submit", "Sale Submit"),
            ("price_change", "Price Change"),
            ("discount", "Discount"),
            ("cancel", "Cancel"),
            ("heartbeat", "Heartbeat"),
        ],
        required=True,
        index=True,
    )
    operation_status = fields.Selection(
        [
            ("success", "Success"),
            ("denied", "Denied"),
            ("error", "Error"),
            ("pending", "Pending"),
        ],
        required=True,
        default="success",
        index=True,
    )
    operation_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    device_uid = fields.Char(index=True)
    device_name = fields.Char()
    device_ip = fields.Char(index=True)
    details_json = fields.Text()
